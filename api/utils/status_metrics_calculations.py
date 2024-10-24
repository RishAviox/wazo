from django.utils import timezone
from api.models import DailyWellnessUserResponse, RPEUserResponse, DailyWellnessQuestionnaire, RPEQuestionnaire

from .calculation_weights import STATUS_METRIC_WEIGHTS

SESSION_DURATION = 60
"""
    Team Training 90mins
    Persornal Training 60mins
    Match Session will come from Bepro
"""

question_mapping = {
    'WQ-1': 'Mood',
    'WQ-2': 'Sleep Quality',
    'WQ-3': 'Energy Level',
    'WQ-4': 'Muscle Soreness',
    'WQ-5': 'Diet',
    'WQ-6': 'Stress Level',
    'WQ-7': 'Pain Level',
    'WQ-8': 'Pain Location',
}


# some scores have reversed scale(5 is bad, 1 is good), 
# like Stress, Soreness, Fatigue, General Pain Level
NORMALIZED_SCORES_ID = ['WQ-4', 'WQ-6', 'WQ-7', 'RPE-TT-1', 'RPE-TT-2', 'RPE-PT-1', 'RPE-PT-2', 'RPE-MS-1', 'RPE-MS-2'] # added fatigue & intensity from RPE

def normalize_score(question_id, score):
    """Normalize scores to ensure higher scores are consistently better across all questions."""
    denominator = 5
    if question_id in NORMALIZED_SCORES_ID:
        return ((6 - int(score)) / denominator) * 100  # Reverse the score: 5 becomes 1, 4 becomes 2, etc.
    if question_id == 'WQ-2': # Sleep Quality = (Hours Slept / 9) * 100
        denominator = 9
    return (int(score) / denominator) * 100


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

# Convert answer IDs to normalized values for wellness
def normalize_wellness_response(response):
    _data = {}
    for item in response:
        question_id = item["question_id"]
        score = int(item["answer_id"])
        normalized_score = normalize_score(question_id, score)
        factor = question_mapping[question_id]
        _data[factor] = normalized_score

        # print(f"{factor} ---> score: {score}, normalized: {normalized_score}")
    return _data

def normalize_rpe_response(response):
    _data = {}
    for item in response:
        question_id = item["question_id"]
        score = int(item["answer_id"])
        normalized_score = normalize_score(question_id, score)
        _data[question_id] = normalized_score
    return _data

# ****************** Helper Scores **************************


# ****************** StatusCard Metrics **************************

def calculate_wellness_score(normalized_wellness_response, weights=STATUS_METRIC_WEIGHTS):
    category = "Overall Wellness"
    return (
        (normalized_wellness_response['Mood'] * weights[category]['Mood'] if normalized_wellness_response['Mood'] is not None else 0) +
        (normalized_wellness_response['Sleep Quality'] * weights[category]['Sleep Quality'] if normalized_wellness_response['Sleep Quality'] is not None else 0) +
        (normalized_wellness_response['Energy Level'] * weights[category]['Energy Level'] if normalized_wellness_response['Energy Level'] is not None else 0) +
        (normalized_wellness_response['Muscle Soreness'] * weights[category]['Muscle Soreness'] if normalized_wellness_response['Muscle Soreness'] is not None else 0) +
        (normalized_wellness_response['Diet'] * weights[category]['Diet'] if normalized_wellness_response['Diet'] is not None else 0) +
        (normalized_wellness_response['Stress Level'] * weights[category]['Stress Level'] if normalized_wellness_response['Stress Level'] is not None else 0) +
        (normalized_wellness_response['Pain Level'] * weights[category]['Pain Level'] if normalized_wellness_response['Pain Level'] is not None else 0)
    )
    # denominator = sum(
    #     weights[category][factor] 
    #     for factor in weights[category] 
    #     if factor in normalized_wellness_response and normalized_wellness_response[factor] is not None
    # )

    # return (numerator / denominator) * age_adjustment_factor if denominator else None


def calculate_normalized_rpe_score(normalized_rpe_response, age_adjustment_factor=1.0, weights=STATUS_METRIC_WEIGHTS):
    """
        Intensity question in the RPE Questionnaire 
        (
            RPE-TT-1 for Team Training, RPE-PT-1 for Personal Training, 
            or RPE-MS-1 for Match Session
        ).
    As per the discussion on 13/08/2024, remove RPE & sRPE. Moved to Next Phase
    
    rpe = normalized_rpe_response["RPE-PT-1"] if normalized_rpe_response["RPE-PT-1"] else 0
    print("rpe: ", rpe)
    return (((rpe - 1) * (20 - 6) / (5 - 1)) + 6 - 6) * (100 / (20 - 6)) * age_adjustment_factor
    """
    # category = "RPE"
    # rpe = normalized_rpe_response["RPE-PT-1"] * weights[category]["RPE"] if normalized_rpe_response["RPE-PT-1"] else 0
    # print("rpe: ", rpe)
    # return (((rpe - 1) * (20 - 6) / (5 - 1)) + 6 - 6) * (100 / (20 - 6)) * age_adjustment_factor
    return 0

def calculate_normalized_srpe_score(rpe_score):
    """
    srpe = rpe_score * SESSION_DURATION # (in minutes) for now constant, later from GPS data
    return (srpe * 2.0) * 10.0 * age_adjustment_factor
    """
    srpe = rpe_score * SESSION_DURATION
    return (srpe / 10) * 100


def calculate_readiness_score(normalized_rpe_response, normalized_wellness_response, weights=STATUS_METRIC_WEIGHTS):
    category = "Readiness"
    
    return (
        (normalized_rpe_response['RPE-PT-2'] * weights[category]['Fatigue'] if normalized_rpe_response['RPE-PT-2'] is not None else 0) +
        (normalized_wellness_response['Sleep Quality'] * weights[category]['Sleep Quality'] if normalized_wellness_response['Sleep Quality'] is not None else 0) +
        (normalized_wellness_response['Muscle Soreness'] * weights[category]['Muscle Soreness'] if normalized_wellness_response['Muscle Soreness'] is not None else 0)
    )
    
    # Calculate denominator
    # denominator = (
        # (weights["RPE"]["RPE"] if rpe_score is not None else 0) +
        # (weights["sRPE"]["SRPE"] if srpe_score is not None else 0) +
    #     (weights[category]['Intensity'] if 'RPE-PT-1' in normalized_rpe_response and normalized_rpe_response['RPE-PT-1'] is not None else 0) +
    #     (weights[category]['Fatigue'] if 'RPE-PT-2' in normalized_rpe_response and normalized_rpe_response['RPE-PT-2'] is not None else 0) +
    #     (weights[category]['Recovery'] if 'RPE-PT-3' in normalized_rpe_response and normalized_rpe_response['RPE-PT-3'] is not None else 0) +
    #     (weights[category]['Performance'] if 'RPE-PT-5' in normalized_rpe_response and normalized_rpe_response['RPE-PT-5'] is not None else 0) +
    #     (weights[category]['Satisfaction'] if 'RPE-PT-4' in normalized_rpe_response and normalized_rpe_response['RPE-PT-4'] is not None else 0)
    # )
    
    # return (numerator / denominator) * age_adjustment_factor if denominator else None


def calculate_self_evaluation(normalized_rpe_response, weights=STATUS_METRIC_WEIGHTS):
    category = "Self Evaluation"
    return (
        (weights[category]['Performance'] if 'RPE-PT-5' in normalized_rpe_response and normalized_rpe_response['RPE-PT-5'] is not None else 0) +
        (weights[category]['Satisfaction'] if 'RPE-PT-4' in normalized_rpe_response and normalized_rpe_response['RPE-PT-4'] is not None else 0)
    )


def calculate_recovery_score(normalized_rpe_response, normalized_wellness_response, weights=STATUS_METRIC_WEIGHTS):
    category = "Recovery"
    return (
        (normalized_wellness_response['Sleep Quality'] * weights[category]['Sleep Quality'] if normalized_wellness_response['Sleep Quality'] is not None else 0) +
        (normalized_wellness_response['Muscle Soreness'] * weights[category]['Muscle Soreness'] if normalized_wellness_response['Muscle Soreness'] is not None else 0) +
        (normalized_rpe_response['RPE-PT-3'] * weights[category]['Recovery'] if normalized_rpe_response['RPE-PT-3'] is not None else 0)
    )
    # denominator = (
    #     (weights[category]['Fatigue'] if 'RPE-PT-2' in normalized_rpe_response and normalized_rpe_response['RPE-PT-2'] is not None else 0) +
    #     (weights[category]['Recovery'] if 'RPE-PT-3' in normalized_rpe_response and normalized_rpe_response['RPE-PT-3'] is not None else 0) +
    #     (weights[category]['Sleep Quality'] if 'Sleep Quality' in normalized_wellness_response and normalized_wellness_response['Sleep Quality'] is not None else 0) +
    #     (weights[category]['Muscle Soreness'] if 'Muscle Soreness' in normalized_wellness_response and normalized_wellness_response['Muscle Soreness'] is not None else 0)
    # )
    # return (numerator / denominator) * age_adjustment_factor if denominator else None


def calculate_fitness_score(normalized_rpe_response, normalized_wellness_response, distance_covered, high_intensity_runs, play_time=SESSION_DURATION, age_adjustment_factor=1.0, weights=STATUS_METRIC_WEIGHTS):
    category = "Recovery"
    recovery_score = calculate_recovery_score(normalized_rpe_response, normalized_wellness_response, age_adjustment_factor)
    gps_data = ((distance_covered + high_intensity_runs) / play_time) * 90
    numerator = (
        (recovery_score * weights[category]['Recovery'] if recovery_score is not None else 0) +
        (normalized_wellness_response['Energy Level'] * weights["Overall Wellness"]['Energy Level'] if normalized_wellness_response['Energy Level'] is not None else 0) +
        (gps_data * 1)  # Assuming GPS Data has a weight of 1
    )
    denominator = (
        (weights[category]['Recovery'] if recovery_score is not None else 0) +
        (weights["Overall Wellness"]['Energy Level'] if normalized_wellness_response['Energy Level'] is not None else 0) +
        (1)
    )
    return (numerator / denominator) * age_adjustment_factor


def calculate_morale_score(normalized_wellness_response, weights=STATUS_METRIC_WEIGHTS):
    category = "Overall Wellness"
    return (
        normalized_wellness_response['Mood'] * weights[category]['Mood'] +
        normalized_wellness_response['Stress Level'] * weights[category]['Stress Level']
    )
    # denominator = weights[category]['Mood'] + weights[category]['Stress Level']
    # return (numerator / denominator) * age_adjustment_factor

def calculate_spi_score(normalized_rpe_response, age_adjustment_factor=1.0, weights=STATUS_METRIC_WEIGHTS):
    category = "Subjective Performance Index"
    # Performance for Athlete is 0
    numerator = (
        (0 * weights[category]['Performance'] ) +
        (normalized_rpe_response['RPE-PT-4'] * weights[category]['Satisfaction'] if normalized_rpe_response['RPE-PT-4'] is not None else 0) +
        (normalized_rpe_response['RPE-PT-1'] * weights[category]['Intensity'] if normalized_rpe_response['RPE-PT-1'] is not None else 0)
    )
    denominator = weights[category]['Satisfaction'] + weights[category]['Intensity']

    return (numerator / denominator) * age_adjustment_factor if denominator else None


def calculate_overall_status(overall_wellness_score, readiness_score, spi_score, recovery_score, weights=STATUS_METRIC_WEIGHTS):
    category = "Athlete Status"
    numerator = (
        overall_wellness_score * weights[category]['Overall Wellness'] +
        readiness_score * weights[category]['Readiness'] +
        spi_score * weights[category]['Subjective Performance Index (SPI)'] +
        recovery_score * weights[category]['Recovery']
    )
    denominator = sum(weights[category].values())
    return round(numerator / denominator, 2)