# views related to cards
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.serializer import CardSuggestedActionsSerializer, StatusCardMetricsSerializer
from api.models import CardSuggestedAction, StatusCardMetrics
from api.utils import *


# getStatusCardMetric
class StatusCardMetricAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            actions = StatusCardMetrics.objects.filter(user=request.user).latest('updated_on')
            serializer = StatusCardMetricsSerializer(actions)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response({ 'error': 'status metrics data not found'}, status=status.HTTP_400_BAD_REQUEST)



# getCardSuggestedActions
class CardSuggestedActionsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, card):
        try:
            actions = CardSuggestedAction.objects.filter(card_name=card).all()
            serializer = CardSuggestedActionsSerializer(actions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response({ 'error': 'card data not found'}, status=status.HTTP_400_BAD_REQUEST)