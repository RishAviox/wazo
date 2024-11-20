from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings

import jwt
import re

from jwt.exceptions import ExpiredSignatureError, DecodeError, InvalidTokenError

from ..models import WajoUser, OnboardingStep, WajoUserDevice
from ..utils import generate_and_send_otp, validate_otp, generate_access_token, generate_refresh_token



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
                user, created = WajoUser.objects.get_or_create(phone_no=phone_no)
                access_token = generate_access_token(user)
                refresh_token = generate_refresh_token(user)
                
                # for redirecting to screen after LOGIN on mobile app.
                if created:
                    step = 'PQ1'
                    user.selected_language = selected_language
                    user.save()
                else:
                    entrypoint = OnboardingStep.objects.get(user=user)
                    step = entrypoint.step

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
        except:
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

            # Fetch user from payload
            user = WajoUser.objects.filter(phone_no=payload['id']).first()
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
