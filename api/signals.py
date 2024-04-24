from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import WajoUser, OnboardingStep


@receiver(post_save, sender=WajoUser)
def create_onboarding_entryflow(sender, instance, created, **kwargs):
    if created:
        OnboardingStep.objects.create(user=instance)