# views related to cards
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from django.utils.timezone import datetime
from django.utils import timezone
from django.conf import settings


import google.generativeai as genai


from api.serializer import CardSuggestedActionsSerializer
from api.models import CardSuggestedAction, MatchEventsDataFile
from api.utils import *


genai.configure(api_key=settings.WAJO_GOOGLE_GEMINI_API_KEY)
gemini_model = genai.GenerativeModel("gemini-1.5-flash")

# getStatusCardMetric, dummy data for the previous app builds
class StatusCardMetricAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': {}
                    })

            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = {}
            return Response(metrics, status=status.HTTP_200_OK)

# latest, /api/v1/
class StatusCardMetricAPI_v1(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_status_card_metrics(player)
                    })

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




# getCardSuggestedActions, for old builds
class CardSuggestedActionsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, card):
        try:
            actions = CardSuggestedAction.objects.filter(card_name=card).all()
            serializer = CardSuggestedActionsSerializer(actions, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response({ 'error': 'card data not found'}, status=status.HTTP_400_BAD_REQUEST)
        

# getCardSuggestedActions, /api/v1/
class CardSuggestedActionsAPI_v1(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            "Calendar": {
                "actions": [
                {
                    "name": "Add Schedule",
                    "postback": "add_schedule"
                },
                {
                    "name": "Update tomorrow's schedule",
                    "postback": "add_eventsfortomorrow"
                }
                ]
            },
            "Wellness": {
                "actions": [
                {
                    "name": "Update Wellness",
                    "postback": "update_wellness"
                },
                {
                    "name": "Update RPE",
                    "postback": "log_rpe"
                },
                {
                    "name": "How am I doing?",
                    "postback": "get_insights"
                }
                ]
            },
            "Performance Metrics": {
                "actions": [
                {
                    "name": "How am I doing?",
                    "postback": "get_insights"
                }
                ]
            },
            "Defensive Metrics": {
                "actions": [
                {
                    "name": "How am I doing?",
                    "postback": "get_insights"
                }
                ]
            },
            "Offensive Metrics": {
                "actions": [
                {
                    "name": "How am I doing?",
                    "postback": "get_insights"
                }
                ]
            }
        }
        return Response(data, status=status.HTTP_200_OK)
        
        

# greetings api, universal for all cards
class GreetingAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = datetime.today()
        user = request.user

        if user.selected_language == 'he':
            language = "Hebrew"
        else:
            language = "English"
    
        user_data = {
            "name": request.user.name,
            "wellness": get_status_card_metrics(user),
            "calendar": get_daily_snapshot(user, today),
            "performance-metrics": get_performance_metrics(user),
            "defensive-performance-metrics": get_defensive_performance_metrics(user),
            "offensive-performance-metrics": get_offensive_performance_metrics(user),
            "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        print("*" * 100)
        print("user_data for greeting generation: ", user_data)

        prompt = f"""Generate a two-liner greeting only in {language} language for the user with the following data. 
                    Keep the word count around 60 words and make it crisp and to the point for a athelete. Do not include JSON data. 
                    From the data passed, see what should be his main focus for the day.: {user_data}. 
                    {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}
                """

        greeting = gemini_model.generate_content(prompt)

        print("greeting: ", greeting.text)

        return Response({'greeting': greeting.text}, status=status.HTTP_200_OK)
    

# ai-insight API, unique for each card
class InsightAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, card):
        try:
            prompt = get_prompt_for_insight(request.user, card)
            print("prompt: ", prompt)

            if prompt == None:
                return Response({ 'error': 'unknown card'}, status=status.HTTP_400_BAD_REQUEST)

            insight = gemini_model.generate_content(prompt)

            print("insight: ", insight.text)

            return Response({ 'insight': insight.text }, status=status.HTTP_200_OK)
        except:
            return Response({ 'error': 'card data not found'}, status=status.HTTP_400_BAD_REQUEST)


# Video Card API
class VideoAnalysisCardAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # JSON of Category & Sub Category
        return Response({
                "Pass": [
                    "Successful",
                    "Unsuccessful"
                ],
                "Pass Received": [],
                "Clearance": [],
                "Duel": [
                    "Unsuccessful",
                    "Successful"
                ],
                "Recovery": [],
                "Block": [],
                "Intervention": [],
                "Set Piece": [],
                "Foul": [],
                "Foul Won": [],
                "Tackle": [
                    "Unsuccessful",
                    "Successful"
                ],
                "Cross Received": [],
                "Error": [],
                "Shot": [
                    "Off Target",
                    "Blocked",
                    "On Target",
                    "Goal",
                    "Keeper Rush-Out"
                ],
                "Hit": [],
                "Save": [],
                "Interception": [],
                "Ball Received": [],
                "Take-On": [
                    "Unsuccessful",
                    "Successful"
                ],
                "Defensive Line Support": [
                    "Successful"
                ],
                "Aerial Clearance": [
                    "Successful",
                    "Unsuccessful"
                ],
                "Goal Conceded": [],
                "Pause": [],
                "Carry": [],
                "Substitution": [],
                "Offside": []
            }, status.HTTP_200_OK)

    def post(self, request):
        category = request.data.get('category', None)
        sub_category = request.data.get('sub_category', None)

        if not category:
            return Response({'error': 'category is required'}, status.HTTP_400_BAD_REQUEST)
        
        try:
            match_events_data_file = MatchEventsDataFile.objects.latest('updated_on')
        except MatchEventsDataFile.DoesNotExist:
            return Response({ 'error': 'No Match Event data file found'}, status.HTTP_400_BAD_REQUEST)
        
        df = match_events_data_file.get_data()

        if sub_category:
            filtered_df = df[(df['eventType'] == category) & (df['outcome'] == sub_category)]
        else:
            filtered_df = df[(df['eventType'] == category)]
        
        if 'event_time' not in filtered_df.columns:
            return Response({'event_time': []}, status.HTTP_200_OK)
        
        event_times = filtered_df['event_time'].tolist()
        print("Events: ", { 'category': category, 'sub_category': sub_category, 'records': len(event_times)})
        return Response({'event_time': event_times}, status.HTTP_200_OK)


# Game Stats
class GameStatsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_game_stats(player)
                    })

            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_game_stats(request.user)
            return Response(metrics, status=status.HTTP_200_OK)
        
# Season Overview Metrics
class SeasonOverviewMetricsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_season_overview_metrics(player)
                    })

            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_season_overview_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)
        

class WajoPerformanceIndexAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_wajo_performance_index_metrics(player)
                    })

            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_wajo_performance_index_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)


# new APIs for new formulas(new freelancer), 22nd Sept 2024
class AttackingSkillsAPI_v1(APIView): # latest
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            # get team stats
            team_assigned = request.user.coach_team_mappings.first()
            if team_assigned:
                team_stats = team_assigned.team_stats.metrics
            else:
                team_stats = {}

            # get players data
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_attacking_skills_metrics(player)
                    })
                
            data = {
                'team': team_stats['attacking_skills'] if 'attacking_skills' in team_stats.keys() else {},
                'players': player_data
            }

            return Response(data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_attacking_skills_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)

class AttackingSkillsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_attacking_skills_metrics(player)
                    })

            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_attacking_skills_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)
        
# v1
class VideoCardDefensiveAPI_v1(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            # get team stats
            team_assigned = request.user.coach_team_mappings.first()
            if team_assigned:
                team_stats = team_assigned.team_stats.metrics
            else:
                team_stats = {}

            # get players data
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_videocard_defensive_metrics(player)
                    })

            data = {
                'team': team_stats['videocard_defensive'] if 'videocard_defensive' in team_stats.keys() else {},
                'players': player_data
            }

            return Response(data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_videocard_defensive_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)
        

class VideoCardDefensiveAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_videocard_defensive_metrics(player)
                    })

            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_videocard_defensive_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)
        
# v1
class VideoCardDistributionsAPI_v1(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            # get team stats
            team_assigned = request.user.coach_team_mappings.first()
            if team_assigned:
                team_stats = team_assigned.team_stats.metrics
            else:
                team_stats = {}

            # get players data
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_videocard_distributions_metrics(player)
                    })

            data = {
                'team': team_stats['videocard_distributions'] if 'videocard_distributions' in team_stats.keys() else {},
                'players': player_data
            }

            return Response(data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_videocard_distributions_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)


class VideoCardDistributionsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role == 'Coach':
            player_data = []
            for player in request.user.players.all():
                player_data.append({
                        'profile': WajoUserSerializer(player).data,
                        'metrics': get_videocard_distributions_metrics(player)
                    })

            return Response(player_data, status=status.HTTP_200_OK)
        
        else:
            metrics = get_videocard_distributions_metrics(request.user)
            return Response(metrics, status=status.HTTP_200_OK)