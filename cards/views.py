# views related to cards
import logging
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import datetime
from django.utils import timezone
from django.utils.dateparse import parse_date
import random
from datetime import timedelta, timezone
import pytz

from core.llm_provider import generate_llm_response
from .utils import *
from .models import *
from .serializers import TrainingCardDataSerializer, NewsCardDataSerializer
from events.models import MatchEventsDataFile
from accounts.serializer import WajoUserSerializer
from games.models import GameMetaData

logger = logging.getLogger(__name__)

# Fake insights for News Card
NEWS_CARD_INSIGHTS = [
    "Learn from the best! Watching the pros in action can sharpen your skills and elevate your game.",
    "See how the champions play—every match is a lesson waiting to be learned.",
    "Get inspired! Watching your favorite sport can show you strategies you never knew existed.",
    "From technique to teamwork, every game you watch is a masterclass in action.",
    "They play, you learn—witness greatness and take your game to the next level.",
    "Stay in the loop! Watching sports is the quickest way to catch trends and tricks in your game.",
    "Experience the thrill and pick up tips to dominate your own field!",
    "Discover what makes the best players tick—watch and learn from the action.",
    "From strategy to skills, there’s a lot to absorb when you tune into the pros.",
    "Great athletes were once great watchers—start your journey to mastery by watching today!"
]

# greetings api, universal for all cards
class GreetingAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            
            greeting_cache_qs = GreetingCache.objects.filter(user=user).order_by('-updated_on') 
            latest_greeting_obj = greeting_cache_qs.first()
            
            if latest_greeting_obj:
                greeting = latest_greeting_obj.text
                logger.info(f"[Cached] greeting for user {user.id}: {greeting}")
                return Response({ 'greeting': greeting }, status=status.HTTP_200_OK)
     
            
            today = datetime.today()

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
            logger.info(f"Generating greeting for user {user.id} with language: {language}")
            print(f"Generating greeting for user {user.id} with language: {language}")
            # logger.debug("user_data for greeting generation: %s", user_data)

            israel_tz = pytz.timezone('Asia/Jerusalem')
            utc_time = datetime.now(pytz.utc)
            israel_local_time = utc_time.astimezone(israel_tz)

            prompt = f"""Generate a two-liner greeting only in {language} language for the user with the following data. 
                        Keep the word count around 60 words and make it crisp and to the point for a athelete. Do not include JSON data. 
                        From the data passed, see what should be his main focus for the day.: {user_data}. 
                        {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}
                        Current Date and time: {israel_local_time}
                    """

            greeting = generate_llm_response(prompt)
            
            # store in db
            GreetingCache.objects.create(user=user, text=greeting)

            logger.info(f"[Generated] New Greeting for user {user.id}: {greeting}")
            print(f"[Generated] New Greeting for user {user.id}: {greeting}")

            return Response({ 'greeting': greeting }, status=status.HTTP_200_OK)
        
        except Exception as e:
            print(f"Error while processing greeting request for user {request.user.id}: {str(e)}")
            logger.error(
                f"Error while processing greeting request for user {request.user.id}: {str(e)}", stack_info=True)
            return Response({
                "error": "Internal server error",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
 

# ai-insight API, unique for each card
class InsightAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, card=None):
        try:
            user = request.user
            if card == "all":
                all_card_names = ["StatusCard", "DailySnapshot", "AttackingSkills", "VideocardDefensive",
                                  "VideocardDistribution", "AthleticSkills", "FootballAbilities",
                                  "VideoCard", "TrainingCard", "NewsCard"]
                cached_insights = InsightCache.objects.filter(
                    user=user,
                    card__in=all_card_names
                ).order_by('-updated_on')
                
                cached_insights_dict = {}
                for insight in cached_insights:
                    if insight.card not in cached_insights_dict:
                        cached_insights_dict[insight.card] = insight.text
                        
                all_insights = {}
                                
                for card_name in all_card_names:
                    if card_name in cached_insights_dict:
                        all_insights[card_name] = cached_insights_dict[card_name]
                    else:
                        if card_name == 'NewsCard':
                            all_insights[card_name] = random.choice(NEWS_CARD_INSIGHTS)
                        else:
                            prompt = get_prompt_for_insight(user, card_name)
                            if prompt is None:
                                all_insights[card_name] = 'unknown card'
                                continue
                            insight = generate_llm_response(prompt)
                            InsightCache.objects.create(user=user, card=card_name, text=insight)
                            all_insights[card_name] = insight
                            print(f"[Generated and Cached] Insight for card '{card_name}':", insight)

                print(f"[Final Insights] All insights for user '{user}':", all_insights)
                return Response(all_insights, status=status.HTTP_200_OK)

            if card == 'NewsCard':
                return Response({ 'insight': random.choice(NEWS_CARD_INSIGHTS) }, status=status.HTTP_200_OK)
            
            insight_cache_obj = InsightCache.objects.filter(
                    user=user,
                    card=card,
                ).order_by('-updated_on').first()
            
            if insight_cache_obj:
                insight = insight_cache_obj.text
                print(f"[Cached] Insight for card '{card}':", insight)
                return Response({'insight': insight}, status=status.HTTP_200_OK)

            prompt = get_prompt_for_insight(user, card)
            print("prompt: ", prompt)

            if prompt == None:
                return Response({ 'error': 'unknown card'}, status=status.HTTP_400_BAD_REQUEST)

            insight = generate_llm_response(prompt)
            
            # Store the newly generated insight in the cache
            InsightCache.objects.create(user=user, card=card, text=insight)

            print(f"[Generated] New insight for card '{card}':", insight)

            return Response({ 'insight': insight }, status=status.HTTP_200_OK)
        except:
            return Response({ 'error': 'card data not found'}, status=status.HTTP_400_BAD_REQUEST)


# Card Suggested Actions
class CardSuggestedActionsAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.selected_language == 'he':
            data = {
                    "Calendar": {
                        "actions": [
                            {
                                "name": "הוסף או עדכן את לוח הזמנים",
                                "postback": "add_schedule"
                            },
                            # {
                            #     "name": "עדכן את לוח הזמנים למחר",
                            #     "postback": "add_eventsfortomorrow"
                            # }
                        ]
                    },
                    "Wellness": {
                        "actions": [
                            {
                                "name": "עדכן רווחה",
                                "postback": "update_wellness"
                            },
                            {
                                "name": "RPE עדכן",
                                "postback": "log_rpe"
                            },
                            {
                                "name": "קבל תובנות",
                                "postback": "get_insights"
                            },
                            # {
                            #     "name": "RPE תובנות",
                            #     "postback": "get_rpe_insights"
                            # }
                        ]
                    },
                    "Squad Hub": {
                        "actions": [
                            {
                                "name": "הוסף ניתוח התאמה לאחר",
                                "postback": "post_match_analysis"
                            }
                        ]
                    },
                    "Wajo Intelligence": {
                        "actions": [
                            {
                                "name": "מודיעין פוסט-משחק",
                                "postback": "post_match_intelligence"
                            }
                        ]
                    },
                    "Locker Room": {
                        "actions": [
                            {
                                "name": "סטטוס",
                                "postback": "status"
                            },
                            {
                                "name": "סטטיסטיקות",
                                "postback": "stats"
                            },
                            {
                                "name": "התפתחות",
                                "postback": "development"
                            }
                        ]
                    },
                    "Daily Snapshot": {
                        "actions": [
                            {
                                "name": "תמונת מצב יומית",
                                "postback": "daily-snapshot"
                            }
                        ]
                    },
                    "Match Center": {
                        "actions": [
                            {
                                "name": "לפני המשחק",
                                "postback": "pre-match"
                            },
                            {
                                "name": "אחרי המשחק",
                                "postback": "post-match"
                            },
                            {
                                "name": "במהלך המשחק",
                                "postback": "in-match"
                            }
                        ]
                    },
                    "Development Center": {
                        "actions": [
                            {
                                "name": "מעקב התפתחות קבוצתי",
                                "postback": "team-journey"
                            },
                            {
                                "name": "מעקב התפתחות אישי",
                                "postback": "career-journey"
                            }
                        ]
                    },
                    "Reporting and Analysis": {
                        "actions": [
                            {
                                "name": "דיווח ביצועי שחקן",
                                "postback": "player-performance-reporting"
                            },
                            {
                                "name": "דיווח ביצועי קבוצה",
                                "postback": "team-performance-reporting"
                            },
                            {
                                "name": "דיווח אחרי המשחק וניתוח טקטי",
                                "postback": "post-match-tactical-reporting"
                            },
                            {
                                "name": "דיווח על בריאות ורווחה",
                                "postback": "health-wellness-reporting"
                            }
                        ]
                    },
                    "Performance & Data Insights": {
                        "actions": [
                            {
                                "name": "מדדים מתקדמים לביצועים",
                                "postback": "advaced-performance-metrics"
                            },
                            {
                                "name": "תובנות נתונים של שחקן",
                                "postback": "player-data-insights"
                            },
                            {
                                "name": "מגמות ביצועי קבוצה",
                                "postback": "team-performance-trends"
                            },
                            {
                                "name": "ניתוח נתוני יריב",
                                "postback": "opponent-data-analysis"
                            }
                        ]
                    }
                }
        else:
            data = {
                "Calendar": {
                    "actions": [
                        {
                            "name": "Add or Update Schedule",
                            "postback": "add_schedule"
                        },
                        # {
                        #     "name": "Update tomorrow's schedule",
                        #     "postback": "add_eventsfortomorrow"
                        # }
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
                        # {
                        #     "name": "RPE Insights",
                        #     "postback": "get_rpe_insights"
                        # }
                    ]
                },
                "Squad Hub": {
                    "actions": [
                        {
                            "name": "Add Post Match Analysis",
                            "postback": "post_match_analysis"
                        }
                    ]
                },
                "Wajo Intelligence": {
                    "actions": [
                        {
                            "name": "Postmatch Intelligence",
                            "postback": "post_match_intelligence"
                        }
                    ]
                },
                "Locker Room": {
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
        if user.selected_language == 'he' and metrics_entry:
            entries = metrics_entry.metrics
            translate_units_en_to_he(entries)

        return metrics_entry
    
    def get_available_dates_for_user(self, user, date_field):
        available_dates = (
                    self.card_model.objects.filter(user=user)
                        .values_list(date_field, flat=True)
                        .distinct()
                        .order_by(f'-{date_field}')  # Sort dates in descending order
                    )
        return list(available_dates)
    
    def get_extra_profile_metrics(self, user, target_date, date_field):
        # Get latest wellness and RPE scores, with proper fallbacks
        wellness_score = ""
        rpe_score = ""
        try:
            wellness_score_qs = StatusCardMetrics.objects.filter(user=user).latest("created_on")
            wellness_score = wellness_score_qs.metrics.get("Overall Wellness", "")
        except StatusCardMetrics.DoesNotExist:
            wellness_score = ""

        try:
            rpe_score_qs = RPEMetrics.objects.filter(user=user).latest("created_on")
            rpe_score = rpe_score_qs.metrics.get("Readiness", "")  # Readiness for now
        except RPEMetrics.DoesNotExist:
            rpe_score = ""

        # Athletic skills and distribution with optional date filtering
        athletic_skills_qs = GPSAthleticSkills.objects.filter(user=user)
        distribution_qs = VideoCardDistributions.objects.filter(user=user)

        if target_date:
            filter_kwargs = {f"{date_field}": target_date}
            athletic_skills_qs = athletic_skills_qs.filter(**filter_kwargs).order_by(date_field)
            distribution_qs = distribution_qs.filter(**filter_kwargs).order_by(date_field)

        # Safely get the first result and its metrics, with fallbacks
        athletic_skills = (
            athletic_skills_qs.first().metrics.get("Athletic Skills", "")
            if athletic_skills_qs.exists() and athletic_skills_qs.first() else ""
        )

        distribution = (
            distribution_qs.first().metrics.get("Game Rating", "")
            if distribution_qs.exists() and distribution_qs.first() else ""
        )

        # Return the results as a dictionary
        return {
            "wellness_score": wellness_score,
            "rpe_score": rpe_score,
            "athletics_score": athletic_skills,
            "distribution_score": distribution
        }
            
    
    def get_players_data_for_coach(self, players, target_date, date_field):
        players_data = []
        for player in players:
            metrics_entry = self.get_metrics_for_user(player, target_date, date_field)
            available_dates = self.get_available_dates_for_user(player, date_field)
            extra_metrics = self.get_extra_profile_metrics(player, target_date, date_field)
            
            players_data.append(
                {
                    'profile': { **WajoUserSerializer(player).data, **extra_metrics },
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
class StatusCardMetricAPI(APIView):
    permission_classes = [IsAuthenticated]
    
    def get_8_day_average_metrics(self, user):
        # Set today to 12:00 AM
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)  
        start_date = today - timedelta(days=7)
        
        # fetch metrics for the past 8 days
        metrics_qs = StatusCardMetrics.objects.filter(
            user=user, 
            updated_on__date__range=(start_date, today)
        )
        
        if not metrics_qs.exists():
            print(f"No status card metrics found for the past 8 days for user {user}.")
            return {
                'Energy Level': '0.0',
                'Muscle Soreness': '0.0',
                'Pain Level': '0.0',
                'Mood': '0.0',
                'Stress Level': '0.0',
                'Sleep Quality': '0.0',
                'Diet Quality': '0.0',
                'Overall Wellness': '0.0'
            }
        
        # Initialize sums for metrics
        metrics_sum = {
            'Energy Level': 0.0,
            'Muscle Soreness': 0.0,
            'Pain Level': 0.0,
            'Mood': 0.0,
            'Stress Level': 0.0,
            'Sleep Quality': 0.0,
            'Diet Quality': 0.0,
            'Overall Wellness': 0.0
        }
        count = 0
        
        # Aggregate metrics
        for entry in metrics_qs:
            try:
                metrics = entry.metrics  # Assuming metrics is a dictionary
                for key in metrics_sum.keys():
                    metrics_sum[key] += float(metrics.get(key, 0.0))
                count += 1
            except Exception as e:
                print(f"Error processing status card metrics for entry {entry.id}: {e}")

        if count == 0:
            return {
                'Energy Level': '0.0',
                'Muscle Soreness': '0.0',
                'Pain Level': '0.0',
                'Mood': '0.0',
                'Stress Level': '0.0',
                'Sleep Quality': '0.0',
                'Diet Quality': '0.0',
                'Overall Wellness': '0.0'
            }
        
        # Calculate averages
        metrics_average = {key: str(round(value / count, 2)) for key, value in metrics_sum.items()}
        print(f"Calculated 8-day average status card metrics for user {user}: {metrics_average}")
        return metrics_average
    
    
    def get(self, request):
        # Get the authenticated user
        user = request.user

        # Calculate the 8-day average metrics
        metrics_average = self.get_8_day_average_metrics(user)

        if not metrics_average:
            return Response(
                {"error": "No status card metrics available for the past 8 days."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Serve the 8-day average metrics
        return Response(metrics_average, status=status.HTTP_200_OK)
   
        
# card: 2.1 --> RPE Metrics (Player Overview)
class RPEMetricAPI(BaseCardAPI):
    permission_classes = [IsAuthenticated]

    def get_8_day_average_metrics(self, user):
        # Set today to 12:00 AM
        today = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = today - timedelta(days=7)

        # Fetch metrics for the past 8 days
        metrics_qs = RPEMetrics.objects.filter(
            user=user,
            updated_on__date__range=(start_date, today)
        )

        if not metrics_qs.exists():
            print(f"No rpe metrics found for the past 8 days for user {user}.")
            return {
                'Intensity': '0.0',
                'Fatigue': '0.0',
                'Recovery': '0.0',
                'Readiness': '0.0'
            }

        # Initialize sums for rpe metrics
        rpe_metrics_sum = {
            'Intensity': 0.0,
            'Fatigue': 0.0,
            'Recovery': 0.0,
            'Readiness': 0.0
        }
        count = 0

        # Aggregate metrics
        for entry in metrics_qs:
            try:
                metrics = entry.metrics  # Assuming metrics is a dictionary
                for key in rpe_metrics_sum.keys():
                    rpe_metrics_sum[key] += float(metrics.get(key, 0.0))
                count += 1
            except Exception as e:
                print(f"Error processing rpe metrics for entry {entry.id}: {e}")

        if count == 0:
            return {key: '0.0' for key in rpe_metrics_sum.keys()}

        # Calculate averages
        rpe_metrics_average = {
            key: str(round(value / count, 2)) for key, value in rpe_metrics_sum.items()
        }
        print(f"Calculated 8-day average rpe metrics for user {user}: {rpe_metrics_average}")
        return rpe_metrics_average

    def get(self, request):
        # Get the authenticated user
        user = request.user

        # Calculate the 8-day average rpe metrics
        metrics_average = self.get_8_day_average_metrics(user)

        if not metrics_average:
            return Response(
                {"error": "No rpe metrics available for the past 8 days."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Serve the 8-day average rpe metrics
        return Response(metrics_average, status=status.HTTP_200_OK)
        
        
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


# Video Card JSON API ---> Deprecated
class VideoCardJSONAPI_Deprecated(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        try:
            # Retrieve the latest GameMetaData by creation time
            latest_metadata = GameMetaData.objects.latest('created_on')
        except GameMetaData.DoesNotExist:
            return Response({"error": "No GameMetaData found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Return the data field from the latest GameMetaData record
        return Response(latest_metadata.data, status=status.HTTP_200_OK)
        
# Video Card JSON API ---> V1
class VideoCardJSONAPI(APIView):
    permission_classes = [IsAuthenticated]

    def get_available_dates(self):
        """
        Gather all distinct dates found in GameMetaData.game.date, sorted descending.
        """
        return list(
            GameMetaData.objects
            .exclude(game__date__isnull=True)
            .values_list('game__date', flat=True)
            .distinct()
            .order_by('-game__date')
        )

    def get(self, request, *args, **kwargs):
        # Parse optional 'date' parameter
        date_str = request.query_params.get('date')
        target_date = parse_date(date_str) if date_str else None

        # Filter by target_date if provided, else get all
        if target_date:
            queryset = GameMetaData.objects.filter(game__date=target_date)
        else:
            queryset = GameMetaData.objects.all()

        # Order by the creation time, newest first
        queryset = queryset.order_by('-created_on')

        # Pick the newest item
        latest_metadata = queryset.first()
        if not latest_metadata:
            return Response(
                {
                    "data": {},
                    "available_dates": self.get_available_dates()
                },
                status=status.HTTP_200_OK
            )

        response_data = {
            "data": latest_metadata.data,
            "available_dates": self.get_available_dates()
        }
        return Response(response_data, status=status.HTTP_200_OK)
    
    
# Training Card JSON data API
class TrainingCardJSONAPI(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TrainingCardDataSerializer
    
    def get_queryset(self):
        user_language = getattr(self.request.user, "selected_language", "en")
        return TrainingCardData.objects.filter(language=user_language)
    
    
# News Card JSON data API
class NewsCardJSONAPI(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = NewsCardDataSerializer
    
    def get_queryset(self):
        user_language = getattr(self.request.user, "selected_language", "en")
        return NewsCardData.objects.filter(language=user_language)