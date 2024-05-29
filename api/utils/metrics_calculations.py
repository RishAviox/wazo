from django.utils import timezone
from api.models import DailyWellnessUserResponse, RPEUserResponse, DailyWellnessQuestionnaire, RPEQuestionnaire

# Helper function to extract score from JSON responses
def get_score_by_q_id(response, q_id):
    for item in response:
        if item['q_id'] == q_id:
            return item['score']
    return 0

def get_rpe_score_by_q_name(user, response, q_name):
    scores = []
    for item in response:
        question = RPEQuestionnaire.objects.filter(q_id=item['q_id'], language=user.selected_language).first()
        if question and q_name in question.name:
            scores.append(item['score'])
    scores_avg = sum(scores) / len(scores) if scores else 0
    return scores_avg

def get_wellness_score_by_q_name(user, response, q_name):
    scores = []
    for item in response:
        question = DailyWellnessQuestionnaire.objects.filter(q_id=item['q_id'], language=user.selected_language).first()
        if question and q_name in question.name:
            scores.append(item['score'])
    scores_avg = sum(scores) / len(scores) if scores else 0
    return scores_avg

# Helper function to get the most recent instance with the required response count
def get_most_recent_instance_with_count(queryset, required_count):
    for instance in queryset:
        if len(instance.response) == required_count:
            return instance
    return None

# ****************** StatusCard Metrics **************************

def calculate_overall_score(user, days=7):
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(days=days)
    wellness_responses = DailyWellnessUserResponse.objects.filter(
        user=user,
        updated_on__range=(start_date, end_date)
    )

    rpe_responses = RPEUserResponse.objects.filter(
        user=user,
        updated_on__range=(start_date, end_date)
    )

    wellness_scores = []
    rpe_scores = []

    for instance in wellness_responses:
        if len(instance.response) == 8:  # Ensure response count is 8
            wellness_scores.extend([item['score'] for item in instance.response])

    for instance in rpe_responses:
        if len(instance.response) == 14:  # Ensure response count is 14
            rpe_scores.extend([item['score'] for item in instance.response])

    wellness_avg = sum(wellness_scores) / len(wellness_scores) if wellness_scores else 0
    rpe_avg = sum(rpe_scores) / len(rpe_scores) if rpe_scores else 0

    if not wellness_avg and not rpe_avg:
        return "N/A"
    
    print("scores: ", wellness_scores, rpe_scores)

    overall_avg = (wellness_avg + rpe_avg) / 2
    return round(overall_avg, 1)

def calculate_srpe(user):
    most_recent_training_intensity = RPEUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')

    most_recent_training_intensity = get_most_recent_instance_with_count(most_recent_training_intensity, 14)
    
    if most_recent_training_intensity:
        return get_rpe_score_by_q_name(user, most_recent_training_intensity.response, 'Intensity')
    return "N/A"

def calculate_readiness_score(user, weights={'sleep': 0.4, 'mood': 0.3, 'recovery': 0.3}):
    most_recent_wellness = DailyWellnessUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')

    most_recent_rpe = RPEUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')

    most_recent_wellness = get_most_recent_instance_with_count(most_recent_wellness, 8)
    most_recent_rpe = get_most_recent_instance_with_count(most_recent_rpe, 14)

    sleep_score = get_wellness_score_by_q_name(user, most_recent_wellness.response, 'Sleep') if most_recent_wellness else 0
    mood_score = get_wellness_score_by_q_name(user, most_recent_wellness.response, 'Mood') if most_recent_wellness else 0
    recovery_score = get_rpe_score_by_q_name(user, most_recent_rpe.response, 'Recovery') if most_recent_rpe else 0

    print('sleep_score: ', sleep_score)
    print('mood_score: ', mood_score)
    print('recovery_score: ', recovery_score)

    if not sleep_score and not mood_score and not recovery_score:
        return "N/A"

    readiness_score = (sleep_score * weights['sleep'] + mood_score * weights['mood'] + recovery_score * weights['recovery'])
    return round(readiness_score, 1)

def calculate_sleep_quality(user):
    most_recent_wellness = DailyWellnessUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')
    
    most_recent_wellness = get_most_recent_instance_with_count(most_recent_wellness, 8)

    return get_wellness_score_by_q_name(user, most_recent_wellness.response, 'Sleep') if most_recent_wellness else "N/A"

def calculate_fatigue_score(user):
    most_recent_rpe = RPEUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')

    most_recent_rpe = get_most_recent_instance_with_count(most_recent_rpe, 14)

    return get_rpe_score_by_q_name(user, most_recent_rpe.response, 'Fatigue') if most_recent_rpe else "N/A"

def calculate_mood_score(user):
    most_recent_wellness = DailyWellnessUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')

    most_recent_wellness = get_most_recent_instance_with_count(most_recent_wellness, 8)

    return get_wellness_score_by_q_name(user, most_recent_wellness.response, 'Mood') if most_recent_wellness else "N/A"

def calculate_play_time(user):
    # data not available
    return 0
