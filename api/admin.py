from django.contrib import admin
from .models import (
                    WajoUser, APILog, OTPStore, 
                    OnboardingStep, WajoUserDevice,
                    DailyWellnessQuestionnaire, DailyWellnessUserResponse,
                    RPEQuestionnaire, RPEUserResponse,
                )   

# Register your models here.

class WajoUserAdmin(admin.ModelAdmin):
    list_display = ('phone_no', 'selected_language', 'created_on', 'updated_on', )

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
    list_display = ['user', 'question', 'response', 'language', 'created_on', 'updated_on']


class RPEQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['q_id', 'name', 'after_session_type', 'language', 'description', 'created_on', 'updated_on']


class RPEUserResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'question', 'response', 'language', 'created_on', 'updated_on']


admin.site.register(WajoUser, WajoUserAdmin)
admin.site.register(APILog, APILogAdmin)
admin.site.register(OTPStore, OTPStoreAdmin)
admin.site.register(OnboardingStep, OnboardingFlowAdmin)
admin.site.register(WajoUserDevice, WajoUserDeviceAdmin)
admin.site.register(DailyWellnessQuestionnaire, DailyWellnessQuestionnaireAdmin)
admin.site.register(DailyWellnessUserResponse, DailyWellnessUserResponseAdmin)
admin.site.register(RPEQuestionnaire, RPEQuestionnaireAdmin)
admin.site.register(RPEUserResponse, RPEUserResponseAdmin)