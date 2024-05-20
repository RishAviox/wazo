from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ..serializer import WajoUserSerializer
from ..models import WajoUser

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
