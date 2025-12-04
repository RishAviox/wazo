from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings

import jwt
import re
from jwt.exceptions import ExpiredSignatureError, DecodeError, InvalidTokenError

from .models import WajoUser, WajoUserDevice, UserRequest
from .utils import generate_and_send_otp, validate_otp, generate_access_token, generate_refresh_token, find_user_by_normalized_phone, normalize_phone_number
from .serializer import UserRequestSerializer, WajoUserSerializer

from onboarding.models import OnboardingStep


# SendOTP API
class SendOTPAPI(APIView):
    def post(self, request):
        phone_no = request.data.get("phone_no")
        if not phone_no:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not re.match(r'^\+?1?\d{9,15}$', phone_no):
            return Response({"error": "Invalid phone number format. Please use a valid international phone number format."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            generate_and_send_otp(phone_no)
            return Response({"message": "OTP sent successfully."}, status=status.HTTP_200_OK)
        except Exception as e:  # Catch any exceptions from generate_and_send_otp
            return Response({"error": "Failed to send OTP"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# Both New REGISTRATION and LOGIN done thorugh only one route
class LoginAPI(APIView):
    def post(self, request):
        phone_no = request.data.get("phone_no")
        _data = request.data.copy()
        fcm_token = _data.get('fcm_token', None)
        if not fcm_token:
            # Token will stored in WajoUserDevices if not exists
            # for sending Notifications.
            # will be removed when LOGOUT api is called
            return Response({ 'error': 'FCM Token is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        otp = request.data.get("otp")
        selected_language = request.data.get("selected_language")

        # Check if both phone number and OTP are provided
        if not phone_no or not otp:
            return Response({"error": "Phone number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate the phone number format
        if not re.match(r'^\+?1?\d{9,15}$', phone_no):
            return Response({"error": "Invalid phone number format. Please use a valid international phone number format."}, status=status.HTTP_400_BAD_REQUEST)

        # Attempt to retrieve the user and verify the OTP
        try:
            # method to validate OTP
            if validate_otp(phone_no, otp):
                # Step 1: Try exact match with the original phone number provided in request
                try:
                    user = WajoUser.objects.get(phone_no=phone_no)
                    created = False
                    print(f"Found existing user with exact phone number: {user.phone_no}")
                except WajoUser.DoesNotExist:
                    # Step 2: Not found with exact match, try normalized phone number
                    normalized_phone = normalize_phone_number(phone_no)
                    if not normalized_phone:
                        return Response({"error": "Invalid phone number format"}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Find user by normalized phone number
                    # This handles cases where user exists with different format:
                    # - User with normalized phone (e.g., "1234567890")
                    # - User with country code (e.g., "+11234567890" or "+911234567890")
                    existing_user = find_user_by_normalized_phone(phone_no)
                    
                    if existing_user:
                        # Found user with normalized phone number
                        user = existing_user
                        created = False
                        print(f"Found existing user: {user.phone_no} (normalized from input: {phone_no} -> {normalized_phone})")
                    else:
                        # Step 3: Still not found, create new user with ORIGINAL phone number from request
                        user = WajoUser.objects.create(phone_no=phone_no)
                        created = True
                        print(f"Created new user with original phone number: {phone_no}")
                
                access_token = generate_access_token(user)
                refresh_token = generate_refresh_token(user)
                
                # for redirecting to screen after LOGIN on mobile app.
                if created:
                    step = 'PQ1'
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
                        OnboardingStep.objects.create(user=user, step='PQ1')
                        step = 'PQ1'

                # add FCM token wajo user devices if not exists
                device, _ = WajoUserDevice.objects.get_or_create(user=user, fcm_token=fcm_token)
                print("Wajo User Device: ", device, _)

                return Response({
                    'token': access_token,
                    'refresh': refresh_token,
                    'step': step,
                    'selected_language': user.selected_language
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response({"error": "Failed to validate OTP, try again."}, status=status.HTTP_400_BAD_REQUEST)
        

# LOGOUT API
class LogoutAPI(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fcm_token = request.data.get('fcm_token', None)
        if not fcm_token:
            # will be removed when LOGOUT api is called
            return Response({ 'error': 'FCM Token is required.'}, status=status.HTTP_400_BAD_REQUEST)
        
        device, _ = WajoUserDevice.objects.filter(
                                    user=request.user, 
                                    fcm_token=fcm_token
                                ).delete()
        print("remove user device: ", device, _)
        return Response({ 'message': 'logout successful'}, status=status.HTTP_200_OK)


# token refresh
class RefreshTokenAPI(APIView):
    def post(self, request):
        # Extract refresh token
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Decode the refresh token
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])
            
            # Validate token type
            if payload.get('token_type') != 'refresh':
                return Response({'error': 'Invalid token type.'}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch user from payload (normalize phone number to handle format differences)
            user = find_user_by_normalized_phone(payload['id'])
            if not user:
                return Response({'error': 'User not found.'}, status=status.HTTP_400_BAD_REQUEST)

            # Generate a new access token
            access_token = generate_access_token(user)
            return Response({'token': access_token}, status=status.HTTP_200_OK)

        except ExpiredSignatureError:
            return Response({'error': 'Refresh token has expired.'}, status=status.HTTP_401_UNAUTHORIZED)
        except DecodeError:
            return Response({'error': 'Invalid refresh token.'}, status=status.HTTP_400_BAD_REQUEST)
        except InvalidTokenError:
            return Response({'error': 'Malformed token.'}, status=status.HTTP_400_BAD_REQUEST)


class WajoUserProfileDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            serializer = WajoUserSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except WajoUser.DoesNotExist:
            return Response({'error': 'User does not exist'}, status=status.HTTP_400_BAD_REQUEST)


class UserRequestCreateView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        request.data["user"] = request.user.phone_no
        serializer = UserRequestSerializer(data=request.data)
        
        if serializer.is_valid():
            # Try to update or create the UserRequest
            user_request, created = UserRequest.objects.update_or_create(
                user=request.user,
                defaults=serializer.validated_data
            )
            
            # Serialize the result after saving
            response_data = UserRequestSerializer(user_request).data
            
            if created:
                return Response(response_data, status=status.HTTP_201_CREATED)
            else:
                return Response(response_data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
