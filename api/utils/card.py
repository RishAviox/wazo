from django.utils.timezone import timedelta
from django.utils import timezone

from api.models import OneTimeEvents, RecurringEvents

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