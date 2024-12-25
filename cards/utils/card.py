from django.utils.timezone import timedelta
from django.utils import timezone
from django.db.models import Sum, FloatField, ExpressionWrapper
from django.db.models.functions import Cast, Coalesce
from django.db.models.fields.json import KeyTextTransform
from django.utils.timezone import datetime


from ..models import *
from events.models import OneTimeEvents, RecurringEvents
from .status_metrics_calculations import *
from .gps import get_gps_athletic_skills_metrics, get_gps_football_abilities_metrics


from datetime import date

def calculate_age(dob):
    try:
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except Exception:
        return 25
    

# for status card
def get_status_card_metrics(user):
    try:
        metrics = StatusCardMetrics.objects.filter(user=user).latest('updated_on')
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
    print("one_time_events: ", list(one_time_events), recurring_events)
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
def calculate_wellness_metrics(instance):
    normalized_wellness_response = normalize_wellness_response(instance.response)

    def get_score_(metric):
        return str(round(normalized_wellness_response[metric], 2)) if normalized_wellness_response[metric] is not None else 0

    def get_overall_wellness_score(data):
        category = "Overall Wellness"
        return round(
            (float(data['Energy Level']) * STATUS_METRIC_WEIGHTS[category]['Energy Level'])  +
            (float(data['Muscle Soreness']) * STATUS_METRIC_WEIGHTS[category]['Muscle Soreness'])  +
            (float(data['Pain Level']) * STATUS_METRIC_WEIGHTS[category]['Pain Level']) +
            (float(data['Mood']) * STATUS_METRIC_WEIGHTS[category]['Mood']) +
            (float(data['Stress Level']) * STATUS_METRIC_WEIGHTS[category]['Stress Level']) +
            (float(data['Sleep Quality']) * STATUS_METRIC_WEIGHTS[category]['Sleep Quality']) +
            (float(data['Diet Quality']) * STATUS_METRIC_WEIGHTS[category]['Diet']), 2
        )
    
    data = {
        'Energy Level': get_score_('Energy Level'),
        'Muscle Soreness': get_score_('Muscle Soreness'),
        'Pain Level': get_score_('Pain Level'),
        'Mood': get_score_('Mood'),
        'Stress Level': get_score_('Stress Level'),
        'Sleep Quality': get_score_('Sleep Quality'),
        'Diet Quality': get_score_('Diet')
    }

    return { **data, 'Overall Wellness': str(get_overall_wellness_score(data)) }


def calculate_physical_readiness_metrics(instance, overall_wellness):
    group = ""
    question_id = instance.response[0]['question_id']
    if 'PT' in question_id:
        group = 'PT'
    elif 'TT' in question_id:
        group = 'TT'
    elif 'MS' in question_id:
        group = 'MS'

    normalized_rpe_response = normalize_rpe_response(instance.response)
    print("normalized_rpe_response: ", normalized_rpe_response)
    print("group: ", group)

    def get_score_(metric):
        return str(round(normalized_rpe_response[metric], 2)) if normalized_rpe_response[metric] is not None else 0
    
    def get_overall_readiness_score(data):
        category = "Readiness"
        return round(
            (float(data['Intensity']) * STATUS_METRIC_WEIGHTS[category]['Intensity'])  +
            (float(data['Fatigue']) * STATUS_METRIC_WEIGHTS[category]['Fatigue'])  +
            (float(data['Recovery']) * STATUS_METRIC_WEIGHTS[category]['Recovery']) +
            (overall_wellness * STATUS_METRIC_WEIGHTS[category]['Wellness']), 2
        )
    
    data = {
        'Intensity': get_score_(f'RPE-{group}-1'),
        'Fatigue': get_score_(f'RPE-{group}-2'),
        'Recovery': get_score_(f'RPE-{group}-3')
    }

    return { **data, 'Readiness': str(get_overall_readiness_score(data)) }



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

    defensive_value_mapping["Clearances"] = calculate_percentage(
        "aerial_clearance_succeeded",
        "aerial_clearance",
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
        "intercept": "Interceptions",
        "intervention": "Interventions",
        "block": "Blocks",
        "recovery": "Recoveries",
        "mistake": "Mistakes",
        "own_goal": "Own Goals"
    }

    # Rename the dict keys
    defensive_value_mapping = {
        rename_dict.get(k, k): v for k, v in defensive_value_mapping.items()
    }

    # Keys to keep
    keys_to_keep = (
        "Play time",
        "Game Rating",
        "Tackles",
        "Aerial Clearances",
        "Aerial Duels",
        "Ground Duels",
        "Loose Ball Duels",
        "Interceptions",
        "Interventions",
        "Clearances",
        "Blocks",
        "Shots Blocked",
        "Defensive Area Passes",
        "Defensive Line Support",
        "Recoveries",
        "Mistakes",
        "Own Goals"
    )

    # Filter defensive_value_mapping
    filtered_defensive_value_mapping = {k: str(defensive_value_mapping[k]) for k in keys_to_keep}
    
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
            # "performance-metrics": get_performance_metrics(user),
            # "defensive-performance-metrics": get_defensive_performance_metrics(user),
            # "offensive-performance-metrics": get_offensive_performance_metrics(user),
            "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        prompt = f"Generate a concise expert analysis for {role} only in {language} language based on the provided calendar data, highlighting key events, training sessions, rest periods, and suggesting reschedules for conflicts keeping games as immovable but suggest if athelete should play if their wellness scores are too low. Also look at other stats like wellness and other stats to set the priority for the user. Keep it under 20 words and avoid mentioning the data passed to you or atheletes and coaches. Please make sure to address the athelete in second person and not in third person.  Data provided: {user_data}.  Maximum 40 words. Example: 'Reschedule Team B training on July 20 due to potential conflicts. Let's focus on the upcoming game on July 19.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
        return prompt
    
    elif card == 'AttackingSkills':
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                player_data.append(get_attacking_skills_metrics(player))

            user_data = {
                'team-attacking-skills-metrics': player_data
            }
            print("team-attacking-skills-metrics for coach: ", user_data)
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided performance metrics for the team's attacking skills, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the coach. Data provided:{user_data}. Example: 'The team displays effective attacking movement and positioning but lacks finishing consistency. Focus on improving shot accuracy and decision-making in the final third. Suggested drills: Finishing Under Pressure, Quick Counter Attacks, and Off-the-Ball Runs.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                'attacking-skills-metrics': get_attacking_skills_metrics(user)
            }
            prompt = f"Generate a concise expert analysis for athletes only in {language} language based on the provided performance metrics, focusing on their attacking skills, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the player. Data provided:{user_data}. Example: 'Your attacking skills show strong movement and positioning, with solid goal contributions. Keep improving finishing accuracy and decision-making in the final third. Focus on drills for quick finishing and off-the-ball runs.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt

    elif card == 'VideocardDefensive':
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                player_data.append(get_videocard_defensive_metrics(player))

            user_data = {
                'team-defensive-skills-metrics': player_data
            }
            print("team-defensive-skills-metrics for coach: ", user_data)
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided performance metrics for the team's defensive skills, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the coach. Data provided:{user_data}. Example: 'The team demonstrates strong tackling and interception numbers but needs better defensive organization and discipline. Focus on improving defensive transitions and positioning. Suggested drills: Defensive Shape, 1v1 Defending, and Transition Defense.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                'defensive-skills-metrics': get_videocard_defensive_metrics(user)
            }
            prompt = f"Generate a concise expert analysis for athletes only in {language} language based on the provided performance metrics, focusing on their defensive skills, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the player. Data provided:{user_data}. Example: 'Your tackling and interception skills are strong, but work on improving positioning and defensive discipline. Focus on drills for 1v1 defending, marking, and maintaining shape during transitions.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt

    elif card == 'VideocardDistribution':
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                player_data.append(get_videocard_distributions_metrics(player))

            user_data = {
                'team-distribution-skills-metrics': player_data
            }
            print("team-distribution-skills-metrics for coach: ", user_data)
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided performance metrics for the team's distribution skills, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the coach. Data provided:{user_data}. Example: 'The team shows strong passing accuracy but struggles with long-range distribution and decision-making under pressure. Focus on drills for long passes, switching play, and building from the back.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                'distribution-skills-metrics': get_videocard_distributions_metrics(user)
            }
            prompt = f"Generate a concise expert analysis for athletes only in {language} language based on the provided performance metrics, focusing on their distribution skills, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the player. Data provided:{user_data}. Example: 'Your short passing is accurate, but improve decision-making for long passes and switches under pressure. Focus on drills for long-range passing and building from the back.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt

    elif card == 'AthleticSkills':
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                player_data.append(get_gps_athletic_skills_metrics(player))

            user_data = {
                'team-gps-athletic-skills-metrics': player_data
            }
            print("team-gps-athletic-skills-metrics for coach: ", user_data)
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided GPS athletic performance metrics for the team, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the coach. Data provided:{user_data}. Example: 'The team shows strong sprint speeds and distance covered but needs to improve acceleration and deceleration in high-pressure situations. Focus on drills for agility, quick burst sprints, and endurance training.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                'gps-athletic-skills-metrics': get_gps_athletic_skills_metrics(user)
            }
            prompt = f"Generate a concise expert analysis for athletes only in {language} language based on the provided GPS athletic performance metrics, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the player. Data provided:{user_data}. Example: 'Your top speed and distance covered are impressive, but work on improving acceleration and recovery during transitions. Focus on agility drills, quick sprints, and endurance.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt

    elif card == 'FootballAbilities':
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                player_data.append(get_gps_football_abilities_metrics(player))

            user_data = {
                'team-gps-football-abilities-metrics': player_data
            }
            print("team-gps-football-abilities-metrics for coach: ", user_data)
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided GPS football performance metrics for the team, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the coach. Data provided:{user_data}. Example: 'The team excels in high-speed running and covering distance, but needs improvement in recovery and positioning during transitions. Focus on drills for endurance, positioning, and quick directional changes.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                'gps-football-abilities-metrics': get_gps_football_abilities_metrics(user)
            }
            prompt = f"Generate a concise expert analysis for athletes only in {language} language based on the provided GPS football performance metrics, highlighting key strengths, areas for improvement, and suggesting targeted drills. Keep it under 40 words and avoid mentioning the data passed to you or athletes and coaches. Make sure the sentence can be directly sent to the player. Data provided:{user_data}. Example: 'You have strong high-speed runs and cover good distance, but work on improving your recovery speed and positioning in transitions. Focus on drills for endurance, agility, and quick direction changes.' {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
    
    elif card == 'VideoCard':
        today = datetime.today()
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                user_data = {
                        "wellness": get_status_card_metrics(player),
                        "calendar": get_daily_snapshot(player, today),
                        "defensive-skills-metrics":get_videocard_defensive_metrics(player),
                        "gps-football-abilities-metrics": get_gps_football_abilities_metrics(player),
                        'gps-athletic-skills-metrics': get_gps_athletic_skills_metrics(player),
                    }
                player_data.append(user_data)

            user_data = {
                'team-VideoCard': player_data
            }
            print("team-gps-football-abilities-metrics for coach: ", user_data)
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided calendar data, team wellness data, and offensive and defensive performance metrics. This is mandatory. Analyze the team’s last game and provide one key focus area for reviewing game footage. Also, consider wellness and other stats to set the priority for the team. Avoid mentioning the data passed to you or athletes and coaches. Data provided: {user_data}. Please make sure to address the coach directly. Maximum 40 words. {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                        "wellness": get_status_card_metrics(user),
                        "calendar": get_daily_snapshot(user, today),
                        "defensive-skills-metrics":get_videocard_defensive_metrics(user),
                        "gps-football-abilities-metrics": get_gps_football_abilities_metrics(user),
                        'gps-athletic-skills-metrics': get_gps_athletic_skills_metrics(user),
                    }
            user_data = {
                'player-VideoCard': user_data
            }
            prompt = f"Generate a concise expert analysis for athletes only in {language} language based on the provided calendar data, their wellness data, and offensive and defensive performance metrics. This is mandatory. Analyze their last game and provide one key focus area while watching their game footage. Also, consider wellness and other stats to set the priority for the user. Avoid mentioning the data passed to you or athletes and coaches. Data provided: {user_data}. Please make sure to address the athlete in second person and not in third person. Maximum 40 words. {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt

    elif card == 'TrainingCard':
        today = datetime.today()
        if user.role == 'Coach':
            player_data = []
            for player in user.players.all():
                user_data = {
                        "wellness": get_status_card_metrics(player),
                        "calendar": get_daily_snapshot(player, today),
                        "defensive-skills-metrics":get_videocard_defensive_metrics(player),
                        "gps-football-abilities-metrics": get_gps_football_abilities_metrics(player),
                        'gps-athletic-skills-metrics': get_gps_athletic_skills_metrics(player),
                    }
                player_data.append(user_data)

            user_data = {
                'team-VideoCard': player_data
            }
            prompt = f"Generate a concise expert analysis for coaches only in {language} language based on the provided calendar data, team wellness data, and offensive and defensive performance metrics. This is mandatory. Analyze the team’s last game and recommend one specific training area for the team. Consider wellness and other stats to set the training priorities. Avoid mentioning the data passed to you or athletes and coaches. Data provided: {json_data}. Address the coach directly. Maximum 40 words. {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt
        
        else:
            user_data = {
                        "wellness": get_status_card_metrics(user),
                        "calendar": get_daily_snapshot(user, today),
                        "defensive-skills-metrics":get_videocard_defensive_metrics(user),
                        "gps-football-abilities-metrics": get_gps_football_abilities_metrics(user),
                        'gps-athletic-skills-metrics': get_gps_athletic_skills_metrics(user),
                    }
            user_data = {
                'player-VideoCard': user_data
            }
            prompt = f"Generate a concise expert analysis for athletes only in {language} language based on the provided calendar data, their wellness data, and offensive and defensive performance metrics. This is mandatory. Analyze their last game and provide one key focus area while watching their game footage. Also, consider wellness and other stats to set the priority for the user. Avoid mentioning the data passed to you or athletes and coaches. Data provided: {user_data}. Please make sure to address the athlete in second person and not in third person. Maximum 40 words. {'Dont translate but think and respond in Hebrew.' if language == 'Hebrew' else ''}"
            return prompt

    return None
