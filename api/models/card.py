from django.db import models

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
    