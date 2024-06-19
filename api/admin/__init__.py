from django.contrib import admin
from ..models import (
                    WajoUser, APILog, OTPStore, 
                    OnboardingStep, WajoUserDevice,
                    DailyWellnessQuestionnaire, DailyWellnessUserResponse,
                    RPEQuestionnaire, RPEUserResponse,
                    CardSuggestedAction, StatusCardMetrics,
                )   

from .customize import admin_site

# Register your models here.

class WajoUserAdmin(admin.ModelAdmin):
    list_display = ('phone_no', 'selected_language', 'role', 'created_on', 'updated_on', )

class APILogAdmin(admin.ModelAdmin):
    list_display = ['user', 'method', 'path', 'status_code', 'created_on']
    list_filter = ['method', 'status_code', 'created_on']
    search_fields = ['path']

class OTPStoreAdmin(admin.ModelAdmin):
    list_display = ['phone_no', 'data', 'is_used', 'created_on']


class OnboardingFlowAdmin(admin.ModelAdmin):
    list_display = ['user', 'step', 'created_on', 'updated_on']

class WajoUserDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'fcm_token', 'created_on', 'updated_on']

class DailyWellnessQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['q_id', 'name', 'language', 'description', 'created_on', 'updated_on']


class DailyWellnessUserResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'response', 'created_on', 'updated_on']


class RPEQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['q_id', 'name', 'after_session_type', 'language', 'description', 'created_on', 'updated_on']


class RPEUserResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'response', 'created_on', 'updated_on']


class CardSuggestedActionAdmin(admin.ModelAdmin):
    list_display = ['card_name', 'action_title', 'postback_name', 'action_note', 'created_on', 'updated_on']


class StatusCardMetricsAdmin(admin.ModelAdmin):
    list_display = ['user', 'overall_score', 'srpe_score', 'readiness_score', 'sleep_quality', 
                    'fatigue_score', 'mood_score', 'play_time', 'created_on', 'updated_on']


admin_site.register(WajoUser, WajoUserAdmin)
admin_site.register(APILog, APILogAdmin)
admin_site.register(OTPStore, OTPStoreAdmin)
admin_site.register(OnboardingStep, OnboardingFlowAdmin)
admin_site.register(WajoUserDevice, WajoUserDeviceAdmin)
admin_site.register(DailyWellnessQuestionnaire, DailyWellnessQuestionnaireAdmin)
admin_site.register(DailyWellnessUserResponse, DailyWellnessUserResponseAdmin)
admin_site.register(RPEQuestionnaire, RPEQuestionnaireAdmin)
admin_site.register(RPEUserResponse, RPEUserResponseAdmin)
admin_site.register(CardSuggestedAction, CardSuggestedActionAdmin)
admin_site.register(StatusCardMetrics, StatusCardMetricsAdmin)