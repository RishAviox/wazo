from django.contrib import admin
from .models import *
from core.admin import admin_site


class OnboardingFlowAdmin(admin.ModelAdmin):
    list_display = ['user', 'step', 'created_on', 'updated_on']


admin_site.register(OnboardingStep, OnboardingFlowAdmin)