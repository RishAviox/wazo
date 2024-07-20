# views related to cards
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.utils.timezone import datetime
from django.utils import timezone
from django.conf import settings
from django.db.models import Sum, F, FloatField, ExpressionWrapper
from django.db.models.functions import Cast, Coalesce
from django.db.models.fields.json import KeyTextTransform


from collections import defaultdict, OrderedDict

from openai import AzureOpenAI


from api.serializer import (CardSuggestedActionsSerializer, 
                            StatusCardMetricsSerializer, WajoUserSerializer,
                        )
from api.models import CardSuggestedAction, StatusCardMetrics, PerformanceMetrics
from api.utils import *


openai_client = AzureOpenAI(
                azure_endpoint=settings.WAJO_AZURE_OPENAI_ENDPOINT,
                api_version="2022-12-01",
                api_key=settings.WAJO_AZURE_OPENAI_KEY
            )

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

# Get 5 days events for the DailySnapshot card --> changed to per-day
class DailySnapshortCardAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        start_date_str = request.query_params.get('start_date')
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            start_date = timezone.make_aware(start_date, timezone.get_current_timezone())
        else:
            start_date = datetime.today()

        one_time_events, recurring_events = get_events_for_date(user=request.user, event_date=start_date)

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

        combined_events.sort(key=lambda x: x['date'])

        response = {
            'events': combined_events
        }

        return Response(response, status=status.HTTP_200_OK)

        # one_time_events, recurring_events = get_events_for_next_5_days(user=request.user, start_date=start_date)

        # # one_time_events_data = OneTimeEventsSerializer(one_time_events, many=True).data
        # one_time_events_data = [
        #     {       
        #         'event_type': event.event_type,
        #         'event': event.event,
        #         'date': timezone.localtime(event.date),
        #         'source': event.source,
        #     }
        #     for event in one_time_events
        # ]
    
        # combined_events = one_time_events_data + recurring_events
        # events_by_date = defaultdict(list)
        # for event in combined_events:
        #     event_date = event['date'].date().isoformat()
        #     events_by_date[event_date].append(event)

        # # Sort events for each day by time (latest first)
        # for event_date in events_by_date:
        #     events_by_date[event_date].sort(key=lambda x: x['date'])


        # # Sort the dictionary by date keys (ascending order)
        # events_by_date = OrderedDict(sorted(events_by_date.items()))


        # return Response(events_by_date, status=status.HTTP_200_OK)


# card no. 7, performance metrics API
class PerformanceMetricsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        metrics_data = PerformanceMetrics.objects.filter(user=request.user)

        # Return an empty dictionary if no data is available for the user
        if not metrics_data.exists():
            return Response({}, status=status.HTTP_200_OK)

        total_shots = metrics_data.aggregate(
            total_shots=Sum(
                Coalesce(Cast(KeyTextTransform('value', 'metrics__total_shot'), FloatField()), 0), output_field=FloatField()
            )
        )

        total_passes = metrics_data.aggregate(
            total_passes=Sum(
                Coalesce(Cast(KeyTextTransform('value', 'metrics__pass'), FloatField()), 0), output_field=FloatField()
            )
        )

        results = {
            'Rating': metrics_data.aggregate(total_rating=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__rating'), FloatField()), 0), output_field=FloatField())))['total_rating'],
            'Play Time': metrics_data.aggregate(total_play_time=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__play_time'), FloatField()), 0), output_field=FloatField())))['total_play_time'],
            'Goals': metrics_data.aggregate(total_goals=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__goal'), FloatField()), 0), output_field=FloatField())))['total_goals'],
            'Assists': metrics_data.aggregate(total_assists=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__assist'), FloatField()), 0), output_field=FloatField())))['total_assists'],
            'Shooting Accuracy (%)': (metrics_data.aggregate(total_shot_on_target=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__shot_on_target'), FloatField()), 0), output_field=FloatField())))['total_shot_on_target'] / total_shots['total_shots']) * 100 if total_shots['total_shots'] else 0,
            'Pass Accuracy (%)': (metrics_data.aggregate(total_pass_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__pass_succeeded'), FloatField()), 0), output_field=FloatField())))['total_pass_succeeded'] / total_passes['total_passes']) * 100 if total_passes['total_passes'] else 0,
            'Expected Pass Completion (xP)': metrics_data.aggregate(total_pass_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__pass_succeeded'), FloatField()), 0), output_field=FloatField())))['total_pass_succeeded'] / total_passes['total_passes'] if total_passes['total_passes'] else 0,
            'Expected Receiver (xReceiver)': (metrics_data.aggregate(total_take_on_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__take_on_succeeded'), FloatField()), 0), output_field=FloatField())))['total_take_on_succeeded'] / metrics_data.aggregate(total_take_on=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__take_on'), FloatField()), 0), output_field=FloatField())))['total_take_on'] if metrics_data.aggregate(total_take_on=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__take_on'), FloatField()), 0), output_field=FloatField())))['total_take_on'] else 0) * (metrics_data.aggregate(total_forward_pass_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass_succeeded'), FloatField()), 0), output_field=FloatField())))['total_forward_pass_succeeded'] / metrics_data.aggregate(total_forward_pass=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass'), FloatField()), 0), output_field=FloatField())))['total_forward_pass'] if metrics_data.aggregate(total_forward_pass=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass'), FloatField()), 0), output_field=FloatField())))['total_forward_pass'] else 0),
            'Expected Threat (xThreat)': metrics_data.aggregate(x_threat=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass_succeeded'), FloatField()), 0) * 1.2 + Coalesce(Cast(KeyTextTransform('value', 'metrics__final_third_area_pass_succeeded'), FloatField()), 0) * 1.5 * 2, output_field=FloatField())))['x_threat'],
        }

        print(f"performance metrics for the user({request.user}): ", results)
        return Response(results, status=status.HTTP_200_OK)
        


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
        

# cards greetings api
class CardGreetingsAPI(APIView):
    def get(self, request, card):
        pass