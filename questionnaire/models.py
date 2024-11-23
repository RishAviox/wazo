from django.db import models
from accounts.models import WajoUser


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
    
    class Meta:
        verbose_name = "Daily Wellness Questionnaire"
        verbose_name_plural = "Daily Wellness Questionnaire"


class DailyWellnessUserResponse(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='daily_wellness_user_response')
    response = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name}"
    
    class Meta:
        verbose_name = "Daily Wellness User Response"
        verbose_name_plural = "Daily Wellness User Responses"
    

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
    
    class Meta:
        verbose_name = "RPE Questionnaire"
        verbose_name_plural = "RPE Questionnaire"


class RPEUserResponse(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='rpe_user_response')
    response = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name}"
    
    class Meta:
        verbose_name = "RPE User Response"
        verbose_name_plural = "RPE User Responses"
    

# Activities Questionnaire
# class ActivitiesQuestionnaire(models.Model):
#     activity_id = models.BigIntegerField()
#     language = models.CharField(max_length=10)

#     user_role = models.CharField(max_length=150, null=True, blank=True)
#     category = models.CharField(max_length=150, null=True, blank=True)
#     activity_type = models.CharField(max_length=150, null=True, blank=True)
#     event_description = models.TextField(null=True, blank=True)
#     description = models.TextField(null=True, blank=True)
#     duration = models.CharField(max_length=150, null=True, blank=True)
#     typical_time = models.CharField(max_length=150, null=True, blank=True)
#     warnings_or_considerations = models.TextField(null=True, blank=True)
#     icon = models.CharField(max_length=150, null=True, blank=True)

#     created_on = models.DateTimeField(auto_now_add=True)
#     updated_on = models.DateTimeField(auto_now=True)

#     def __str__(self):
#         return str(self.activity_id)
    
#     class Meta:
#         verbose_name = "Activities Questionnaire"
#         verbose_name_plural = "Activities Questionnaire"
    

# Q&A Table for Schedule Planning
class SchedulePlanningQuestionnaire(models.Model):
    question_id = models.CharField(max_length=20)
    step = models.IntegerField()
    language = models.CharField(max_length=10)

    user_role = models.CharField(max_length=150, null=True, blank=True)
    age = models.CharField(max_length=150, null=True, blank=True)
    category = models.CharField(max_length=150, null=True, blank=True)
    question = models.TextField(null=True, blank=True)
    response_type = models.CharField(max_length=150, null=True, blank=True)
    options_or_instructions = models.TextField(null=True, blank=True)

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.question_id)
    
    class Meta:
        verbose_name = "Schedule Planning Questionnaire"
        verbose_name_plural = "Schedule Planning Questionnaire"
    

class SchedulePlanningResponse(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='shchedule_planning_response')
    response = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name}"
    
    class Meta:
        verbose_name = "Schedule Planning User Response"
        verbose_name_plural = "Schedule Planning User Responses"
    
