from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..serializer import WajoUserSerializer
from ..models import WajoUser, WajoUserDevice

# USER Prfoile Details
class WajoUserProfileDetails(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            serializer = WajoUserSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except WajoUser.DoesNotExist:
            return Response({'error': 'User does not exist'}, status=status.HTTP_400_BAD_REQUEST)


class NotificationsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, fcm_token):
        try:
            device = WajoUserDevice.objects.get(user=request.user, fcm_token=fcm_token)
            notifications = device.notifications.order_by('-created_on')[:10]
            # Return a list of notifications or any specific fields
            notification_list = [
                {
                    'title': n.title,
                    'body': n.body,
                    'postback': n.postback,
                    'created_on': n.created_on
                }
                for n in notifications
            ]
            return Response(notification_list, status=status.HTTP_200_OK)
    
        except WajoUserDevice.DoesNotExist:
            return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
