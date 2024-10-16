from django.utils.timezone import timedelta
from django.utils import timezone
from django.db.models import Sum, FloatField, ExpressionWrapper
from django.db.models.functions import Cast, Coalesce
from django.db.models.fields.json import KeyTextTransform
from django.utils.timezone import datetime


from api.models import *
from api.serializer import StatusCardMetricsSerializer, WajoUserSerializer
from .status_metrics_calculations import *


# for status card
def get_status_card_metrics(user):
    try:
        metrics = StatusCardMetrics.objects.filter(user=user).latest('updated_on')
        return metrics.metrics
    
    except:
        return {}
    
# for game stats
def get_game_stats(user):
    try:
        metrics = GameStats.objects.filter(user=user).latest('updated_on')
        return metrics.metrics
    except:
        return {}
    
# for season overview metrics
def get_season_overview_metrics(user):
    try:
        metrics = SeasonOverviewMetrics.objects.filter(user=user).latest('updated_on')
        return metrics.metrics
    except:
        return {}
    

# for status card
def get_wajo_performance_index_metrics(user):
    try:
        metrics = WajoPerformanceIndex.objects.filter(user=user).latest('updated_on')
        return metrics.metrics
    
    except:
        return {}
    

# for attacking skills
def get_attacking_skills_metrics(user):
    try:
        metrics = AttackingSkills.objects.filter(user=user).latest('updated_on')
        return metrics.metrics
    
    except:
        return {}
    

# for video card Defensive skills
def get_videocard_defensive_metrics(user):
    try:
        metrics = VideoCardDefensive.objects.filter(user=user).latest('updated_on')
        return metrics.metrics
    
    except:
        return {}
    

# for video card distributions skills
def get_videocard_distributions_metrics(user):
    try:
        metrics = VideoCardDistributions.objects.filter(user=user).latest('updated_on')
        return metrics.metrics
    
    except:
        return {}
    

# for daily snapshot
def get_events_for_next_5_days(user, start_date):
    next_5_days = start_date + timedelta(days=5)

    # Convert start_date and next_5_days to timezone-aware datetime objects (if they are not already)
    if timezone.is_naive(start_date):
        start_date = timezone.make_aware(start_date, timezone.get_current_timezone())
    if timezone.is_naive(next_5_days):
        next_5_days = timezone.make_aware(next_5_days, timezone.get_current_timezone())

    # get one time events
    one_time_events = OneTimeEvents.objects.filter(user=user, date__range=(start_date, next_5_days))
    
    # get recurring events
    recurring_events = []
    for event in RecurringEvents.objects.filter(user=user).all():
        # if event.date <= next_5_days and (event.end_date is None or event.end_date >= start_date):
        if timezone.localtime(event.date) <= next_5_days:
            recurrence_dates = calculate_recurrence_dates(event, start_date, next_5_days)
            for recurrence_date in recurrence_dates:
                recurring_events.append({
                    'event_type': event.event_type,
                    'event': event.event,
                    'date': recurrence_date,
                    'source': event.source
                })

    return one_time_events, recurring_events


def get_events_for_date(user, event_date):
    # Ensure event_date is timezone-aware
    if timezone.is_naive(event_date):
        event_date = timezone.make_aware(event_date, timezone.get_current_timezone())

    # Get one-time events
    one_time_events = OneTimeEvents.objects.filter(user=user, date__date=event_date.date())

    # Get recurring events
    recurring_events = []

    # Set end_date to the last minute of the day
    end_date = event_date.replace(hour=23, minute=59, second=59, microsecond=999999)

    for event in RecurringEvents.objects.filter(user=user):
        recurrence_dates = calculate_recurrence_dates(event, event_date, end_date)
        for recurrence_date in recurrence_dates:
            if recurrence_date.date() == event_date.date():
                recurring_events.append({
                    'event_type': event.event_type,
                    'event': event.event,
                    'date': recurrence_date,
                    'source': event.source
                })

    return one_time_events, recurring_events


def calculate_recurrence_dates(event, start_date, end_date):
    dates = []
    current_date = timezone.localtime(event.date)

    if event.frequency == 'Daily':
        while current_date <= end_date:
            if current_date >= start_date:
                dates.append(current_date)
            current_date += timedelta(days=1)
    
    elif event.frequency == 'Weekly':
        while current_date <= end_date:
            if current_date >= start_date:
                dates.append(current_date)
            current_date += timedelta(weeks=1)
    
    elif event.frequency == 'Monthly':
        while current_date <= end_date:
            if current_date >= start_date:
                dates.append(current_date)
            current_date += timedelta(days=30)  # Simple monthly increment, adjust as needed
    
    elif event.frequency == 'Yearly':
        while current_date <= end_date:
            if current_date >= start_date:
                dates.append(current_date)
            current_date += timedelta(days=365)  # Simple monthly increment, adjust as needed

    return dates


def get_daily_snapshot(user, event_date):
    one_time_events, recurring_events = get_events_for_date(user=user, event_date=event_date)

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

    return combined_events

"""For 5 days events"""
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

""" End """

def get_age_adjustment_factor(dob):
    if not dob:
        return 1.0
    current_date = datetime.today()
    age = current_date.year - dob.year - ((current_date.month, current_date.day) < (dob.month, dob.day))
    if age <= 14:
        return 1.05
    elif age >= 15 and age <= 17:
        return 1.02
    elif age >= 18 and age <= 24:
        return 1.0
    elif age >= 25 and age <= 29:
        return 0.98
    elif age >= 30 and age <= 34:
        return 0.95
    elif age >= 35 and age <= 39:
        return 0.92
    elif age >= 40:
        return 0.88

# for wellness signal
def calculate_and_store_status_card_metrics(user):
    # Fetch the latest wellness response within the specified date range
    latest_wellness_response = DailyWellnessUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on').first().response

    # Fetch the latest RPE response within the specified date range
    latest_rpe_response = RPEUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on').first().response

    age_adjustment_factor = get_age_adjustment_factor(user.dob)
    print("age_adjustment_factor: ", age_adjustment_factor)
    normalized_wellness_response = normalize_wellness_response(latest_wellness_response)
    normalized_rpe_response = normalize_rpe_response(latest_rpe_response)
    
    Wellness =  calculate_wellness_score(normalized_wellness_response, age_adjustment_factor)
    Readiness =  calculate_readiness_score(normalized_rpe_response, age_adjustment_factor)
    Fitness =  calculate_fitness_score(
                                normalized_rpe_response,
                                normalized_wellness_response, 
                                distance_covered = 1, 
                                high_intensity_runs = 1,
                                age_adjustment_factor=age_adjustment_factor)
    Morale =  calculate_morale_score(normalized_wellness_response, age_adjustment_factor)
    # RPE =  calculate_normalized_rpe_score(normalized_rpe_response)
    # sRPE =  calculate_normalized_srpe_score(rpe_score=RPE)
    SPI =  calculate_spi_score(normalized_rpe_response, age_adjustment_factor)
    Recover =  calculate_recovery_score(normalized_rpe_response, normalized_wellness_response, age_adjustment_factor)

    metrics = {
        'Status': calculate_overall_status(Wellness, Readiness, SPI, Recover),
        'Wellness': round(Wellness, 2),
        'Readiness': round(Readiness, 2),
        'Fitness': round(Fitness, 2),
        'Morale': round(Morale, 2),
        # 'RPE': RPE,
        # 'sRPE': sRPE,
        'SPI': round(SPI, 2),
        'Recover': round(Recover, 2)
    }
    print(metrics)
    
    StatusCardMetrics.objects.create(
        user=user,
        metrics=metrics
    )


# for MatchEventDataFile processing Signal
def calculate_game_stats(row):
    return {
            "Overall Game Score": round(row.get('rating', 0), 2),
            "Minutes Played": round(row.get('play_time', 0) / (60 * 1000), 2), # mili seconds to minutes
            "Successful Crosses": round(row.get('cross_succeeded', 0), 2),
            "Key Passes": round(row.get('key_pass', 0), 2),
            "Pass Accuracy": round(100 * row.get('cross_succeeded', 0) / row.get('pass', 0), 2) if row.get('pass', 0) > 0 else 0.0,
            "Total Shots": round(row.get('total_shot', 0), 2),
            "Shots on Target": round(row.get('shot_on_target', 0), 2),
            "Clearances": round(row.get('clearance', 0), 2),
            "Tackles": round(row.get('tackle', 0), 2),
            "Interceptions": round(row.get('intercept', 0), 2),
            "Duels Won": round(100 * (row.get('ground_duel_succeeded', 0) + row.get('aerial_duel_succeeded', 0)) / (row.get('ground_duel', 0) + row.get('aerial_duel', 0)), 2) if (row.get('ground_duel', 0) + row.get('aerial_duel', 0)) > 0 else 0.0,
            "Aerial Duels Won": round(row.get('aerial_duel_succeeded', 0), 2),
            "Distance Covered": round(row.get('distance_covered', 0), 2), # get from GPS data
            "Saves": round(row.get('save_by_catching', 0) + row.get('save_by_punching', 0), 2),
            "% Save": round(100 * (row.get('save_by_catching', 0) + row.get('save_by_punching', 0)) / (row.get('save_by_catching', 0) + row.get('save_by_punching', 0) + row.get('goal_conceded', 0)), 2) if (row.get('save_by_catching', 0) + row.get('save_by_punching', 0) + row.get('goal_conceded', 0)) > 0 else 0.0,
        }

def calculate_season_overview_metrics(row):
    return {
            "Overall Score": float(round(row.get('rating', 0.0), 2)),
            "Matches Played": float(round(row.get('play_time', 0.0) / (90 * 60 * 1000), 2)),
            "Goals": float(round(row.get('goal', 0.0), 2)),
            "Assists": float(round(row.get('assist', 0.0), 2)),
            "Own Goals": float(round(row.get('own_goal', 0.0), 2)),
            "Goals Conceded": float(round(row.get('goal_conceded', 0.0), 2)),
            "Clean Sheets": 1.0 if row.get('goal_conceded') == 0 else 0.0,
            "Yellow Cards": float(round(row.get('yellow_card', 0.0), 2)),
            "Red Cards": float(round(row.get('red_card', 0.0), 2)),
            "Substituted In": 1.0 if row.get('play_time', 0.0) / (60 * 1000) < 90 else 0.0,
            "Substituted Out": 1.0 if row.get('play_time', 0.0) / (60 * 1000) < 90 else 0.0,
        }

def calculate_performance_metrics(row):
    return {
            "rating": {"skill": "Rating", "category": "Performance Metrics", "value": float(row.get('rating', 0.0))},
            "play_time": {"skill": "Play Time", "category": "Performance Metrics", "value": float(row.get('play_time', 0.0))},
            "goal": {"skill": "Goals", "category": "Performance Metrics", "value": float(row.get('goal', 0.0))},
            "assist": {"skill": "Assists", "category": "Performance Metrics", "value": float(row.get('assist', 0.0))},
            "shot_on_target": {"skill": "Shooting", "category": "Performance Metrics", "value": float(row.get('shot_on_target', 0.0))},
            "pass_succeeded": {"skill": "Passing", "category": "Performance Metrics", "value": float(row.get('pass_succeeded', 0.0))},
            "yellow_card": {"skill": "Disciplinary", "category": "Performance Metrics", "value": float(row.get('yellow_card', 0.0))},
            "red_card": {"skill": "Disciplinary", "category": "Performance Metrics", "value": float(row.get('red_card', 0.0))},
            "total_shot": {"skill": "Total Shot", "category": "Performance Metrics", "value": float(row.get('total_shot', 0.0))},
            "pass": {"skill": "Pass", "category": "Performance Metrics", "value": float(row.get('pass', 0.0))},
            "take_on_succeeded": {"skill": "Take On Succeeded", "category": "Performance Metrics", "value": float(row.get('take_on_succeeded', 0.0))},
            "take_on": {"skill": "Take On", "category": "Performance Metrics", "value": float(row.get('take_on', 0.0))},
            "forward_pass_succeeded": {"skill": "Forward Pass Succeeded", "category": "Performance Metrics", "value": float(row.get('forward_pass_succeeded', 0.0))},
            "forward_pass": {"skill": "Forward Pass", "category": "Performance Metrics", "value": float(row.get('forward_pass', 0.0))},
            "final_third_area_pass_succeeded": {"skill": "Final Third Area Pass Succeeded", "category": "Performance Metrics", "value": float(row.get('final_third_area_pass_succeeded', 0.0))},
            "final_third_area_pass": {"skill": "Final Third Area Pass", "category": "Performance Metrics", "value": float(row.get('final_third_area_pass', 0.0))},
        }

def calculate_defensive_performance_metrics(row):
    return {
            "play_time": {"skill": "Play Time", "category": "Performance Metrics", "value": float(row.get('play_time', 0.0))},
            "aerial_clearance": {"skill": "Clearances", "category": "Defensive Skills", "value": float(row.get('aerial_clearance', 0.0))},
            "aerial_clearance_failed": {"skill": "Clearances", "category": "Defensive Skills", "value": float(row.get('aerial_clearance_failed', 0.0))},
            "aerial_clearance_succeeded": {"skill": "Clearances", "category": "Defensive Skills", "value": float(row.get('aerial_clearance_succeeded', 0.0))},
            "clearance": {"skill": "Clearances", "category": "Defensive Skills", "value": float(row.get('clearance', 0.0))},
            "block": {"skill": "Clearances", "category": "Defensive Skills", "value": float(row.get('block', 0.0))},
            "intercept": {"skill": "Interceptions", "category": "Defensive Skills", "value": float(row.get('intercept', 0.0))},
            "intervention": {"skill": "Interceptions", "category": "Defensive Skills", "value": float(row.get('intervention', 0.0))},
            "tackle": {"skill": "Tackling", "category": "Defensive Skills", "value": float(row.get('tackle', 0.0))},
            "tackle_succeeded": {"skill": "Tackling", "category": "Defensive Skills", "value": float(row.get('tackle_succeeded', 0.0))},
            "foul": {"skill": "Tackling", "category": "Defensive Skills", "value": float(row.get('foul', 0.0))},
            "foul_won": {"skill": "Tackling", "category": "Defensive Skills", "value": float(row.get('foul_won', 0.0))},
            "aerial_duel": {"skill": "Duels", "category": "Defensive Skills", "value": float(row.get('aerial_duel', 0.0))},
            "aerial_duel_failed": {"skill": "Duels", "category": "Defensive Skills", "value": float(row.get('aerial_duel_failed', 0.0))},
            "aerial_duel_succeeded": {"skill": "Duels", "category": "Defensive Skills", "value": float(row.get('aerial_duel_succeeded', 0.0))},
            "ground_duel": {"skill": "Duels", "category": "Defensive Skills", "value": float(row.get('ground_duel', 0.0))},
            "ground_duel_failed": {"skill": "Duels", "category": "Defensive Skills", "value": float(row.get('ground_duel_failed', 0.0))},
            "ground_duel_succeeded": {"skill": "Duels", "category": "Defensive Skills", "value": float(row.get('ground_duel_succeeded', 0.0))},
            "loose_ball_duel": {"skill": "Duels", "category": "Defensive Skills", "value": float(row.get('loose_ball_duel', 0.0))},
            "loose_ball_duel_failed": {"skill": "Duels", "category": "Defensive Skills", "value": float(row.get('loose_ball_duel_failed', 0.0))},
            "loose_ball_duel_succeeded": {"skill": "Duels", "category": "Defensive Skills", "value": float(row.get('loose_ball_duel_succeeded', 0.0))},
            "defensive_line_support": {"skill": "Support Play", "category": "Defensive Skills", "value": float(row.get('defensive_line_support', 0.0))},
            "defensive_line_support_failed": {"skill": "Support Play", "category": "Defensive Skills", "value": float(row.get('defensive_line_support_failed', 0.0))},
            "defensive_line_support_succeeded": {"skill": "Support Play", "category": "Defensive Skills", "value": float(row.get('defensive_line_support_succeeded', 0.0))},
            "recovery": {"skill": "Recovery", "category": "Defensive Skills", "value": float(row.get('recovery', 0.0))},
            "goal": {"skill": "Goals", "category": "Performance Metrics", "value": float(row.get('goal', 0.0))},
            "goal_conceded": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": float(row.get('goal_conceded', 0.0))},
            "goal_kick": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": float(row.get('goal_kick', 0.0))},
            "goal_kick_succeeded": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": float(row.get('goal_kick_succeeded', 0.0))},
            "save_by_catching": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": float(row.get('save_by_catching', 0.0))},
            "save_by_punching": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": float(row.get('save_by_punching', 0.0))},
            "control_under_pressure": {"skill": "Ball Control", "category": "Defensive Skills", "value": float(row.get('control_under_pressure', 0.0))},
            "mistake": {"skill": "Negative Performance", "category": "Defensive Skills", "value": float(row.get('mistake', 0.0))},
            "offside": {"skill": "Negative Performance", "category": "Defensive Skills", "value": float(row.get('offside', 0.0))},
            "own_goal": {"skill": "Negative Performance", "category": "Defensive Skills", "value": float(row.get('own_goal', 0.0))},
        }

def calculate_offensive_performance_metrics(row):
    return {
            "play_time": {"skill": "Shooting", "category": "Offensive Skills", "value": float(row.get('play_time', 0.0))},
            "goal": {"skill": "Goals", "category": "Performance Metrics", "value": float(row.get('goal', 0.0))},
            "assist": {"skill": "Assists", "category": "Performance Metrics", "value": float(row.get('assist', 0.0))},
            "shot_on_target": {"skill": "Shooting", "category": "Offensive Skills", "value": float(row.get('shot_on_target', 0.0))},
            "shot_off_target": {"skill": "Shooting", "category": "Offensive Skills", "value": float(row.get('shot_off_target', 0.0))},
            "total_shot": {"skill": "Shooting", "category": "Offensive Skills", "value": float(row.get('total_shot', 0.0))},
            "shot_blocked": {"skill": "Shooting", "category": "Offensive Skills", "value": float(row.get('shot_blocked', 0.0))},
            "shot_in_PA": {"skill": "Shooting", "category": "Offensive Skills", "value": float(row.get('shot_in_PA', 0.0))},
            "shot_outside_of_PA": {"skill": "Shooting", "category": "Offensive Skills", "value": float(row.get('shot_outside_of_PA', 0.0))},
            "penalty_kick": {"skill": "Shooting", "category": "Offensive Skills", "value": float(row.get('penalty_kick', 0.0))},
            "pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('pass', 0.0))},
            "forward_pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('forward_pass', 0.0))},
            "backward_pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('backward_pass', 0.0))},
            "defensive_area_pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('defensive_area_pass', 0.0))},
            "final_third_area_pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('final_third_area_pass', 0.0))},
            "middle_area_pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('middle_area_pass', 0.0))},
            "key_pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('key_pass', 0.0))},
            "long_pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('long_pass', 0.0))},
            "short_pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('short_pass', 0.0))},
            "sideways_pass": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('sideways_pass', 0.0))},
            "cross": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('cross', 0.0))},
            "cross_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('cross_succeeded', 0.0))},
            "pass_failed": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('pass_failed', 0.0))},
            "pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('pass_succeeded', 0.0))},
            "forward_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('forward_pass_succeeded', 0.0))},
            "backward_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('backward_pass_succeeded', 0.0))},
            "defensive_area_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('defensive_area_pass_succeeded', 0.0))},
            "final_third_area_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('final_third_area_pass_succeeded', 0.0))},
            "middle_area_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('middle_area_pass_succeeded', 0.0))},
            "long_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('long_pass_succeeded', 0.0))},
            "short_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('short_pass_succeeded', 0.0))},
            "sideways_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": float(row.get('sideways_pass_succeeded', 0.0))},
            "take_on": {"skill": "Dribbling", "category": "Offensive Skills", "value": float(row.get('take_on', 0.0))},
            "take_on_succeeded": {"skill": "Dribbling", "category": "Offensive Skills", "value": float(row.get('take_on_succeeded', 0.0))},
            "corner_kick": {"skill": "Set Pieces", "category": "Offensive Skills", "value": float(row.get('corner_kick', 0.0))},
            "free_kick": {"skill": "Set Pieces", "category": "Offensive Skills", "value": float(row.get('free_kick', 0.0))},
            "throw_in": {"skill": "Set Pieces", "category": "Offensive Skills", "value": float(row.get('throw_in', 0.0))},
        }




# new formulas by Freelancer, 22nd Sept 2024
def calculate_attacking_skills(row, match_sheet):
    attacking_skills_mapping = [
        "goals_scored",
        "assist",
        "shot_blocked",
        "shot_in_PA",
        "shot_outside_of_PA",
        "key_pass",
        "pass",
        "control_under_pressure",
        "shot_on_target",
        "pass_succeeded",
        "final_third_area_pass",
        "final_third_area_pass_succeeded",
        "cross",
        "cross_succeeded",
        "take_on_succeeded",
        "take_on",
        "total_shot",
        "offside",
    ]

    # Initialize the dictionary for value mapping
    attacking_skills_value_mapping = {}

    # Helper function to calculate percentage with error handling
    def calculate_percentage(numerator_key: str, denominator_key: str):
        numerator = attacking_skills_value_mapping[numerator_key]
        denominator = attacking_skills_value_mapping[denominator_key]
        attacking_skills_value_mapping.pop(numerator_key)
        attacking_skills_value_mapping.pop(denominator_key)
        try:
            return f"{int(numerator)}/{int(denominator)} ({int(((numerator / denominator) * 100))}%)"
        except ZeroDivisionError:
            return 0
        

    minutes_column = "play_time"
    attacking_skills_value_mapping[minutes_column] = int(
        int(row.get(minutes_column, 0)) / 60000
    )

    # Process other columns
    for column_name in attacking_skills_mapping:
        attacking_skills_value_mapping[column_name] = int(row.get(column_name, 0))


    # Calculate percentage values
    attacking_skills_value_mapping["(shot_on_target / total_shot) x 100"] = (
        calculate_percentage(
            "shot_on_target",
            "total_shot",
        )
    )

    attacking_skills_value_mapping["(pass_succeeded / pass) x 100"] = calculate_percentage(
        "pass_succeeded",
        "pass",
    )

    attacking_skills_value_mapping[
        "(final_third_area_pass_succeeded / final_third_area_pass) x 100"
    ] = calculate_percentage(
        "final_third_area_pass_succeeded",
        "final_third_area_pass",
    )

    attacking_skills_value_mapping["(cross_succeeded / cross) x 100"] = (
        calculate_percentage(
            "cross_succeeded",
            "cross",
        )
    )

    attacking_skills_value_mapping["(take_on_succeeded / take_on) x 100"] = (
        calculate_percentage(
            "take_on_succeeded",
            "take_on",
        )
    )

    attacking_skills_value_mapping["play_time"] = (
        f"{attacking_skills_value_mapping['play_time']}/{int(match_sheet.iloc[0]['full_time']) + int(match_sheet.iloc[0]['extra_full_time'])} min"
    )

    attacking_skills_value_mapping["Game Rating"] = float(
        row["rating"]
    ).__round__(1)


    rename_dict = {
        "play_time": "Play Time",
        "goals_scored": "Goals",
        "assist": "Assists",
        "shot_blocked": "Shots Blocked",
        "shot_in_PA": "Shots in PA",
        "shot_outside_of_PA": "Shots Outside PA",
        "key_pass": "Key Passes",
        "control_under_pressure": "Control Under Pressure",
        "offside": "Offside",
        "(shot_on_target / total_shot) x 100": "Shots",
        "(pass_succeeded / pass) x 100": "Passing",
        "(final_third_area_pass_succeeded / final_third_area_pass) x 100": "Final 1/3 Pass",
        "(cross_succeeded / cross) x 100": "Crossing",
        "(take_on_succeeded / take_on) x 100": "Take-ons",
        "Game Rating": "Game Rating",
    }

    # Rename the dict keys
    attacking_skills_value_mapping = {
        rename_dict.get(k, k): str(v) for k, v in attacking_skills_value_mapping.items()
    }

    print("attacking_skills_value_mapping: ", attacking_skills_value_mapping)

    return attacking_skills_value_mapping


def calculate_videocard_defensive(row, match_sheet):

    # List of column names to map
    videocard_defensive_mapping = [
        "rating",
        "tackle_succeeded",
        "tackle",
        "aerial_clearance_succeeded",
        "aerial_clearance",
        "aerial_duel_succeeded",
        "aerial_duel",
        "ground_duel_succeeded",
        "ground_duel",
        "loose_ball_duel_succeeded",
        "loose_ball_duel",
        "intercept",
        "intervention",
        "block",
        "shot_blocked",
        "defensive_area_pass_succeeded",
        "defensive_area_pass",
        "defensive_line_support_succeeded",
        "defensive_line_support_succeeded",
        "defensive_line_support_failed",
        "recovery",
        "mistake",
        "own_goal",
    ]

    # Initialize the dictionary for value mapping
    defensive_value_mapping = {}

    # Helper function to calculate percentage with error handling
    def calculate_percentage(numerator_key: str, denominator_key: str):
        numerator = defensive_value_mapping[numerator_key]
        denominator = defensive_value_mapping[denominator_key]
        defensive_value_mapping.pop(numerator_key)
        defensive_value_mapping.pop(denominator_key)
        try:
            return f"{int(numerator)}/{int(denominator)} ({int(((numerator / denominator) * 100))}%)"
        except ZeroDivisionError:
            return 0

    # Process 'minutes' column
    minutes_column = "play_time"
    defensive_value_mapping["Play time"] = int(
        int(row[minutes_column]) / 60000
    )

    # Process other columns
    for column_name in videocard_defensive_mapping:
        defensive_value_mapping[column_name] = int(row.get(column_name, 0))


    # Calculate percentage values
    defensive_value_mapping["Tackles"] = calculate_percentage(
        "tackle_succeeded",
        "tackle",
    )

    defensive_value_mapping["Aerial Clearances"] = calculate_percentage(
        "aerial_clearance_succeeded",
        "aerial_clearance",
    )

    defensive_value_mapping["Aerial Duels"] = calculate_percentage(
        "aerial_duel_succeeded",
        "aerial_duel",
    )

    defensive_value_mapping["Ground Duels"] = calculate_percentage(
        "ground_duel_succeeded",
        "ground_duel",
    )

    defensive_value_mapping["Loose Ball Duels"] = calculate_percentage(
        "loose_ball_duel_succeeded",
        "loose_ball_duel",
    )

    defensive_value_mapping["Defensive Area Passes"] = calculate_percentage(
        "defensive_area_pass_succeeded",
        "defensive_area_pass",
    )

    try:
        defensive_value_mapping["Defensive Line Support"] = (
            defensive_value_mapping["defensive_line_support_succeeded"]
            / (
                defensive_value_mapping["defensive_line_support_succeeded"]
                + defensive_value_mapping["defensive_line_support_failed"]
            )
        ) * 100
    except ZeroDivisionError:
        defensive_value_mapping["Defensive Line Support"] = 0

    defensive_value_mapping["Play time"] = (
        f"{defensive_value_mapping['Play time']}/{int(match_sheet.iloc[0]['full_time']) + int(match_sheet.iloc[0]['extra_full_time'])} min"
    )

    defensive_value_mapping["Game Rating"] = float(row["rating"]).__round__(1)


    rename_dict = {
        "rating": "Game Rating",
        "goals_scored": "Goals",
        "assist": "Assists",
        "shot_blocked": "Shots Blocked",
        "shot_in_PA": "Shots in PA",
        "shot_outside_of_PA": "Shots Outside PA",
        "key_pass": "Key Passes",
        "control_under_pressure": "Control Under Pressure",
        "offside": "Offside",
    }

    # Rename the dict keys
    defensive_value_mapping = {
        rename_dict.get(k, k): v for k, v in defensive_value_mapping.items()
    }

    # Keys to keep
    keys_to_keep = {
        "Play time",
        "Game Rating",
        "Shots Blocked",
        "Tackles",
        "Aerial Clearances",
        "Aerial Duels",
        "Ground Duels",
        "Loose Ball Duels",
        "Defensive Area Passes",
        "Defensive Line Support"
    }

    # Filter defensive_value_mapping
    filtered_defensive_value_mapping = {k: str(v) for k, v in defensive_value_mapping.items() if k in keys_to_keep}
    
    print("filtered_defensive_value_mapping: ", filtered_defensive_value_mapping)

    return filtered_defensive_value_mapping


def calculate_videocard_distributions(row, match_sheet):
    videocard_distribution_mapping = [
        "rating",
        "key_pass",
        "pass_succeeded",
        "pass",
        "final_third_area_pass_succeeded",
        "final_third_area_pass",
        "cross_succeeded",
        "cross",
        "long_pass_succeeded",
        "long_pass",
        "short_pass_succeeded",
        "short_pass",
        "medium_range_pass_succeeded",
        "medium_range_pass",
        "forward_pass_succeeded",
        "forward_pass",
        "sideways_pass_succeeded",
        "sideways_pass",
        "backward_pass_succeeded",
        "backward_pass",
        "take_on_succeeded",
        "take_on",
    ]
    # Initialize the dictionary for value mapping
    distribution_value_mapping = {}


    # Helper function to calculate percentage with error handling
    def calculate_percentage(numerator_key: str, denominator_key: str):
        numerator = distribution_value_mapping[numerator_key]
        denominator = distribution_value_mapping[denominator_key]
        distribution_value_mapping.pop(numerator_key)
        distribution_value_mapping.pop(denominator_key)
        try:
            return f"{int(numerator)}/{int(denominator)} ({int(((numerator / denominator) * 100))}%)"
        except ZeroDivisionError:
            return 0
        
    # Process 'minutes' column
    minutes_column = "play_time"
    distribution_value_mapping["Play time"] = int(
        int(row[minutes_column]) / 60000
    )

    # Process other columns
    for column_name in videocard_distribution_mapping:
        distribution_value_mapping[column_name] = int(row.get(column_name, 0))


    # Calculate percentage values
    distribution_value_mapping["Passing"] = calculate_percentage(
        "pass_succeeded",
        "pass",
    )

    distribution_value_mapping["Final 1/3 Passes"] = calculate_percentage(
        "final_third_area_pass_succeeded",
        "final_third_area_pass",
    )

    distribution_value_mapping["Crosses"] = calculate_percentage(
        "cross_succeeded",
        "cross",
    )

    distribution_value_mapping["Long Passes"] = calculate_percentage(
        "long_pass_succeeded",
        "long_pass",
    )

    distribution_value_mapping["Short Passes"] = calculate_percentage(
        "short_pass_succeeded",
        "short_pass",
    )

    distribution_value_mapping["Med. Passes"] = calculate_percentage(
        "medium_range_pass_succeeded",
        "medium_range_pass",
    )

    distribution_value_mapping["Fwd. Passes"] = calculate_percentage(
        "forward_pass_succeeded",
        "forward_pass",
    )

    distribution_value_mapping["Side Passes"] = calculate_percentage(
        "sideways_pass_succeeded",
        "sideways_pass",
    )

    distribution_value_mapping["Back Passes"] = calculate_percentage(
        "backward_pass_succeeded",
        "backward_pass",
    )


    distribution_value_mapping["Take-ons"] = calculate_percentage(
        "take_on_succeeded",
        "take_on",
    )

    distribution_value_mapping["Play time"] = (
        f"{distribution_value_mapping['Play time']}/{int(match_sheet.iloc[0]['full_time']) + int(match_sheet.iloc[0]['extra_full_time'])} min"
    )

    distribution_value_mapping["Game Rating"] = float(
        row["rating"]
    ).__round__(1)


    rename_dict = {
        "key_pass": "Key Passes",
        "rating": "Game Rating",
    }

    # Rename the dict keys
    distribution_value_mapping = {
        rename_dict.get(k, k): str(v) for k, v in distribution_value_mapping.items()
    }

    print("distribution_value_mapping: ", distribution_value_mapping)

    return distribution_value_mapping



# for API view
def get_performance_metrics(user):
    metrics_data = PerformanceMetrics.objects.filter(user=user)

    # Return an empty dictionary if no data is available for the user
    if not metrics_data.exists():
        return {}
    
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
        'Overall Score': metrics_data.aggregate(total_rating=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__rating'), FloatField()), 0), output_field=FloatField())))['total_rating'],
        'Play Time': metrics_data.aggregate(total_play_time=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__play_time'), FloatField()), 0), output_field=FloatField())))['total_play_time'],
        'Goals': metrics_data.aggregate(total_goals=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__goal'), FloatField()), 0), output_field=FloatField())))['total_goals'],
        'Assists': metrics_data.aggregate(total_assists=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__assist'), FloatField()), 0), output_field=FloatField())))['total_assists'],
        'Shooting Accuracy (%)': round((metrics_data.aggregate(total_shot_on_target=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__shot_on_target'), FloatField()), 0), output_field=FloatField())))['total_shot_on_target'] / total_shots['total_shots']) * 100 if total_shots['total_shots'] else 0, 2),
        'Pass Accuracy (%)': round((metrics_data.aggregate(total_pass_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__pass_succeeded'), FloatField()), 0), output_field=FloatField())))['total_pass_succeeded'] / total_passes['total_passes']) * 100 if total_passes['total_passes'] else 0, 2),
        'Expected Pass Completion (xP)': round(metrics_data.aggregate(total_pass_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__pass_succeeded'), FloatField()), 0), output_field=FloatField())))['total_pass_succeeded'] / total_passes['total_passes'] if total_passes['total_passes'] else 0, 2),
        'Expected Receiver (xReceiver)': round((metrics_data.aggregate(total_take_on_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__take_on_succeeded'), FloatField()), 0), output_field=FloatField())))['total_take_on_succeeded'] / metrics_data.aggregate(total_take_on=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__take_on'), FloatField()), 0), output_field=FloatField())))['total_take_on'] if metrics_data.aggregate(total_take_on=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__take_on'), FloatField()), 0), output_field=FloatField())))['total_take_on'] else 0) * (metrics_data.aggregate(total_forward_pass_succeeded=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass_succeeded'), FloatField()), 0), output_field=FloatField())))['total_forward_pass_succeeded'] / metrics_data.aggregate(total_forward_pass=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass'), FloatField()), 0), output_field=FloatField())))['total_forward_pass'] if metrics_data.aggregate(total_forward_pass=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass'), FloatField()), 0), output_field=FloatField())))['total_forward_pass'] else 0), 2),
        'Expected Threat (xThreat)': round(metrics_data.aggregate(x_threat=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__forward_pass_succeeded'), FloatField()), 0) * 1.2 + Coalesce(Cast(KeyTextTransform('value', 'metrics__final_third_area_pass_succeeded'), FloatField()), 0) * 1.5 * 2, output_field=FloatField())))['x_threat'], 2),
    }
    print(f"performance metrics for the user({user}): ", results)

    return results


def get_defensive_performance_metrics(user):
    metrics_data = DefensivePerformanceMetrics.objects.filter(user=user)
        
    # Return an empty dictionary if no data is available for the user
    if not metrics_data.exists():
        return {}
    
    results = {}
    FULL_GAME_TIME = 90 * 60 * 1000  # in miliseconds

    play_time = metrics_data.aggregate(total_play_time=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__play_time'), FloatField()), 0), output_field=FloatField())))['total_play_time']
    
    if not play_time or play_time == 0:
        return {}
    
    def get_metric(metric_name):
        return metrics_data.aggregate(total=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', f'metrics__{metric_name}'), FloatField()), 0), output_field=FloatField())))['total']
    
    def normalized_count(metric_name):
        return round((get_metric(metric_name) / play_time) * FULL_GAME_TIME, 2)
    
    # aerial_clearance = normalized_count('aerial_clearance')
    aerial_clearance_failed = normalized_count('aerial_clearance_failed')
    aerial_clearance_succeeded = normalized_count('aerial_clearance_succeeded')
    clearance = normalized_count('clearance')
    # block = normalized_count('block')
    # intercept = normalized_count('intercept')
    # intervention = normalized_count('intervention')
    tackle = normalized_count('tackle')
    tackle_succeeded = normalized_count('tackle_succeeded')
    # foul = normalized_count('foul')
    # foul_won = normalized_count('foul_won')
    # aerial_duel = normalized_count('aerial_duel')
    aerial_duel_failed = normalized_count('aerial_duel_failed')
    aerial_duel_succeeded = normalized_count('aerial_duel_succeeded')
    # ground_duel = normalized_count('ground_duel')
    ground_duel_failed = normalized_count('ground_duel_failed')
    ground_duel_succeeded = normalized_count('ground_duel_succeeded')
    # loose_ball_duel = normalized_count('loose_ball_duel')
    loose_ball_duel_failed = normalized_count('loose_ball_duel_failed')
    loose_ball_duel_succeeded = normalized_count('loose_ball_duel_succeeded')
    # defensive_line_support = normalized_count('defensive_line_support')
    defensive_line_support_failed = normalized_count('defensive_line_support_failed')
    defensive_line_support_succeeded = normalized_count('defensive_line_support_succeeded')
    # recovery = normalized_count('recovery')
    # goal_conceded = normalized_count('goal_conceded')
    # goal_kick = normalized_count('goal_kick')
    # goal_kick_succeeded = normalized_count('goal_kick_succeeded')
    # save_by_catching = normalized_count('save_by_catching')
    # save_by_punching = normalized_count('save_by_punching')
    # control_under_pressure = normalized_count('control_under_pressure')
    mistake = normalized_count('mistake')
    offside = normalized_count('offside')
    # own_goal = normalized_count('own_goal')
    
    clearance_success_rate = round((aerial_clearance_succeeded + clearance) / (aerial_clearance_succeeded + aerial_clearance_failed + clearance) * 100, 2) if (aerial_clearance_succeeded + aerial_clearance_failed + clearance) else 0
    tackle_success_rate = round(tackle_succeeded / (tackle) * 100, 2) if (tackle) else 0
    duel_success_rate = round((aerial_duel_succeeded + ground_duel_succeeded + loose_ball_duel_succeeded) / (aerial_duel_succeeded + ground_duel_succeeded + loose_ball_duel_succeeded + aerial_duel_failed + ground_duel_failed + loose_ball_duel_failed) * 100, 2) if (aerial_duel_succeeded + ground_duel_succeeded + loose_ball_duel_succeeded + aerial_duel_failed + ground_duel_failed + loose_ball_duel_failed) else 0
    discipline_score = round(((mistake * 1) + (offside * 3)) / (play_time / FULL_GAME_TIME), 2)
    
    weighted_clearances_per_full_game = round(((aerial_clearance_succeeded * 2) + (clearance * 2) - (aerial_clearance_failed * 1)) / (play_time / FULL_GAME_TIME), 2)
    overall_clearance_score = round(weighted_clearances_per_full_game * (clearance_success_rate / 100), 2)
    
    weighted_tackles_per_full_game = round(((tackle_succeeded * 2) - ((tackle - tackle_succeeded) * 1)) / (play_time / FULL_GAME_TIME), 2)
    overall_tackle_score = round(weighted_tackles_per_full_game * (tackle_success_rate / 100), 2)
    
    weighted_duels_per_full_game = round(((aerial_duel_succeeded * 2) + (ground_duel_succeeded * 2) + (loose_ball_duel_succeeded * 2) - (aerial_duel_failed * 1) - (ground_duel_failed * 1) - (loose_ball_duel_failed * 1)) / (play_time / FULL_GAME_TIME), 2)
    overall_duel_score = round(weighted_duels_per_full_game * (duel_success_rate / 100), 2)
    
    overall_interception_score = normalized_count('intercept') + normalized_count('intervention')
    overall_recovery_score = normalized_count('recovery')
    
    overall_defensive_line_support_score = round(((defensive_line_support_succeeded * 2) - (defensive_line_support_failed * 1)) / (play_time / FULL_GAME_TIME), 2)
    
    overall_defensive_skills_score = round((0.25 * overall_clearance_score + 0.2 * overall_tackle_score + 0.2 * overall_interception_score + 0.15 * overall_duel_score + 0.1 * overall_recovery_score + 0.1 * discipline_score), 2)
    
    results.update({
        'Overall Defensive Skills Score': float(overall_defensive_skills_score),
        'Clearances': float(overall_clearance_score),
        # 'Aerial Clearance': aerial_clearance,
        # 'Aerial Clearance Succeeded': aerial_clearance_succeeded,
        # 'Clearance': clearance,
        # 'Block': block,
        'Tackles': float(overall_tackle_score),
        # 'Tackle': tackle,
        # 'Tackle Succeeded': tackle_succeeded,
        # 'Foul': foul,
        # 'Foul Won': foul_won,
        'Interceptions': float(overall_interception_score),
        # 'Intercept': intercept,
        # 'Intervention': intervention,
        'Duels': float(overall_duel_score),
        # 'Aerial Duel': aerial_duel,
        # 'Aerial Duel Succeeded': aerial_duel_succeeded,
        # 'Aerial Duel Failed': aerial_duel_failed,
        # 'Ground Duel': ground_duel,
        # 'Ground Duel Succeeded': ground_duel_succeeded,
        # 'Ground Duel Failed': ground_duel_failed,
        # 'Loose Ball Duel': loose_ball_duel,
        # 'Loose Ball Duel Succeeded': loose_ball_duel_succeeded,
        # 'Loose Ball Duel Failed': loose_ball_duel_failed,
        'Defensive Line Support': float(overall_defensive_line_support_score),
        # 'Defensive Line Support Succeeded': defensive_line_support_succeeded,
        # 'Defensive Line Support Failed': defensive_line_support_failed,
        'Recovery': float(overall_recovery_score),
        # 'Goal Conceded': goal_conceded,
        # 'Goal Kick': goal_kick,
        # 'Goal Kick Succeeded': goal_kick_succeeded,
        # 'Save by Catching': save_by_catching,
        # 'Save by Punching': save_by_punching,
        # 'Control Under Pressure': control_under_pressure,
        # 'Mistake': mistake,
        # 'Offside': offside,
        # 'Own Goal': own_goal,
        'Discipline Score': float(discipline_score),
    })

    return results


def get_offensive_performance_metrics(user):
    metrics_data = OffensivePerformanceMetrics.objects.filter(user=user)
        
    # Return an empty dictionary if no data is available for the user
    if not metrics_data.exists():
        return {}
        
    results = {}
    FULL_GAME_TIME = 90 * 60 * 1000  # in miliseconds

    play_time = metrics_data.aggregate(total_play_time=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', 'metrics__play_time'), FloatField()), 0), output_field=FloatField())))['total_play_time']
        
    if not play_time or play_time == 0:
        return {}

        
    def get_metric(metric_name):
        return metrics_data.aggregate(total=Sum(ExpressionWrapper(Coalesce(Cast(KeyTextTransform('value', f'metrics__{metric_name}'), FloatField()), 0), output_field=FloatField())))['total']

    def normalized_count(metric_name):
        return round((get_metric(metric_name) / play_time) * FULL_GAME_TIME, 2)


    goals = normalized_count('goal')
    assists = normalized_count('assist')
    shot_on_target = normalized_count('shot_on_target')
    shot_off_target = normalized_count('shot_off_target')
    total_shot = normalized_count('total_shot')
    shot_blocked = normalized_count('shot_blocked')
    shot_in_PA = normalized_count('shot_in_PA')
    # shot_outside_of_PA = normalized_count('shot_outside_of_PA')
    # penalty_kick = normalized_count('penalty_kick')
    pass_total = normalized_count('pass')
    pass_succeeded = normalized_count('pass_succeeded')
    pass_failed = normalized_count('pass_failed')
    forward_pass = normalized_count('forward_pass')
    forward_pass_succeeded = normalized_count('forward_pass_succeeded')
    # cross = normalized_count('cross')
    cross_succeeded = normalized_count('cross_succeeded')
    # long_pass = normalized_count('long_pass')
    long_pass_succeeded = normalized_count('long_pass_succeeded')
    # short_pass = normalized_count('short_pass')
    # short_pass_succeeded = normalized_count('short_pass_succeeded')
    take_on = normalized_count('take_on')
    take_on_succeeded = normalized_count('take_on_succeeded')
    # key_pass = normalized_count('key_pass')
    # final_third_pass = normalized_count('final_third_area_pass')
    final_third_pass_succeeded = normalized_count('final_third_area_pass_succeeded')
    # middle_area_pass = normalized_count('middle_area_pass')
    # middle_area_pass_succeeded = normalized_count('middle_area_pass_succeeded')
    # backward_pass = normalized_count('backward_pass')
    # backward_pass_succeeded = normalized_count('backward_pass_succeeded')
    # defensive_area_pass = normalized_count('defensive_area_pass')
    # defensive_area_pass_succeeded = normalized_count('defensive_area_pass_succeeded')
    
    # pass_accuracy = round((pass_succeeded / pass_total) * 100, 2) if pass_total else 0
    xp = round(pass_succeeded / pass_total, 2) if pass_total else 0
    xreceiver = round((take_on_succeeded / take_on) * (forward_pass_succeeded / forward_pass), 2) if take_on and forward_pass else 0
    xthreat = round(forward_pass_succeeded * 1.2 + final_third_pass_succeeded * 1.5 * 2, 2)

    weighted_passes_per_full_game = round(((pass_succeeded * 1 + forward_pass_succeeded * 1.2 + cross_succeeded * 1.5 + long_pass_succeeded * 1.3 - pass_failed * 0.5) / (play_time / FULL_GAME_TIME)), 2)
    overall_passing_score = round(weighted_passes_per_full_game * (pass_succeeded / pass_total) if pass_total else 0, 2)

    weighted_shots_per_full_game = round(((shot_on_target * 2 + shot_in_PA * 1.5 - shot_off_target - shot_blocked * 0.5) / (play_time / FULL_GAME_TIME)), 2)
    # shooting_accuracy = round((shot_on_target / total_shot) * 100, 2) if total_shot else 0
    overall_shooting_score = round(weighted_shots_per_full_game * (shot_on_target / total_shot) if total_shot else 0, 2)

    weighted_dribbles_per_full_game = round(((take_on_succeeded * 2 + take_on * 2 - take_on_succeeded - take_on_succeeded) / (play_time / FULL_GAME_TIME)), 2)
    # dribbling_success_rate = round((take_on_succeeded / take_on) * 100, 2) if take_on else 0
    overall_dribbling_score = round(weighted_dribbles_per_full_game * (take_on_succeeded / take_on) if take_on else 0, 2)

    overall_offensive_skills_score = round((0.35 * goals + 0.15 * assists + 0.15 * overall_shooting_score + 0.15 * overall_passing_score + 0.1 * overall_dribbling_score + 0.05 * xp + 0.05 * xreceiver), 2)

    results.update({
        'Overall Offensive Skills Score': float(overall_offensive_skills_score),
        'Goals': float(goals),
        'Assists': float(assists),
        # 'Shots on Target': shot_on_target,
        # 'Shots off Target': shot_off_target,
        # 'Total Shots': total_shot,
        # 'Shots Blocked': shot_blocked,
        # 'Shots in PA': shot_in_PA,
        # 'Shots Outside PA': shot_outside_of_PA,
        # 'Penalty Kicks': penalty_kick,
        'Overall Shooting Score': float(overall_shooting_score),
        # 'Passes': pass_total,
        # 'Pass Accuracy (%)': pass_accuracy,
        'Overall Passing Score': float(overall_passing_score),
        # 'Key Passes': key_pass,
        # 'Crosses': cross,
        # 'Crosses Completed': cross_succeeded,
        # 'Long Passes': long_pass,
        # 'Long Passes Completed': long_pass_succeeded,
        # 'Short Passes': short_pass,
        # 'Short Passes Completed': short_pass_succeeded,
        # 'Forward Passes': forward_pass,
        # 'Forward Passes Completed': forward_pass_succeeded,
        # 'Final Third Passes': final_third_pass,
        # 'Final Third Passes Completed': final_third_pass_succeeded,
        # 'Middle Area Passes': middle_area_pass,
        # 'Middle Area Passes Completed': middle_area_pass_succeeded,
        # 'Backward Passes': backward_pass,
        # 'Backward Passes Completed': backward_pass_succeeded,
        # 'Defensive Area Passes': defensive_area_pass,
        # 'Defensive Area Passes Completed': defensive_area_pass_succeeded,
        'Overall Dribbling Score': float(overall_dribbling_score),
        # 'Take Ons': take_on,
        # 'Take Ons Completed': take_on_succeeded,
        'Expected Pass Completion (xP)': float(xp),
        'Expected Receiver (xReceiver)': float(xreceiver),
        'Expected Threat (xThreat)': float(xthreat),
    })

    print("Types: ", type(float(overall_dribbling_score)), type(goals), type(xp), type(xreceiver), type(xthreat))

    return results



# ai-insight API, unique for each card
def get_prompt_for_insight(user, card):
    if user.selected_language == 'he':
        language = "Hebrew"
    else:
        language = "English"

    if card == "StatusCard":
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                player_data.append(get_status_card_metrics(player))

            user_data = {
                'team-wellness': player_data
            }
            print("player_data for coach: ", user_data)
            
            prompt = f"Generate a concise expert analysis for a coach only in {language} language from the provided wellness data of players, highlighting key points that could impact athlete performance. Keep the word count under 20 words. Exclude JSON data. Wellness scores range from 1 to 5, with 1 being the lowest and 5 the highest. Note that low overall scores often correlate with sub-optimal performance. Encourage athletes to improve in areas where they are lacking. Data provided: {user_data}. Example: 'Overall wellness is relatively low, with fatigue and sleep quality as key areas for improvement. Encourage better rest and recovery to maximize performance. {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}'"
            return prompt
        
        else:
            user_data = {
                'wellness': get_status_card_metrics(user)
            }
            prompt = f"Generate a one-liner analysis for the user only in {language} language with the following data which is crisp and helpful from the perspective of an expert directly to the athelete. Keep the word count less than 20 words. Do not include JSON data. The data being passed is for wellness and it is expected that you will bring attention to something that might impact their performance as an athelete. Wellness Scores are 1-5 where 1 is the lowest and 5 is the highest. It is generally noticed that low overall scores lead to sub-optimal performace. We always want to push atheletes to do better in sections where they are lacking. Data passed: {user_data}. {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
            
    elif card == 'DailySnapshot':
        if user.role == 'Coach':
            role = 'Coach'
        else:
            role = 'Athlete'

        today = datetime.today()
         
        user_data = {
            "wellness": get_status_card_metrics(user),
            "calendar": get_daily_snapshot(user, today),
            "performance-metrics": get_performance_metrics(user),
            "defensive-performance-metrics": get_defensive_performance_metrics(user),
            "offensive-performance-metrics": get_offensive_performance_metrics(user),
            "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        prompt = f"Generate a concise expert analysis for {role} only in {language} language based on the provided calendar data, highlighting key events, training sessions, rest periods, and suggesting reschedules for conflicts keeping games as immovable but suggest if athelete should play if their wellness scores are too low. Also look at other stats like wellness and other stats to set the priority for the user. Keep it under 20 words and avoid mentioning the data passed to you or atheletes and coaches. Please make sure to address the athelete in second person and not in third person.  Data provided: {user_data}.  Maximum 40 words. Example: 'Reschedule Team B training on July 20 due to potential conflicts. Let's focus on the upcoming game on July 19.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
        return prompt
    
    elif card == 'PerformanceMetrics':
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                player_data.append(get_performance_metrics(player))

            user_data = {
                'team-performance-metrics': player_data
            }
            print("team-performance-metrics for coach: ", user_data)
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided performance metrics for the team, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the coach. Data provided:{user_data}. Example: 'Players showed high passing accuracy (80%) and successful take-ons (67%) but need to create more goal-scoring opportunities. Suggested drills: Pass and Move, Attacking Overload, and Finishing Under Pressure.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                'performance-metrics': get_performance_metrics(user)
            }
            prompt = f"Generate a concise expert analysis for athletes only in {language} language based on the provided performance metrics, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the player. Data provided:{user_data}. Example:'You have strong passing and attacking skills, with good goal and assist numbers. Keep working on shooting and disciplinary tendencies. To improve, focus on drills for finishing and maintaining composure in pressure situations.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
    elif card == 'DefensivePerformanceMetrics':
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                player_data.append(get_defensive_performance_metrics(player))

            user_data = {
                'team-defensive-performance-metrics': player_data
            }
            print("team-defensive-performance-metrics for coach: ", user_data)
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided defensive performance metrics for the team, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the coach. Data provided:{user_data}. {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                'defensive-performance-metrics': get_defensive_performance_metrics(user)
            }
            prompt = f"Generate a concise expert analysis for athletes only in {language} language based on the provided defensive performance metrics, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Data provided:{user_data}. Example: 'Strong tackling, dueling, and recovery skills shown. Need to work on aerial clearances and improving goalkeeping for a more well-rounded performance. Drills targeting clearing and catching under pressure may benefit.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
    elif card == 'OffensivePerformanceMetrics':
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                player_data.append(get_offensive_performance_metrics(player))

            user_data = {
                'team-offensive-performance-metrics': player_data
            }
            print("team-offensive-performance-metrics for coach: ", user_data)
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided defensive performance metrics for the team, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the coach. Data provided:{user_data}. {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                'offensive-performance-metrics': get_offensive_performance_metrics(user)
            }
            prompt = f"Generate a concise expert analysis for athletes based only in {language} language on the provided offensive performance metrics, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Data provided:{user_data}. Example: 'This athlete has strong shooting and passing skills but may benefit from targeted drills to improve pass accuracy. Suggest incorporating dribbling and set piece work to further enhance offensive performance.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
    
    return None
