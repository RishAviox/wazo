# views related to cards
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import datetime
from django.utils import timezone
from django.utils.dateparse import parse_date

from core.llm_provider import generate_llm_response
from .utils import *
from .models import *
from events.models import MatchEventsDataFile
from accounts.serializer import WajoUserSerializer

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
            # "performance-metrics": get_performance_metrics(user),
            # "defensive-performance-metrics": get_defensive_performance_metrics(user),
            # "offensive-performance-metrics": get_offensive_performance_metrics(user),
            "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        print("*" * 100)
        # print("user_data for greeting generation: ", user_data)

        prompt = f"""Generate a two-liner greeting only in {language} language for the user with the following data. 
                    Keep the word count around 60 words and make it crisp and to the point for a athelete. Do not include JSON data. 
                    From the data passed, see what should be his main focus for the day.: {user_data}. 
                    {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}
                """

        greeting = generate_llm_response(prompt)

        print("greeting: ", greeting)

        return Response({ 'greeting': greeting }, status=status.HTTP_200_OK)
 

# ai-insight API, unique for each card
class InsightAPI(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, card):
        try:
            prompt = get_prompt_for_insight(request.user, card)
            print("prompt: ", prompt)

            if prompt == None:
                return Response({ 'error': 'unknown card'}, status=status.HTTP_400_BAD_REQUEST)

            insight = generate_llm_response(prompt)

            print(f"insight for card -> {card}: ", insight)

            return Response({ 'insight': insight }, status=status.HTTP_200_OK)
        except:
            return Response({ 'error': 'card data not found'}, status=status.HTTP_400_BAD_REQUEST)


# Card Suggested Actions
class CardSuggestedActionsAPI(APIView):
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
                    },
                    {
                        "name": "RPE Insights",
                        "postback": "get_rpe_insights"
                    }
                ]
            },
            "Squad Hub": {
                "actions": [
                    {
                        "name": "Status",
                        "postback": "status"
                    },
                    {
                        "name": "Stats",
                        "postback": "stats"
                    },
                    {
                        "name": "Development",
                        "postback": "development"
                    }
                ]
            },
            "Daily Snapshot": {
                "actions": [
                    {
                        "name": "Daily Snapshot",
                        "postback": "daily-snapshot"
                    }
                ]
            },
            "Match Center": {
                "actions": [
                    {
                        "name": "Pre-Match",
                        "postback": "pre-match"
                    },
                    {
                        "name": "Post-Match",
                        "postback": "post-match"
                    },
                    {
                        "name": "In-Match",
                        "postback": "in-match"
                    }
                ]
            },
            "Development Center": {
                "actions": [
                    {
                        "name": "Team Journey",
                        "postback": "team-journey"
                    },
                    {
                        "name": "Career Journey",
                        "postback": "career-journey"
                    }
                ]
            },
            "Reporting and Analysis": {
                "actions": [
                    {
                        "name": "Player Performance Reporting",
                        "postback": "player-performance-reporting"
                    },
                    {
                        "name": "Team Performance Reporting",
                        "postback": "team-performance-reporting"
                    },
                    {
                        "name": "Post-Match & Tactical Reporting",
                        "postback": "post-match-tactical-reporting"
                    },
                    {
                        "name": "Health & Wellness Reporting",
                        "postback": "health-wellness-reporting"
                    }
                ]
            },
            "Performance & Data Insights": {
                "actions": [
                    {
                        "name": "Advanced Performance Metrics",
                        "postback": "advaced-performance-metrics"
                    },
                    {
                        "name": "Player Data Insights",
                        "postback": "player-data-insights"
                    },
                    {
                        "name": "Team Performance Trends",
                        "postback": "team-performance-trends"
                    },
                    {
                        "name": "Opponent Data Analysis",
                        "postback": "opponent-data-analysis"
                    }
                ]
            }
        }

        return Response(data, status=status.HTTP_200_OK)
 
 
# Base API for common functionalities
class BaseCardAPI(APIView):
    permission_classes = [IsAuthenticated]
    card_model = None
    card_name = ''
    has_team = True # Indicates if the card involves team data
    
    def get_metrics_for_user(self, user, target_date, date_field):
        if target_date:
            filter_kwargs = {f'{date_field}': target_date}
            metrics_entry = (
                            self.card_model.objects.filter(
                                    user=user, 
                                    **filter_kwargs
                            ).first()
            )
        else:
            metrics_entry = (
                            self.card_model.objects.filter(user=user)
                            .order_by(f'-{date_field}')
                            .first()
                        )
        return metrics_entry
    
    def get_available_dates_for_user(self, user, date_field):
        available_dates = (
                    self.card_model.objects.filter(user=user)
                        .values_list(date_field, flat=True)
                        .distinct()
                        .order_by(f'-{date_field}')  # Sort dates in descending order
                    )
        return list(available_dates)
    
    def get_players_data_for_coach(self, players, target_date, date_field):
        players_data = []
        for player in players:
            metrics_entry = self.get_metrics_for_user(player, target_date, date_field)
            available_dates = self.get_available_dates_for_user(player, date_field)
            
            players_data.append(
                {
                    'profile': WajoUserSerializer(player).data,
                    'metrics': metrics_entry.metrics if metrics_entry else {},
                    "available_dates": available_dates
                }
            )
        return players_data
    
    def get_team_stats_for_coach(self, user, target_date):
        # Get all teams the coach is associated with
        teams = user.teams_coached.all()
                
        if not teams.exists():
            print(f"No team associated with this coach ({user})")
            return {}
        else:
            team = teams.first()
            
            # Filter TeamStats for the team, optionally by date
            team_stats_qs = team.team_stats.all()
            if target_date:
                team_stats_qs = team_stats_qs.filter(game__date=target_date)
            else:
                team_stats_qs = team_stats_qs.order_by('-game__date')
            
            team_stats_data = team_stats_qs.first()
            if team_stats_data:
                return team_stats_data.metrics.get(self.card_name, {})
            else:
                return {}
        
    def get(self, request):
        # Parse the date parameter (if provided)
        date_str = request.query_params.get('date')
        target_date = parse_date(date_str) if date_str else None
        date_field = 'game__date' if self.has_team else 'created_on__date'
        
        # get user
        user = request.user
        
        if user.role == 'Coach':
            if self.has_team:
                team_stats = self.get_team_stats_for_coach(
                                            user=user, 
                                            target_date=target_date
                                        )
                players_data = self.get_players_data_for_coach(
                                            players=user.players.all(),
                                            target_date=target_date,
                                            date_field=date_field
                                        )
                return Response({'team': team_stats, 'players': players_data}, status=status.HTTP_200_OK)
            else:
                players_data = self.get_players_data_for_coach(
                                            players=user.players.all(),
                                            target_date=target_date,
                                            date_field=date_field
                                        )
                return Response(players_data, status=status.HTTP_200_OK)
        else:
            metrics_entry = self.get_metrics_for_user(
                                        user=user,
                                        target_date=target_date,
                                        date_field=date_field
                                    )
            available_dates = self.get_available_dates_for_user(
                                        user=user,
                                        date_field=date_field
                                    )
            
            response_data = {
                "metrics": metrics_entry.metrics if metrics_entry else {},
                "available_dates": available_dates
            }
                        
            return Response(response_data, status=status.HTTP_200_OK)
        
   
# card: 1 --> Daily Snapshot
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


# card: 2 --> Status Card Metrics (Player Overview)
class StatusCardMetricAPI(BaseCardAPI):
    card_model = StatusCardMetrics
    has_team = False
   
        
# card: 2.1 --> RPE Metrics (Player Overview)
class RPEMetricAPI(BaseCardAPI):
    card_model = RPEMetrics
    has_team = False
        
        
# card: 3 --> Attacking Skills
class AttackingSkillsAPI(BaseCardAPI):
    card_model = AttackingSkills
    card_name = "attacking_skills"
    

# card: 4 --> VideoCard Defensive (Defensive)
class VideoCardDefensiveAPI(BaseCardAPI):
    card_model = VideoCardDefensive
    card_name = "videocard_defensive"
        

# card: 5 --> VideoCard Distribution (Distribution)
class VideoCardDistributionsAPI(BaseCardAPI):
    card_model = VideoCardDistributions
    card_name = "videocard_distributions"


# card: 6 --> GPS Athletic Skills (Athletic Skills)
class GPSAthleticSkillsAPI(BaseCardAPI):
    card_model = GPSAthleticSkills
    card_name = "gps_athletic_skills"


# card: 7 --> GPS Football Abilities (Football Skills)
class GPSFootballAbilitiesAPI(BaseCardAPI):
    card_model = GPSFootballAbilities
    card_name = "gps_football_abilities"

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

