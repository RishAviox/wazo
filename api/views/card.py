# views related to cards
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.utils.timezone import datetime
from django.utils import timezone
from django.conf import settings


from openai import AzureOpenAI


from api.serializer import (
                        CardSuggestedActionsSerializer, StatusCardMetricsSerializer, 
                    )
from api.models import CardSuggestedAction, StatusCardMetrics
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
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_status_card_metrics(player)
                    })

            print("player_data for coach: ", player_data)
            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_status_card_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)



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

        combined_events = get_daily_snapshot(user=request.user, event_date=start_date)
        
        response = {
            'events': combined_events
        }
        return Response(response, status=status.HTTP_200_OK)


# card no. 7, performance metrics API
class PerformanceMetricsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_performance_metrics(player)
                    })

            print("performance_metrics for coach: ", player_data)
            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_performance_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)
    

# card no. 8, Defensive Performance Metrics API
class DefensivePerformanceMetricsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_defensive_performance_metrics(player)
                    })
                
            print("performance_metrics for coach: ", player_data)
            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_defensive_performance_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)



# card no. 9, Offensive Performance Metrics API
class OffensivePerformanceMetricsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, format=None):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_offensive_performance_metrics(player)
                    })
                
            print("performance_metrics for coach: ", player_data)
            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_offensive_performance_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)


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
        

# greetings api, universal for all cards
class GreetingAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = datetime.today()
        user = request.user
        user_data = {
            "name": request.user.name,
            "wellness": get_status_card_metrics(user),
            "calender": get_daily_snapshot(user, today),
            "performance-metrics": get_performance_metrics(user),
            "defensive-performance-metrics": get_defensive_performance_metrics(user),
            "offensive-performance-metrics": get_offensive_performance_metrics(user),
            "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        print("*" * 100)
        print("user_data: ", user_data)

        prompt = f"Generate a two-liner greeting for the user with the following data. Keep the word count less than 40 and make it crisp and to the point for a athelete. Do not include JSON data. From the data passed, see what should be his main focus for the day.: {user_data}"

        deployment_name = "Completion"
        response = openai_client.completions.create(
                                        model=deployment_name,
                                        prompt=prompt,
                                        max_tokens=50
                                )

        # Extract the greeting from the response
        greeting = response.choices[0].text.strip()

        print("greeting: ", greeting)

        return Response({'greeting': greeting}, status=status.HTTP_200_OK)
    

# ai-insight API, unique for each card
class InsightAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, card):
        try:
            prompt = get_prompt_for_insight(request.user, card)
            print("prompt: ", prompt)

            if prompt == None:
                return Response({ 'error': 'unknown card'}, status=status.HTTP_400_BAD_REQUEST)

            deployment_name = "Completion"
            response = openai_client.completions.create(
                                            model=deployment_name,
                                            prompt=prompt,
                                            max_tokens=50
                                    )

            # Extract the insight from the response
            insight = response.choices[0].text.strip()

            print("insight: ", insight)
            return Response({ 'insight': insight }, status=status.HTTP_200_OK)
        except:
            return Response({ 'error': 'card data not found'}, status=status.HTTP_400_BAD_REQUEST)
        