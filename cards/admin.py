from django.contrib import admin

from .models import *
from core.admin import admin_site


class StatusCardMetricsAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

class AttackingSkillsAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

class VideoCardDefensiveAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

class VideoCardDistributionsAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

class GPSAthleticSkillsAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']

class GPSFootballAbilitiesAdmin(admin.ModelAdmin):
    list_display = ['user', 'metrics', 'created_on', 'updated_on']


admin_site.register(StatusCardMetrics, StatusCardMetricsAdmin)
admin_site.register(AttackingSkills, AttackingSkillsAdmin)
admin_site.register(VideoCardDefensive, VideoCardDefensiveAdmin)
admin_site.register(VideoCardDistributions, VideoCardDistributionsAdmin)
admin_site.register(GPSAthleticSkills, GPSAthleticSkillsAdmin)
admin_site.register(GPSFootballAbilities, GPSFootballAbilitiesAdmin)