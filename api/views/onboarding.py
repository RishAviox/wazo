from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from datetime import datetime
from django.utils.dateparse import parse_time

from ..models import  OnboardingStep
from ..serializer import OnboardingStepSerializer
from ..utils import is_valid_image, is_valid_image_extension, is_valid_image_size      



""" 
    Handle Onboarding Profile Update.
    Also update question ID i.e, current step(entrypoint).
    Default ID is PQ1, after Q1 is updated, then change current_step PQ2
    which represents the NEXT step.
"""
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

    MAX_IMAGE_SIZE = 5 * 1024 * 1024 # 5MB
    
    def post(self, request, field):
        user = request.user
        # Map the URL field to the data key
        data_key = self.field_mapping.get(field, field)
        data = request.data.get(data_key)

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

        entrypoint = OnboardingStep.objects.get(user=user)
        entrypoint.step = "PQ2" # PQ1 has been completed through this current step.
        entrypoint.save()
        return Response({ 'message': 'Full name updated successfully'}, status=status.HTTP_200_OK)

    def handle_nickname(self, user, nickname):
        user.nickname = nickname
        user.save()

        entrypoint = OnboardingStep.objects.get(user=user)
        entrypoint.step = "PQ3" 
        entrypoint.save()
        return Response({ 'message': 'Nickname updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_gender(self, user, gender):
        user.gender = gender
        user.save()

        entrypoint = OnboardingStep.objects.get(user=user)
        entrypoint.step = "PQ4" 
        entrypoint.save()
        return Response({ 'message': 'Gender updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_dob(self, user, dob):
        try:
            parsed_dob = datetime.strptime(dob, '%Y-%m-%d').date()
        except ValueError:
            return Response({ 'error': 'Invalid date format. Please use YYYY-MM-DD format.' }, status=status.HTTP_400_BAD_REQUEST)
    
        user.dob = parsed_dob
        user.save()

        entrypoint = OnboardingStep.objects.get(user=user)
        entrypoint.step = "PQ5"
        entrypoint.save()
        return Response({'message': 'Date of birth updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_primary_sport(self, user, primary_sport):
        user.primary_sport = primary_sport
        user.save()

        entrypoint = OnboardingStep.objects.get(user=user)
        entrypoint.step = "PQ6"
        entrypoint.save()
        return Response({'message': 'Primary sport updated successfully'}, status=status.HTTP_200_OK)
    
    def handle_role(self, user, role):
        user.role = role
        user.save()

        entrypoint = OnboardingStep.objects.get(user=user)
        entrypoint.step = "PQ7"
        entrypoint.save()
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

        entrypoint = OnboardingStep.objects.get(user=user)
        entrypoint.step = "PQ8"
        entrypoint.save()
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

        entrypoint = OnboardingStep.objects.get(user=user)
        entrypoint.step = "PQ9"
        entrypoint.save()
        return Response({'message': 'Sleep time updated successfully'}, status=status.HTTP_200_OK)

    def handle_picture(self, user, picture):
        # if type(picture) == str:
        #     picture, content_type, error = convert_base64_to_file(picture)
        #     if error:
        #         return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        #     picture.content_type = content_type
                    
        # Validate file type and content type
        if not is_valid_image_extension(picture):
            return Response({'error': 'Only valid image files are accepted (.png, .jpg, .jpeg)'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate file size
        if not is_valid_image_size(picture, self.MAX_IMAGE_SIZE):
            return Response({'error': f'The file size must not exceed {self.MAX_IMAGE_SIZE/1024/1024} MB'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate image integrity and type
        if not is_valid_image(picture):
            return Response({'error': 'The uploaded file is not a valid image or is corrupted'}, status=status.HTTP_400_BAD_REQUEST)

        user.picture = picture
        user.save()

        entrypoint = OnboardingStep.objects.get(user=user)
        entrypoint.step = "COMPLETED"
        entrypoint.save()
        return Response({'message': 'Profile picture updated successfully'}, status=status.HTTP_200_OK)


class OnboardingFlowEntrypoint(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        onboarding_step, created = OnboardingStep.objects.get_or_create(user=user)
        serializer = OnboardingStepSerializer(onboarding_step)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    """
        Current step has been update through onboarding API.
    """


