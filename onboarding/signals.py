from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import WajoUser
from .models import OnboardingStep 


# auto create entrypoint
@receiver(post_save, sender=WajoUser)
def create_onboarding_entryflow(sender, instance, created, **kwargs):
    print("Signal triggered: Onboard Entrypoint Creator")
    if created:
        OnboardingStep.objects.create(user=instance)