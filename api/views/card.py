# views related to cards
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.utils.timezone import datetime
from django.utils import timezone
from collections import defaultdict, OrderedDict


from api.serializer import (CardSuggestedActionsSerializer, 
                            StatusCardMetricsSerializer, WajoUserSerializer,
                            OneTimeEventsSerializer, RecurringEventsSerializer,
                        )
from api.models import CardSuggestedAction, StatusCardMetrics
from api.utils import *


# getStatusCardMetric
class StatusCardMetricAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):

        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                try:
                    metrics = StatusCardMetrics.objects.filter(user=player).latest('updated_on')
                    player_data.append({
                                'profile': WajoUserSerializer(player).data,
                                'metrics': StatusCardMetricsSerializer(metrics).data
                            })

                except StatusCardMetrics.DoesNotExist:
                    player_data.append({
                                'profile': WajoUserSerializer(player).data,
                                'metrics': {}
                            })

            print("player_data for coach: ", player_data)
            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            try:
                metrics = StatusCardMetrics.objects.filter(user=request.user).latest('updated_on')
                serializer = StatusCardMetricsSerializer(metrics)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except:
                return Response({}, status=status.HTTP_200_OK)

# Get 5 days events for the DailySnapshot card
class DailySnapshortCardAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date_str = request.query_params.get('start_date')
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            start_date = timezone.make_aware(start_date, timezone.get_current_timezone())
        else:
            start_date = datetime.today()

        one_time_events, recurring_events = get_events_for_next_5_days(user=request.user, start_date=start_date)

        # one_time_events_data = OneTimeEventsSerializer(one_time_events, many=True).data
        one_time_events_data = [
            {       
                'event_type': event.event_type,
                'event': event.event,
                'date': timezone.localtime(event.date),
                'source': event.source,
            }
            for event in one_time_events
        ]
    
        combined_events = one_time_events_data + recurring_events
        events_by_date = defaultdict(list)
        for event in combined_events:
            event_date = event['date'].date().isoformat()
            events_by_date[event_date].append(event)

        # Sort events for each day by time (latest first)
        for event_date in events_by_date:
            events_by_date[event_date].sort(key=lambda x: x['date'])


        # Sort the dictionary by date keys (ascending order)
        events_by_date = OrderedDict(sorted(events_by_date.items()))


        return Response(events_by_date, status=status.HTTP_200_OK)



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