from django.utils.timezone import timedelta
from django.utils import timezone

from api.models import OneTimeEvents, RecurringEvents
from api.serializer import StatusCardMetricsSerializer
from .metrics_calculations import *

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