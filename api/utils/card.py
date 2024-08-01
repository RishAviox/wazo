from django.utils.timezone import timedelta
from django.utils import timezone
from django.db.models import Sum, FloatField, ExpressionWrapper
from django.db.models.functions import Cast, Coalesce
from django.db.models.fields.json import KeyTextTransform
from django.utils.timezone import datetime


from api.models import (
                        OneTimeEvents, RecurringEvents, PerformanceMetrics, 
                        DefensivePerformanceMetrics, OffensivePerformanceMetrics,
                        StatusCardMetrics,
                    )
from api.serializer import StatusCardMetricsSerializer, WajoUserSerializer
from .metrics_calculations import *


# for status card
def get_status_card_metrics(user):
    try:
        metrics = StatusCardMetrics.objects.filter(user=user).latest('updated_on')
        serializer = StatusCardMetricsSerializer(metrics)
        return serializer.data
    
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


# for wellness signal
def calculate_and_store_status_card_metrics(user):
    metrics = {
        'overall_score': calculate_overall_score(user, days=7),
        'srpe_score': calculate_srpe(user),
        'readiness_score': calculate_readiness_score(user),
        'sleep_quality': calculate_sleep_quality(user),
        'fatigue_score': calculate_fatigue_score(user),
        'mood_score': calculate_mood_score(user),
        'play_time': calculate_play_time(user)
    }
    print(metrics)
    metrics_serializer = StatusCardMetricsSerializer(data=metrics)
    if metrics_serializer.is_valid():
        metrics_serializer.save(user=user)


# for MatchEventDataFile processing Signal
def calculate_performance_metrics(row):
    return {
            "rating": {"skill": "Rating", "category": "Performance Metrics", "value": row.get('rating', 0)},
            "play_time": {"skill": "Play Time", "category": "Performance Metrics", "value": row.get('play_time', 0)},
            "goal": {"skill": "Goals", "category": "Performance Metrics", "value": row.get('goal', 0)},
            "assist": {"skill": "Assists", "category": "Performance Metrics", "value": row.get('assist', 0)},
            "shot_on_target": {"skill": "Shooting", "category": "Performance Metrics", "value": row.get('shot_on_target', 0)},
            "pass_succeeded": {"skill": "Passing", "category": "Performance Metrics", "value": row.get('pass_succeeded', 0)},
            "yellow_card": {"skill": "Disciplinary", "category": "Performance Metrics", "value": row.get('yellow_card', 0)},
            "red_card": {"skill": "Disciplinary", "category": "Performance Metrics", "value": row.get('red_card', 0)},
            "total_shot": {"skill": "Total Shot", "category": "Performance Metrics", "value": row.get('total_shot', 0)},
            "pass": {"skill": "Pass", "category": "Performance Metrics", "value": row.get('pass', 0)},
            "take_on_succeeded": {"skill": "Take On Succeeded", "category": "Performance Metrics", "value": row.get('take_on_succeeded', 0)},
            "take_on": {"skill": "Take On", "category": "Performance Metrics", "value": row.get('take_on', 0)},
            "forward_pass_succeeded": {"skill": "Forward Pass Succeeded", "category": "Performance Metrics", "value": row.get('forward_pass_succeeded', 0)},
            "forward_pass": {"skill": "Forward Pass", "category": "Performance Metrics", "value": row.get('forward_pass', 0)},
            "final_third_area_pass_succeeded": {"skill": "Final Third Area Pass Succeeded", "category": "Performance Metrics", "value": row.get('final_third_area_pass_succeeded', 0)},
            "final_third_area_pass": {"skill": "Final Third Area Pass", "category": "Performance Metrics", "value": row.get('final_third_area_pass', 0)},
        }

def calculate_defensive_performance_metrics(row):
    return {
            "play_time": {"skill": "Play Time", "category": "Performance Metrics", "value": row.get('play_time', 0)},
            "aerial_clearance": {"skill": "Clearances", "category": "Defensive Skills", "value": row.get('aerial_clearance', 0)},
            "aerial_clearance_failed": {"skill": "Clearances", "category": "Defensive Skills", "value": row.get('aerial_clearance_failed', 0)},
            "aerial_clearance_succeeded": {"skill": "Clearances", "category": "Defensive Skills", "value": row.get('aerial_clearance_succeeded', 0)},
            "clearance": {"skill": "Clearances", "category": "Defensive Skills", "value": row.get('clearance', 0)},
            "block": {"skill": "Clearances", "category": "Defensive Skills", "value": row.get('block', 0)},
            "intercept": {"skill": "Interceptions", "category": "Defensive Skills", "value": row.get('intercept', 0)},
            "intervention": {"skill": "Interceptions", "category": "Defensive Skills", "value": row.get('intervention', 0)},
            "tackle": {"skill": "Tackling", "category": "Defensive Skills", "value": row.get('tackle', 0)},
            "tackle_succeeded": {"skill": "Tackling", "category": "Defensive Skills", "value": row.get('tackle_succeeded', 0)},
            "foul": {"skill": "Tackling", "category": "Defensive Skills", "value": row.get('foul', 0)},
            "foul_won": {"skill": "Tackling", "category": "Defensive Skills", "value": row.get('foul_won', 0)},
            "aerial_duel": {"skill": "Duels", "category": "Defensive Skills", "value": row.get('aerial_duel', 0)},
            "aerial_duel_failed": {"skill": "Duels", "category": "Defensive Skills", "value": row.get('aerial_duel_failed', 0)},
            "aerial_duel_succeeded": {"skill": "Duels", "category": "Defensive Skills", "value": row.get('aerial_duel_succeeded', 0)},
            "ground_duel": {"skill": "Duels", "category": "Defensive Skills", "value": row.get('ground_duel', 0)},
            "ground_duel_failed": {"skill": "Duels", "category": "Defensive Skills", "value": row.get('ground_duel_failed', 0)},
            "ground_duel_succeeded": {"skill": "Duels", "category": "Defensive Skills", "value": row.get('ground_duel_succeeded', 0)},
            "loose_ball_duel": {"skill": "Duels", "category": "Defensive Skills", "value": row.get('loose_ball_duel', 0)},
            "loose_ball_duel_failed": {"skill": "Duels", "category": "Defensive Skills", "value": row.get('loose_ball_duel_failed', 0)},
            "loose_ball_duel_succeeded": {"skill": "Duels", "category": "Defensive Skills", "value": row.get('loose_ball_duel_succeeded', 0)},
            "defensive_line_support": {"skill": "Support Play", "category": "Defensive Skills", "value": row.get('defensive_line_support', 0)},
            "defensive_line_support_failed": {"skill": "Support Play", "category": "Defensive Skills", "value": row.get('defensive_line_support_failed', 0)},
            "defensive_line_support_succeeded": {"skill": "Support Play", "category": "Defensive Skills", "value": row.get('defensive_line_support_succeeded', 0)},
            "recovery": {"skill": "Recovery", "category": "Defensive Skills", "value": row.get('recovery', 0)},
            "goal": {"skill": "Goals", "category": "Performance Metrics", "value": row.get('goal', 0)},
            "goal_conceded": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": row.get('goal_conceded', 0)},
            "goal_kick": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": row.get('goal_kick', 0)},
            "goal_kick_succeeded": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": row.get('goal_kick_succeeded', 0)},
            "save_by_catching": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": row.get('save_by_catching', 0)},
            "save_by_punching": {"skill": "Goalkeeping", "category": "Defensive Skills", "value": row.get('save_by_punching', 0)},
            "control_under_pressure": {"skill": "Ball Control", "category": "Defensive Skills", "value": row.get('control_under_pressure', 0)},
            "mistake": {"skill": "Negative Performance", "category": "Defensive Skills", "value": row.get('mistake', 0)},
            "offside": {"skill": "Negative Performance", "category": "Defensive Skills", "value": row.get('offside', 0)},
            "own_goal": {"skill": "Negative Performance", "category": "Defensive Skills", "value": row.get('own_goal', 0)},
        }

def calculate_offensive_performance_metrics(row):
    return {
            "play_time": {"skill": "Shooting", "category": "Offensive Skills", "value": row.get('play_time', 0)},
            "goal": {"skill": "Goals", "category": "Performance Metrics", "value": row.get('goal', 0)},
            "assist": {"skill": "Assists", "category": "Performance Metrics", "value": row.get('assist', 0)},
            "shot_on_target": {"skill": "Shooting", "category": "Offensive Skills", "value": row.get('shot_on_target', 0)},
            "shot_off_target": {"skill": "Shooting", "category": "Offensive Skills", "value": row.get('shot_off_target', 0)},
            "total_shot": {"skill": "Shooting", "category": "Offensive Skills", "value": row.get('total_shot', 0)},
            "shot_blocked": {"skill": "Shooting", "category": "Offensive Skills", "value": row.get('shot_blocked', 0)},
            "shot_in_PA": {"skill": "Shooting", "category": "Offensive Skills", "value": row.get('shot_in_PA', 0)},
            "shot_outside_of_PA": {"skill": "Shooting", "category": "Offensive Skills", "value": row.get('shot_outside_of_PA', 0)},
            "penalty_kick": {"skill": "Shooting", "category": "Offensive Skills", "value": row.get('penalty_kick', 0)},
            "pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('pass', 0)},
            "forward_pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('forward_pass', 0)},
            "backward_pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('backward_pass', 0)},
            "defensive_area_pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('defensive_area_pass', 0)},
            "final_third_area_pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('final_third_area_pass', 0)},
            "middle_area_pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('middle_area_pass', 0)},
            "key_pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('key_pass', 0)},
            "long_pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('long_pass', 0)},
            "short_pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('short_pass', 0)},
            "sideways_pass": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('sideways_pass', 0)},
            "cross": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('cross', 0)},
            "cross_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('cross_succeeded', 0)},
            "pass_failed": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('pass_failed', 0)},
            "pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('pass_succeeded', 0)},
            "forward_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('forward_pass_succeeded', 0)},
            "backward_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('backward_pass_succeeded', 0)},
            "defensive_area_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('defensive_area_pass_succeeded', 0)},
            "final_third_area_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('final_third_area_pass_succeeded', 0)},
            "middle_area_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('middle_area_pass_succeeded', 0)},
            "long_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('long_pass_succeeded', 0)},
            "short_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('short_pass_succeeded', 0)},
            "sideways_pass_succeeded": {"skill": "Passing", "category": "Offensive Skills", "value": row.get('sideways_pass_succeeded', 0)},
            "take_on": {"skill": "Dribbling", "category": "Offensive Skills", "value": row.get('take_on', 0)},
            "take_on_succeeded": {"skill": "Dribbling", "category": "Offensive Skills", "value": row.get('take_on_succeeded', 0)},
            "corner_kick": {"skill": "Set Pieces", "category": "Offensive Skills", "value": row.get('corner_kick', 0)},
            "free_kick": {"skill": "Set Pieces", "category": "Offensive Skills", "value": row.get('free_kick', 0)},
            "throw_in": {"skill": "Set Pieces", "category": "Offensive Skills", "value": row.get('throw_in', 0)},
        }


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
        combined_events = get_daily_snapshot(user, today)
        user_data = {
            "calender": combined_events,
        }
        prompt = f"Generate a concise expert analysis for {role} only in {language} language based on the provided calendar data, highlighting key events, training sessions, rest periods, and suggesting reschedules for conflicts keeping games as immovable. Keep it under 20 words and avoid mentioning the data passed to you or atheletes and coaches. Data provided: {user_data}. {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
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

