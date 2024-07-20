from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import models
import pandas as pd

from .models import WajoUser, OnboardingStep 
from .models import (
                    DailyWellnessUserResponse, 
                    DailyWellnessQuestionnaire,
                    RPEUserResponse,
                    MatchEventsDataFile,
                    PlayerIDMapping, PerformanceMetrics,
                )
from .serializer import StatusCardMetricsSerializer
from .utils import *


# auto create entrypoint
@receiver(post_save, sender=WajoUser)
def create_onboarding_entryflow(sender, instance, created, **kwargs):
    print("Signal triggered: Onboard Entrypoint Creator")
    if created:
        OnboardingStep.objects.create(user=instance)


# we have JSON field as Response which stores partial or all 8 
# if partial for long time then schedule notification
# if all 8 are present then calculate metrics
# remove PainLocation, so now count is 7
@receiver(post_save, sender=DailyWellnessUserResponse, weak=False)
def process_daily_wellness_responses(sender, instance, created, **kwargs):
    print("Signal triggered: DailyWellness User Response")
    responses_count = len(instance.response) if instance.response else 0
    # number of questions(7) can be made dynamic
    if responses_count > 0 and responses_count < 7:
        # schedule notification in `Notification server`
        # get the latest, if less than for 30 minutes
        # schedule notification to inform user
        # here just skip it
        print("but responses count is: ", responses_count)
    else:
        # create/save metrics table
        calculate_and_store_status_card_metrics(instance.user)

# 14 questions
@receiver(post_save, sender=RPEUserResponse, weak=False)
def process_rpe_responses(sender, instance, created, **kwargs):
    print("Signal triggered: RPE User Response")
    responses_count = len(instance.response) if instance.response else 0
    # number of questions(14) can be made dynamic
    if responses_count > 0 and responses_count < 14:
        # schedule notification in `Notification server`
        # get the latest, if less than for 30 minutes
        # schedule notification to inform user
        # here just skip it
        print("but responses count is: ", responses_count)
    else:
        # create/save metrics table
        calculate_and_store_status_card_metrics(instance.user)




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

    

# match event data signal
@receiver(post_save, sender=MatchEventsDataFile, weak=False)
def process_file(sender, instance, created, **kwargs):
    print("Match Events Data File Signal is called.")

    try:
        # Read sheet_name='PlayerStats_137183'
        stats_sheet = pd.read_excel(instance.file, sheet_name='PlayerStats_137183')

        player_mappings = PlayerIDMapping.objects.select_related('user').all().values('player_id', 'user__phone_no')
        player_mapping_dict = {mapping['player_id']: mapping['user__phone_no'] for mapping in player_mappings}
        
        print("player_mapping_dict: ", player_mapping_dict)

        # Process each row in the DataFrame
        for _, row in stats_sheet.iterrows():
            player_id = row['player_id']
            player_id = str(int(player_id))
            if player_id in player_mapping_dict:
                print(int(player_id))
                user_id = player_mapping_dict[player_id]
                metrics_data = {
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
                    # Add more fields as necessary
                }
                print("metrics_data: ", metrics_data)

                # Create or update the performance metrics for the user
                PerformanceMetrics.objects.update_or_create(
                    user_id=user_id,
                    defaults={'metrics': metrics_data}
                )
    except:
        print("Worksheet named 'PlayerStats_137183' not found")

