# views related to cards
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from api.serializer import CardSuggestedActionsSerializer
from api.models import CardSuggestedAction
from api.utils import *


# getStatusCardMetric
class StatusCardMetricAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'overall_score': calculate_overall_score(user),
            'srpe_score': calculate_srpe(user),
            'readiness_score': calculate_readiness_score(user),
            'sleep_quality': calculate_sleep_quality(user),
            'fatigue_score': calculate_fatigue_score(user),
            'mood_score': calculate_mood_score(user),
            'play_time': calculate_play_time(user)
        }, status=status.HTTP_200_OK)



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