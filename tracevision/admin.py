from django.contrib import admin
from .models import TraceSession, TracePlayer
from core.admin import admin_site


class TraceSessionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'session_id', 'match_date',
        'home_team', 'away_team', 'home_score', 'away_score'
    ]
    search_fields = ['session_id', 'home_team', 'away_team']
    list_filter = ['match_date', 'home_team', 'away_team']


class TracePlayerAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'name', 'jersey_number', 'team',
        'position', 'session'
    ]
    search_fields = ['name', 'team', 'position']
    list_filter = ['team', 'position']


#  Register models to custom admin_site
admin_site.register(TraceSession, TraceSessionAdmin)
admin_site.register(TracePlayer, TracePlayerAdmin)