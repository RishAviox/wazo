from django.db import models
from accounts.models import WajoUser

# Track EntryPoint
class OnboardingStep(models.Model):
    user = models.OneToOneField(WajoUser, primary_key=True, on_delete=models.CASCADE, related_name='onboarding_step')
    step = models.CharField(max_length=10, default='PQ1')
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.phone_no} is at step {self.step}"
    
    class Meta:
        verbose_name = "Onboarding Flow"
        verbose_name_plural = "Onboarding Flow"
