from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import re
from datetime import datetime
from django.utils.dateparse import parse_time
from PIL import Image

from .models import WajoUser, OnboardingStep
from .serializer import WajoUserSerializer, OnboardingStepSerializer
from .auth import create_token

# Register API
class RegisterAPI(APIView):
    def post(self, request):
        serializer = WajoUserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# SendOTP API
# check if user is registerd before sending otp
class SendOTPAPI(APIView):
    def post(self, request):
        phone_no = request.data.get("phone_no")
        if not phone_no:
            return Response({"error": "Phone number is required"}, status=status.HTTP_400_BAD_REQUEST)
        
        if not re.match(r'^\+?1?\d{9,15}$', phone_no):
            return Response({"error": "Invalid phone number format. Please use a valid international phone number format."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = WajoUser.objects.get(phone_no=phone_no)
            return Response({"message": "OTP sent successfully."}, status=status.HTTP_200_OK)
        except WajoUser.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_404_NOT_FOUND)
        


# Verify OTP API    
class VerifyOTPAPI(APIView):
    def post(self, request):
        phone_no = request.data.get("phone_no")
        otp = request.data.get("otp")

        # Check if both phone number and OTP are provided
        if not phone_no or not otp:
            return Response({"error": "Phone number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate the phone number format
        if not re.match(r'^\+?1?\d{9,15}$', phone_no):
            return Response({"error": "Invalid phone number format. Please use a valid international phone number format."}, status=status.HTTP_400_BAD_REQUEST)

        # Attempt to retrieve the user and verify the OTP
        try:
            user = WajoUser.objects.get(phone_no=phone_no)
            # method to validate OTP
            if user.verify_otp(otp):
                return Response({"message": "OTP verified successfully."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)
        except WajoUser.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_404_NOT_FOUND)
        
class LoginAPI(APIView):
    def post(self, request):
        phone_no = request.data.get("phone_no")
        otp = request.data.get("otp")

        # Check if both phone number and OTP are provided
        if not phone_no or not otp:
            return Response({"error": "Phone number and OTP are required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate the phone number format
        if not re.match(r'^\+?1?\d{9,15}$', phone_no):
            return Response({"error": "Invalid phone number format. Please use a valid international phone number format."}, status=status.HTTP_400_BAD_REQUEST)

        # Attempt to retrieve the user and verify the OTP
        try:
            user = WajoUser.objects.get(phone_no=phone_no)
            # method to validate OTP
            if user.verify_otp(otp):
                token = create_token(user)
                print(token)
                return Response({
                    'token': token
                }, status=status.HTTP_200_OK)
                # return Response({"message": "OTP verified successfully."}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)
        except WajoUser.DoesNotExist:
            return Response({"error": "User does not exist"}, status=status.HTTP_404_NOT_FOUND)
        

class OnboardingAPI(APIView):
    permission_classes = [IsAuthenticated]
    field_mapping = {
        'DOB': 'dob',
        'primary-sport': 'primary_sport',
        'wake-up-time': 'wake_up_time',
        'sleep-time': 'sleep_time',
        'activities-n-events': 'activities',
        'profile-picture': 'picture',
    }

    MAX_IMAGE_SIZE = 2 * 1024 * 1024 # 2MB
    
    def post(self, request, field):
        user = request.user
        # Map the URL field to the data key
        data_key = self.field_mapping.get(field, field)
        data = request.data.get(data_key)
        print(user, field, data_key, data)

        if data is None:
            return Response({'error': f'{data_key} field is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Dynamic method based on the fielor data_key
        handler_method_name = f"handle_{data_key}"
        handler = getattr(self, handler_method_name, None)

        if not handler:
            return Response({ 'error': 'Invalid onboarding field'}, status=status.HTTP_400_BAD_REQUEST)
        
        return handler(user, data)
    

    def handle_name(self, user, name):
        user.name = name
        user.save()
        return Response({ 'message': 'Full name updated successfully'}, status=status.HTTP_200_OK)

    def handle_nickname(self, user, nickname):
        user.nickname = nickname
        user.save()
        return Response({ 'message': 'Nickname updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_gender(self, user, gender):
        user.gender = gender
        user.save()
        return Response({ 'message': 'Gender updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_dob(self, user, dob):
        try:
            parsed_dob = datetime.strptime(dob, '%Y-%m-%d').date()
        except ValueError:
            return Response({ 'error': 'Invalid date format. Please use YYYY-MM-DD format.' }, status=status.HTTP_400_BAD_REQUEST)
    
        user.dob = parsed_dob
        user.save()
        return Response({'message': 'Date of birth updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_primary_sport(self, user, primary_sport):
        user.primary_sport = primary_sport
        user.save()
        return Response({'message': 'Primary sport updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_role(self, user, role):
        user.role = role
        user.save()
        return Response({'message': 'Role updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_wake_up_time(self, user, wake_up_time):
        try:
            validated_time = parse_time(wake_up_time)
            if validated_time is None:
                raise ValueError('Invalid time format')
        except ValueError:
            return Response({'error': 'Invalid time format. Please use HH:MM format.'}, status=status.HTTP_400_BAD_REQUEST)

        user.wake_up_time = validated_time
        user.save()
        return Response({'message': 'Wake-up time updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_sleep_time(self, user, sleep_time):
        try:
            validated_time = parse_time(sleep_time)
            if validated_time is None:
                raise ValueError('Invalid time format')
        except ValueError:
            return Response({'error': 'Invalid time format. Please use HH:MM format.'}, status=status.HTTP_400_BAD_REQUEST)

        user.sleep_time = validated_time
        user.save()
        return Response({'message': 'Sleep time updated successfully'}, status=status.HTTP_200_OK)

    def handle_activities(self, user, activities):
        user.activities = activities
        user.save()
        return Response({'message': 'Activities updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_picture(self, user, picture):
        
        def is_valid_image_extension(file):
            return file.name.lower().endswith(('.png', '.jpg', '.jpeg'))
        
        def is_valid_image_content_type(file):
            return file.content_type in ['image/png', 'image/jpeg']
        
        def is_valid_image(file):
            try:
                with Image.open(file) as img:
                    img.verify()  # Verify that it is an image
                return True
            except (IOError, SyntaxError) as e:
                print(f"Invalid image file: {e}")  # Not an image, or corrupted
                return False
        
        def is_valid_image_size(file):
            if file.size > self.MAX_IMAGE_SIZE:
                return False
            return True
            
        # Validate file type and content type
        if not is_valid_image_extension(picture) or not is_valid_image_content_type(picture):
            return Response({'error': 'Only valid image files are accepted (.png, .jpg, etc.)'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size
        if not is_valid_image_size(picture):
            return Response({'error': f'The file size must not exceed {self.MAX_IMAGE_SIZE/1024/1024} MB'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate image integrity and type
        if not is_valid_image(picture):
            return Response({'error': 'The uploaded file is not a valid image or is corrupted'}, status=status.HTTP_400_BAD_REQUEST)

        user.picture = picture
        user.save()

        return Response({'message': 'Profile picture updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_location(self, user, location):
        user.location = location
        user.save()
        return Response({'message': 'Location updated successfully'}, status=status.HTTP_200_OK)

    def handle_affiliation(self, user, affiliation):
        user.affiliation = affiliation
        user.save()
        return Response({'message': 'Affiliation details updated successfully'}, status=status.HTTP_200_OK)
    


class OnboardingFlowEntrypoint(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        onboarding_step, created = OnboardingStep.objects.get_or_create(user=user)
        serializer = OnboardingStepSerializer(onboarding_step)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request):
        user = request.user
        onboarding_step, created = OnboardingStep.objects.get_or_create(user=user)
        serializer = OnboardingStepSerializer(onboarding_step, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)