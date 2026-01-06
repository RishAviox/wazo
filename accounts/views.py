import jwt
from django.conf import settings
from rest_framework import status
from rest_framework.views import APIView
from django.db.models.base import ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from jwt.exceptions import ExpiredSignatureError, DecodeError, InvalidTokenError


from .models import WajoUser, WajoUserDevice, UserRequest
from .utils import (
    generate_and_send_otp,
    validate_otp,
    generate_access_token,
    generate_refresh_token,
    get_country_from_phone,
)
from .serializer import UserRequestSerializer, WajoUserSerializer
from onboarding.models import OnboardingStep


# SendOTP API
class SendOTPAPI(APIView):
    def post(self, request):
        phone_no = request.data.get("phone_no")
        if not phone_no:
            return Response(
                {"error": "Phone number is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not phone_no.startswith("+"):
            return Response(
                {
                    "error": "Invalid phone number format. Please use a valid international phone number format."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        country, country_code = get_country_from_phone(phone_no)
        if not country or not country_code:
            return Response(
                {
                    "error": "Invalid phone number or country code. Please use a valid international format starting with '+'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            generate_and_send_otp(phone_no)
            return Response(
                {"message": "OTP sent successfully."}, status=status.HTTP_200_OK
            )
        except Exception as e:  # Catch any exceptions from generate_and_send_otp
            return Response(
                {"error": "Failed to send OTP"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Both New REGISTRATION and LOGIN done thorugh only one route
class LoginAPI(APIView):
    def post(self, request):
        phone_no = request.data.get("phone_no")
        _data = request.data.copy()
        fcm_token = _data.get("fcm_token", None)
        if not fcm_token:
            # Token will stored in WajoUserDevices if not exists
            # for sending Notifications.
            # will be removed when LOGOUT api is called
            return Response(
                {"error": "FCM Token is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        otp = request.data.get("otp")
        selected_language = request.data.get("selected_language")

        # Check if both phone number and OTP are provided
        if not phone_no or not otp:
            return Response(
                {"error": "Phone number and OTP are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not phone_no.startswith("+"):
            return Response(
                {
                    "error": "Invalid phone number format. Please use a valid international phone number format."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        country, country_code = get_country_from_phone(phone_no)
        if not country or not country_code:
            return Response(
                {
                    "error": "Invalid phone number or country code. Please use a valid international format starting with '+'."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Attempt to retrieve the user and verify the OTP
        try:
            # method to validate OTP
            if validate_otp(phone_no, otp):
                # Invitation Token Logic
                invitation_token = request.data.get("invitation_token")

                if invitation_token:
                    try:
                        user = WajoUser.objects.get(id=invitation_token)

                        if user.is_registered:
                            return Response(
                                {"error": "This account is already registered."},
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        # Update the placeholder user with details calculated from phone
                        user.phone_no = phone_no
                        user.country = country
                        user.country_code = country_code
                        user.is_registered = True
                        # Maintain created_via as EXCEL if it was, or set to MANUAL if not
                        user.save()
                        print(
                            f"Placeholder user {user.id} registered via invitation with phone {phone_no}"
                        )
                        created = False  # It was a placeholder, so we updated it
                    except (WajoUser.DoesNotExist, ValidationError):
                        return Response(
                            {"error": "Invalid or expired invitation link."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    # Normal Login/Registration via Phone
                    try:
                        user = WajoUser.objects.get(phone_no=phone_no)
                        created = False
                        print(
                            f"Found existing user with exact phone number: {user.phone_no}"
                        )

                        if not user.is_registered:
                            user.is_registered = True
                            user.country = country
                            user.country_code = country_code
                            user.save(
                                update_fields=[
                                    "is_registered",
                                    "country",
                                    "country_code",
                                ]
                            )
                            print(
                                f"Updated placeholder user to registered with country {country}: {user.phone_no}"
                            )
                    except WajoUser.DoesNotExist:
                        # Create new user
                        # Create new user with details calculated from phone
                        user = WajoUser.objects.create(
                            phone_no=phone_no,
                            country=country,
                            country_code=country_code,
                            is_registered=True,
                            created_via="MANUAL",
                        )
                        created = True
                        print(
                            f"Created new user with original phone number: {phone_no}"
                        )

                access_token = generate_access_token(user)
                refresh_token = generate_refresh_token(user)

                # for redirecting to screen after LOGIN on mobile app.
                if created:
                    step = "PQ1"
                    user.selected_language = selected_language
                    user.save()
                    # OnboardingStep is created automatically via signal (post_save)
                else:
                    # Get existing user's onboarding step
                    try:
                        entrypoint = OnboardingStep.objects.get(user=user)
                        step = entrypoint.step
                    except OnboardingStep.DoesNotExist:
                        # Fallback: create OnboardingStep if it doesn't exist (shouldn't happen normally)
                        OnboardingStep.objects.create(user=user, step="PQ1")
                        step = "PQ1"

                # add FCM token wajo user devices if not exists
                device, _ = WajoUserDevice.objects.get_or_create(
                    user=user, fcm_token=fcm_token
                )
                print("Wajo User Device: ", device, _)

                return Response(
                    {
                        "token": access_token,
                        "refresh": refresh_token,
                        "step": step,
                        "selected_language": user.selected_language,
                    },
                    status=status.HTTP_200_OK,
                )
            else:
                return Response(
                    {"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            print(e)
            return Response(
                {"error": "Failed to validate OTP, try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )


# LOGOUT API
class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fcm_token = request.data.get("fcm_token", None)
        if not fcm_token:
            # will be removed when LOGOUT api is called
            return Response(
                {"error": "FCM Token is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        device, _ = WajoUserDevice.objects.filter(
            user=request.user, fcm_token=fcm_token
        ).delete()
        print("remove user device: ", device, _)
        return Response({"message": "logout successful"}, status=status.HTTP_200_OK)


# token refresh
class RefreshTokenAPI(APIView):
    def post(self, request):
        # Extract refresh token
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Decode the refresh token
            payload = jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=["HS256"]
            )

            # Validate token type
            if payload.get("token_type") != "refresh":
                return Response(
                    {"error": "Invalid token type."}, status=status.HTTP_400_BAD_REQUEST
                )

            # Fetch user from payload by ID
            user = WajoUser.objects.filter(id=payload["id"]).first()
            if not user:
                return Response(
                    {"error": "User not found."}, status=status.HTTP_400_BAD_REQUEST
                )

            # Generate a new access token
            access_token = generate_access_token(user)
            return Response({"token": access_token}, status=status.HTTP_200_OK)

        except ExpiredSignatureError:
            return Response(
                {"error": "Refresh token has expired."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        except DecodeError:
            return Response(
                {"error": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST
            )
        except InvalidTokenError:
            return Response(
                {"error": "Malformed token."}, status=status.HTTP_400_BAD_REQUEST
            )


class WajoUserProfileDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            serializer = WajoUserSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except WajoUser.DoesNotExist:
            return Response(
                {"error": "User does not exist"}, status=status.HTTP_400_BAD_REQUEST
            )


class UserRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        request.data["user"] = request.user.id
        serializer = UserRequestSerializer(data=request.data)

        if serializer.is_valid():
            # Try to update or create the UserRequest
            user_request, created = UserRequest.objects.update_or_create(
                user=request.user, defaults=serializer.validated_data
            )

            # Serialize the result after saving
            response_data = UserRequestSerializer(user_request).data

            if created:
                return Response(response_data, status=status.HTTP_201_CREATED)
            else:
                return Response(response_data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
