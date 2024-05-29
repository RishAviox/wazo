from django.db import models
from .user import WajoUser

# Card's Suggested Actions (redirect to chatbot) Model
class CardSuggestedAction(models.Model):
    card_name = models.CharField(max_length=100)
    action_title = models.CharField(max_length=255)
    action_note = models.TextField(null=True, blank=True)
    postback_name = models.CharField(max_length=255, null=True, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.action_title
    

# Status Card Metrics
class StatusCardMetrics(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='status_card_metrics')
    overall_score =  models.CharField(max_length=10, null=True, blank=True)
    srpe_score =  models.CharField(max_length=10, null=True, blank=True)
    readiness_score =  models.CharField(max_length=10, null=True, blank=True)
    sleep_quality =  models.CharField(max_length=10, null=True, blank=True)
    fatigue_score =  models.CharField(max_length=10, null=True, blank=True)
    mood_score =  models.CharField(max_length=10, null=True, blank=True)
    play_time =  models.CharField(max_length=10, null=True, blank=True)
     
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.user.phone_no

    