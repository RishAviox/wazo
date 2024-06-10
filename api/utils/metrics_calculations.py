from django.utils import timezone
from api.models import DailyWellnessUserResponse, RPEUserResponse, DailyWellnessQuestionnaire, RPEQuestionnaire


# some scores have reversed scale(5 is bad, 1 is good), 
# like Stress, Soreness, Fatigue, General Pain Level

NORMALIZED_SCORES_ID = ['WQ-4', 'WQ-6', 'WQ-7', 'RPE-TT-2', 'RPE-PT-2', 'RPE-MS-2'] # add fatigue from RPE

def normalize_score(question_id, score):
    """Normalize scores to ensure higher scores are consistently better across all questions."""
    if question_id in NORMALIZED_SCORES_ID:
        return 6 - int(score)  # Reverse the score: 5 becomes 1, 4 becomes 2, etc.
    return int(score)


# Helper function to extract score from JSON responses
def get_score_by_question_id(response, question_id):
    for item in response:
        if item['question_id'] == question_id:
            return normalize_score(question_id, item['answer_id'])
    return 0

def get_rpe_score_by_q_name(user, response, q_name):
    scores = []
    for item in response:
        question = RPEQuestionnaire.objects.filter(q_id=item['question_id'], language=user.selected_language).first()
        if question and q_name in question.name:
            scores.append(normalize_score(item['question_id'], item['answer_id']))
    scores_avg = sum(scores) / len(scores) if scores else 0
    return scores_avg

def get_wellness_score_by_q_name(user, response, q_name):
    scores = []
    for item in response:
        question = DailyWellnessQuestionnaire.objects.filter(q_id=item['question_id'], language=user.selected_language).first()
        if question and q_name in question.name:
            scores.append(normalize_score(item['question_id'], item['answer_id']))
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
        if len(instance.response) == 7:  # Ensure response count is 8
            wellness_scores.extend([normalize_score(item['question_id'], item['answer_id']) for item in instance.response])

    for instance in rpe_responses:
        if len(instance.response) == 14:  # Ensure response count is 14
            rpe_scores.extend([normalize_score(item['question_id'], item['answer_id']) for item in instance.response])

    print(wellness_scores)
    wellness_avg = sum(wellness_scores) / len(wellness_scores) if wellness_scores else 0
    rpe_avg = sum(rpe_scores) / len(rpe_scores) if rpe_scores else 0

    if not wellness_avg and not rpe_avg:
        return "NA"
    
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
    return "NA"

def calculate_readiness_score(user, weights={'sleep': 0.4, 'mood': 0.3, 'recovery': 0.3}):
    most_recent_wellness = DailyWellnessUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')

    most_recent_rpe = RPEUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')

    most_recent_wellness = get_most_recent_instance_with_count(most_recent_wellness, 7)
    most_recent_rpe = get_most_recent_instance_with_count(most_recent_rpe, 14)

    sleep_score = get_wellness_score_by_q_name(user, most_recent_wellness.response, 'Sleep') if most_recent_wellness else 0
    mood_score = get_wellness_score_by_q_name(user, most_recent_wellness.response, 'Mood') if most_recent_wellness else 0
    recovery_score = get_rpe_score_by_q_name(user, most_recent_rpe.response, 'Recovery') if most_recent_rpe else 0

    print('sleep_score: ', sleep_score)
    print('mood_score: ', mood_score)
    print('recovery_score: ', recovery_score)

    if not sleep_score and not mood_score and not recovery_score:
        return "NA"

    readiness_score = (sleep_score * weights['sleep'] + mood_score * weights['mood'] + recovery_score * weights['recovery'])
    return round(readiness_score, 1)

def calculate_sleep_quality(user):
    most_recent_wellness = DailyWellnessUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')
    
    most_recent_wellness = get_most_recent_instance_with_count(most_recent_wellness, 7)

    return get_wellness_score_by_q_name(user, most_recent_wellness.response, 'Sleep') if most_recent_wellness else "NA"

def calculate_fatigue_score(user):
    most_recent_rpe = RPEUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')

    most_recent_rpe = get_most_recent_instance_with_count(most_recent_rpe, 14)

    return get_rpe_score_by_q_name(user, most_recent_rpe.response, 'Fatigue') if most_recent_rpe else "NA"

def calculate_mood_score(user):
    most_recent_wellness = DailyWellnessUserResponse.objects.filter(
        user=user
    ).order_by('-updated_on')

    most_recent_wellness = get_most_recent_instance_with_count(most_recent_wellness, 7)

    return get_wellness_score_by_q_name(user, most_recent_wellness.response, 'Mood') if most_recent_wellness else "NA"

def calculate_play_time(user):
    # data not available
    return 0



# ****************** Individual Player Alerts **************************

def calculate_wellness_score(user, days=7):
    end_date = timezone.now()
    start_date = end_date - timezone.timedelta(days=days)
    wellness_responses = DailyWellnessUserResponse.objects.filter(
        user=user,
        updated_on__range=(start_date, end_date)
    )

    wellness_scores = []

    for instance in wellness_responses:
        if len(instance.response) == 7:  # Ensure response count is 8
            wellness_scores.extend([normalize_score(item['question_id'], item['answer_id']) for item in instance.response])

    wellness_avg = sum(wellness_scores) / len(wellness_scores) if wellness_scores else 0

    if not wellness_avg:
        return "NA"
    
    print("wellness scores and avg: ", wellness_scores, wellness_avg)

    return round(wellness_avg, 1)
