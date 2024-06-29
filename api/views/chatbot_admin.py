# django admin user login for token
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework import status
from django.contrib.auth import authenticate
from django.utils import timezone
from django.utils.timezone import make_aware, now, datetime
from django.conf import settings
import jwt

from api.serializer import DailyWellnessUserResponseSerializer, RPEUserResponseSerializer
from api.models import WajoUser, DailyWellnessUserResponse, RPEUserResponse

# chatbot admin user is used to push data from chabot responses
# make sure to use _Bearer instead of Bearer during API call
class AdminTokenObtainView(APIView):
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)

        if user is not None and user.is_staff:
            payload = {
                'id': user.id,
                'exp': timezone.now() + timezone.timedelta(hours=24),  # Short-lived
                'iat': timezone.now(),
                'token_type': 'access',
            }
            access_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

            payload = {
                'id': user.id,
                'exp': timezone.now() + timezone.timedelta(days=7),  # Long Lived
                'iat': timezone.now(),
                'token_type': 'access',
            }
            refresh_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
            return Response({
                'access': access_token,
                'refresh': refresh_token
            }, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Invalid username or password"}, status=status.HTTP_401_UNAUTHORIZED)
        


class IsAdminUser(BasePermission):
    """
    Custom permission to only allow access to admin/staff users.
    """
    def has_permission(self, request, view):
        try:
            return bool(request.user and request.user.is_authenticated and request.user.is_staff)
        except:
            False

    

# DailyWellness User Responses
# Check if an entry for the user already exists for the current day.
# If an entry exists, update the JSON field.
# If no entry exists, create a new one.

class DailyWellnessUserResponseCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, *args, **kwargs):
        data = request.data.copy() # mutable copy
        print(data)
        phone_no = data.get('phone_no', None)
        if not phone_no:
            return Response({'error': 'User phone number is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = WajoUser.objects.get(phone_no=phone_no)
        except WajoUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.make_aware(datetime.combine(now().date(), datetime.min.time()))
        user_response = DailyWellnessUserResponse.objects.filter(user=user, created_on__gte=today).first()
        
        new_response_data = data.get('response', [])
        print("new_response_data: ", new_response_data)
    
        if user_response:
            existing_response = user_response.response
            # Update the existing JSON field
            for new_entry in new_response_data:
                updated = False
                for existing_entry in existing_response:
                    if existing_entry['question_id'] == new_entry['question_id']:
                        existing_entry['answer_id'] = new_entry['answer_id']
                        updated = True
                        break
                # if not updated existing entry, then append to JSON list.
                if not updated:
                    existing_response.append(new_entry)

            user_response.response = existing_response
            user_response.save()
            serializer = DailyWellnessUserResponseSerializer(user_response)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data['user'] = user
            serializer = DailyWellnessUserResponseSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                print(serializer.data)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RPEUserResponseCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, *args, **kwargs):
        data = request.data.copy() # mutable copy
        print(data)
        phone_no = data.get('phone_no', None)
        if not phone_no:
            return Response({'error': 'User phone number is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = WajoUser.objects.get(phone_no=phone_no)
        except WajoUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        today = timezone.make_aware(datetime.combine(now().date(), datetime.min.time()))
        user_response = RPEUserResponse.objects.filter(user=user, created_on__gte=today).first()
        
        new_response_data = data.get('response', [])
        print("new_response_data: ", new_response_data)
    
        if user_response:
            existing_response = user_response.response
            # Update the existing JSON field
            for new_entry in new_response_data:
                updated = False
                for existing_entry in existing_response:
                    if existing_entry['question_id'] == new_entry['question_id']:
                        existing_entry['answer_id'] = new_entry['answer_id']
                        updated = True
                        break
                # if not updated existing entry, then append to JSON list.
                if not updated:
                    existing_response.append(new_entry)

            user_response.response = existing_response
            user_response.save()
            serializer = RPEUserResponseSerializer(user_response)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            data['user'] = user
            serializer = RPEUserResponseSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                print(serializer.data)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
