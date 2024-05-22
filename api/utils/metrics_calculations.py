from django.utils import timezone
from django.db.models import Avg
from api.models import DailyWellnessUserResponse, RPEUserResponse


# ****************** StatusCard Metrics **************************

# overall score (7 days or defined period) - (STM-01)
# Average of selected scores from the wellness and RPE tables, typically over the past week or another defined period.
def calculate_overall_score(user, days=7):
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(days=days)
    wellness_avg = DailyWellnessUserResponse.objects.filter(
        user=user,
        created_on__range=(start_date, end_date)
    ).aggregate(Avg('response'))['response__avg']

    rpe_avg = RPEUserResponse.objects.filter(
        user=user,
        created_on__range=(start_date, end_date)
    ).aggregate(Avg('response'))['response__avg']

    if wellness_avg is None and rpe_avg is None:
        return 0  # or return "N/A" or return None
    
    wellness_avg = wellness_avg or 0
    rpe_avg = rpe_avg or 0

    overall_avg = (wellness_avg + rpe_avg) / 2
    return round(overall_avg, 1)


# sRPE (STM-06)
# Most recent entry for training intensity from the RPE table.
def calculate_srpe(user):
    most_recent_training_intensity = RPEUserResponse.objects.filter(
        user=user,
        question__name__contains='Intensity',
        question__after_session_type__contains='Training' # only trainings, not match session
    ).order_by('-created_on').first()
    
    return int(most_recent_training_intensity.response) if most_recent_training_intensity else 0


# Readiness Score (STM-07)
# A weighted average of recent scores for sleep quality, mood, and recovery.
def calculate_readiness_score(user, weights={'sleep': 0.4, 'mood': 0.3, 'recovery': 0.3}):
    sleep_score = DailyWellnessUserResponse.objects.filter(
        user=user,
        question__name__contains='Sleep'
    ).order_by('-created_on').first()

    mood_score = DailyWellnessUserResponse.objects.filter(
        user=user,
        question__name__contains='Mood'
    ).order_by('-created_on').first()

    recovery_score = RPEUserResponse.objects.filter(
        user=user,
        question__name__contains='Recovery'
    ).order_by('-created_on').first()

    if not sleep_score and not mood_score and not recovery_score:
        return 0  # or return "N/A"
    
    sleep_score = sleep_score.response if sleep_score else 0
    mood_score = mood_score.response if mood_score else 0
    recovery_score = recovery_score.response if recovery_score else 0

    readiness_score = (int(sleep_score) * weights['sleep'] + int(mood_score) * weights['mood'] + int(recovery_score) * weights['recovery'])
    return readiness_score


# Sleep Quality (SMT-05)
# Most recent score for sleep quality.
def calculate_sleep_quality(user):
    most_recent_sleep = DailyWellnessUserResponse.objects.filter(
        user=user,
        question__name__contains='Sleep'
    ).order_by('-created_on').first()

    return int(most_recent_sleep.response) if most_recent_sleep else 0


# Fatigue (SMT-03)
# Most recent fatigue score from the RPE table.
def calculate_fatigue_score(user):
    most_recent_fatigue = RPEUserResponse.objects.filter(
        user=user,
        question__name__contains='Fatigue'
    ).order_by('-created_on').first()

    return int(most_recent_fatigue.response) if most_recent_fatigue else 0


# Mood (SMT-02)
# Most recent mood score.
def calculate_mood_score(user):
    most_recent_mood = DailyWellnessUserResponse.objects.filter(
        user=user,
        question__name__contains='Mood'
    ).order_by('-created_on').first()

    return int(most_recent_mood.response) if most_recent_mood else 0


# Play Time (SMT-08)
# Total minutes played in the most recent game or training session.
def calculate_play_time(user):
    # data not available
    return 0