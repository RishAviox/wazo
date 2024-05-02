from django.contrib import admin
from .models import WajoUser, APILog, OTPStore, OnboardingStep

# Register your models here.

class WajoUserAdmin(admin.ModelAdmin):
    list_display = ('phone_no', 'selected_language', 'fcm_token', 'created_on', 'updated_on', )

class APILogAdmin(admin.ModelAdmin):
    list_display = ['user', 'method', 'path', 'status_code', 'created_on']
    list_filter = ['method', 'status_code', 'created_on']
    search_fields = ['path']

class OTPStoreAdmin(admin.ModelAdmin):
    list_display = ['user', 'data', 'is_used', 'created_on']


class OnboardingFlowAdmin(admin.ModelAdmin):
    list_display = ['user', 'step', 'created_on', 'updated_on']


admin.site.register(WajoUser, WajoUserAdmin)
admin.site.register(APILog, APILogAdmin)
admin.site.register(OTPStore, OTPStoreAdmin)
admin.site.register(OnboardingStep, OnboardingFlowAdmin)