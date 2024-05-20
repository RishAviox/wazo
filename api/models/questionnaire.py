from django.db import models
from .user import WajoUser


# Daily Wellness Questionnaire
class DailyWellnessQuestionnaire(models.Model):
    q_id = models.CharField(max_length=10)
    name = models.CharField(max_length=50)
    language = models.CharField(max_length=10)
    description = models.TextField()
    question_to_ask = models.TextField()
    response_choices = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('q_id', 'language')

    def __str__(self):
        return f"{self.q_id} - {self.name}"


class DailyWellnessUserResponse(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='daily_wellness_user_response')
    question = models.ForeignKey(DailyWellnessQuestionnaire, on_delete=models.CASCADE)
    response = models.TextField()
    language = models.CharField(max_length=10)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name} - {self.question.name}"
    

# RPE Questionnaire
class RPEQuestionnaire(models.Model):
    q_id = models.CharField(max_length=20)
    after_session_type = models.CharField(max_length=100)
    name = models.CharField(max_length=50)
    language = models.CharField(max_length=10)
    description = models.TextField()
    question_to_ask = models.TextField()
    response_choices = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('q_id', 'language')

    def __str__(self):
        return f"{self.q_id} - {self.name}"


class RPEUserResponse(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='rpe_user_response')
    question = models.ForeignKey(RPEQuestionnaire, on_delete=models.CASCADE)
    response = models.TextField()
    language = models.CharField(max_length=10)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name} - {self.question.name}"
    
