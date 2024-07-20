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
                    PlayerIDMapping, PerformanceMetrics, OffensivePerformanceMetrics,
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

                performance_metrics = calculate_performance_metrics(row)
                offensive_performance_metrics = calculate_offensive_performance_metrics(row)
                
                # print("performance_metrics: ", performance_metrics)
                print("offensive_performance_metrics: ", offensive_performance_metrics)

                # Create or update the performance metrics for the user
                PerformanceMetrics.objects.update_or_create(
                    user_id=user_id,
                    defaults={'metrics': performance_metrics}
                )

                # Create or update the Offensive performance metrics for the user
                OffensivePerformanceMetrics.objects.update_or_create(
                    user_id=user_id,
                    defaults={'metrics': offensive_performance_metrics}
                )
    except:
        print("Worksheet named 'PlayerStats_137183' not found")

