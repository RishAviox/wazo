from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.db import models

from .models import WajoUser, OnboardingStep 
from .models import (
                    DailyWellnessUserResponse, 
                    DailyWellnessQuestionnaire,
                    RPEUserResponse
                )
from .serializer import StatusCardMetricsSerializer
from .utils import *


# auto create entrypoint
@receiver(post_save, sender=WajoUser)
def create_onboarding_entryflow(sender, instance, created, **kwargs):
    if created:
        OnboardingStep.objects.create(user=instance)


# we have JSON field as Response which stores partial or all 8 
# if partial for long time then schedule notification
# if all 8 are present then calculate metrics
@receiver(post_save, sender=DailyWellnessUserResponse)
def process_daily_wellness_responses(sender, instance, created, **kwargs):
    responses_count = len(instance.response) if instance.response else 0
    # number of questions(8) can be made dynamic
    if responses_count > 0 and responses_count < 8:
        # schedule notification in `Notification server`
        # get the latest, if less than for 30 minutes
        # schedule notification to inform user
        # here just skip it
        print("Responses count: ", responses_count)
    else:
        # create/save metrics table
        calculate_and_store_status_card_metrics(instance.user)

# 14 questions
@receiver(post_save, sender=RPEUserResponse)
def process_daily_wellness_responses(sender, instance, created, **kwargs):
    responses_count = len(instance.response) if instance.response else 0
    # number of questions(14) can be made dynamic
    if responses_count > 0 and responses_count < 14:
        # schedule notification in `Notification server`
        # get the latest, if less than for 30 minutes
        # schedule notification to inform user
        # here just skip it
        print("Responses count: ", responses_count)
    else:
        # create/save metrics table
        calculate_and_store_status_card_metrics(instance.user)




def calculate_and_store_status_card_metrics(user):
    metrics = {
        'user': user,
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
        metrics_serializer.save()

    