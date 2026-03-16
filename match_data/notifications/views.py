from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated


from accounts.models import WajoUserDevice


class NotificationsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, fcm_token):
        try:
            device = WajoUserDevice.objects.get(user=request.user, fcm_token=fcm_token)
            notifications = device.notifications.filter(is_read=False).order_by('-created_on')[:10]
            # Return a list of notifications or any specific fields
            notification_list = [
                {
                    'id': n.pk,
                    'title': n.title,
                    'body': n.body,
                    'postback': n.postback,
                    'is_read': n.is_read,
                    'created_on': n.created_on
                }
                for n in notifications
            ]
            return Response(notification_list, status=status.HTTP_200_OK)
    
        except WajoUserDevice.DoesNotExist:
            return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
    
    def patch(self, request, fcm_token, pk):
        try:
            device = WajoUserDevice.objects.get(user=request.user, fcm_token=fcm_token)
            notification = device.notifications.get(id=pk)
            notification.is_read = True
            notification.save()

            return Response({
                'id': notification.pk,
                'title': notification.title,
                'body': notification.body,
                'postback': notification.postback,
                'is_read': notification.is_read,
                'created_on': notification.created_on
            })
        except WajoUserDevice.DoesNotExist:
            return Response({'error': 'Device not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            return Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)

