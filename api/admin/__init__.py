from django.contrib import admin
import os

from ..models import (
                    WajoUser, APILog, OTPStore, PlayerIDMapping,
                    OnboardingStep, WajoUserDevice,
                    DailyWellnessQuestionnaire, DailyWellnessUserResponse,
                    RPEQuestionnaire, RPEUserResponse,
                    CardSuggestedAction, StatusCardMetrics, PerformanceMetrics,
                    DefensivePerformanceMetrics, OffensivePerformanceMetrics,
                    # ActivitiesQuestionnaire, 
                    SchedulePlanningQuestionnaire, SchedulePlanningResponse, 
                    RecurringEvents, OneTimeEvents, MatchEventsDataFile,
                    GameStats, SeasonOverviewMetrics,
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
    list_display = ['user', 'metrics', 'created_on', 'updated_on']


# class ActivitiesQuestionnaireAdmin(admin.ModelAdmin):
#     list_display = ['activity_id', 'language', 'user_role', 'category', 'icon', 'created_on', 'updated_on']


class SchedulePlanningQuestionnaireAdmin(admin.ModelAdmin):
    list_display = ['question_id', 'language', 'user_role', 'age', 'category', 'created_on', 'updated_on']


class SchedulePlanningResponseAdmin(admin.ModelAdmin):
    list_display = ['user', 'response', 'created_on', 'updated_on']


class RecurringEventsAdmin(admin.ModelAdmin):
    list_display = ['user', 'event_type', 'event', 'date', 'frequency', 'created_on', 'updated_on']


class OneTimeEventsAdmin(admin.ModelAdmin):
    list_display = ['user', 'event_type', 'event', 'date', 'created_on', 'updated_on']


class MatchEventsDataFileAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_filename', 'notes', 'created_on', 'updated_on']

    def get_filename(self, obj):
        return os.path.basename(obj.file.name)
    get_filename.short_description = 'File'


class PlayerIDMappingAdmin(admin.ModelAdmin):
    list_display = ['user', 'player_id', 'created_on', 'updated_on']


class PerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

class DefensivePerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

class OffensivePerformanceMetricsAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

class GameStatsAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

class SeasonOverviewMetricsAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

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
# admin_site.register(ActivitiesQuestionnaire, ActivitiesQuestionnaireAdmin)
admin_site.register(SchedulePlanningQuestionnaire, SchedulePlanningQuestionnaireAdmin)
admin_site.register(SchedulePlanningResponse, SchedulePlanningResponseAdmin)
admin_site.register(RecurringEvents, RecurringEventsAdmin)
admin_site.register(OneTimeEvents, OneTimeEventsAdmin)
admin_site.register(MatchEventsDataFile, MatchEventsDataFileAdmin)
admin_site.register(PlayerIDMapping, PlayerIDMappingAdmin)
admin_site.register(PerformanceMetrics, PerformanceMetricsAdmin)
admin_site.register(DefensivePerformanceMetrics, DefensivePerformanceMetricsAdmin)
admin_site.register(OffensivePerformanceMetrics, OffensivePerformanceMetricsAdmin)
admin_site.register(GameStats, GameStatsAdmin)
admin_site.register(SeasonOverviewMetrics, SeasonOverviewMetricsAdmin)