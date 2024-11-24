from django.contrib import admin
import os
from .models import *
from core.admin import admin_site

class DailyWellnessQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['q_id', 'name', 'language', 'description', 'created_on', 'updated_on']


class DailyWellnessUserResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'response', 'created_on', 'updated_on']


class RPEQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['q_id', 'name', 'after_session_type', 'language', 'description', 'created_on', 'updated_on']


class RPEUserResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'response', 'created_on', 'updated_on']



class SchedulePlanningQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['question_id', 'language', 'user_role', 'age', 'category', 'created_on', 'updated_on']


class SchedulePlanningResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'response', 'created_on', 'updated_on']


admin_site.register(DailyWellnessQuestionnaire, DailyWellnessQuestionnaireAdmin)
admin_site.register(DailyWellnessUserResponse, DailyWellnessUserResponseAdmin)
admin_site.register(RPEQuestionnaire, RPEQuestionnaireAdmin)
admin_site.register(RPEUserResponse, RPEUserResponseAdmin)
admin_site.register(SchedulePlanningQuestionnaire, SchedulePlanningQuestionnaireAdmin)
admin_site.register(SchedulePlanningResponse, SchedulePlanningResponseAdmin)