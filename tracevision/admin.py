from django.contrib import admin
from .models import TraceSession, TracePlayer, TraceHighlight, TraceObject, TraceHighlightObject, TraceVisionPlayerStats, TraceVisionSessionStats, TraceCoachReportTeam, TraceTouchLeaderboard, TracePossessionSegment, TraceClipReel, TracePass, TracePassingNetwork
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
admin_site.register(TraceHighlight)
admin_site.register(TraceObject)
admin_site.register(TraceHighlightObject)



class TraceVisionPlayerStatsAdmin(admin.ModelAdmin):
    list_display = ['session', 'object_id', 'side', 'total_distance_meters', 'max_speed_mps', 'sprint_count', 'performance_score', 'last_calculated']
    list_filter = ['side', 'calculation_method', 'last_calculated']
    search_fields = ['object_id', 'session__session_id']
    readonly_fields = ['created_at', 'last_calculated']
    
    fieldsets = (
        ('Session & Object', {
            'fields': ('session', 'object_id', 'side')
        }),
        ('Movement Statistics', {
            'fields': ('total_distance_meters', 'avg_speed_mps', 'max_speed_mps', 'total_time_seconds')
        }),
        ('Sprint Analysis', {
            'fields': ('sprint_count', 'sprint_distance_meters', 'sprint_time_seconds')
        }),
        ('Position & Tactics', {
            'fields': ('avg_position_x', 'avg_position_y', 'position_variance')
        }),
        ('Performance Metrics', {
            'fields': ('performance_score', 'stamina_rating', 'work_rate', 'heatmap_data')
        }),
        ('Calculation Info', {
            'fields': ('calculation_method', 'calculation_version', 'last_calculated')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )


class TraceVisionSessionStatsAdmin(admin.ModelAdmin):
    list_display = ['session', 'total_tracking_points', 'data_coverage_percentage', 'quality_score', 'processing_status', 'created_at']
    list_filter = ['processing_status', 'quality_score', 'created_at']
    search_fields = ['session__session_id', 'session__home_team', 'session__away_team']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Session Information', {
            'fields': ('session',)
        }),
        ('Data Quality Metrics', {
            'fields': ('total_tracking_points', 'data_coverage_percentage', 'quality_score')
        }),
        ('Team Statistics', {
            'fields': ('home_team_stats', 'away_team_stats')
        }),
        ('Match Analysis', {
            'fields': ('possession_data', 'tactical_analysis')
        }),
        ('Processing Status', {
            'fields': ('processing_status', 'processing_errors')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )


class TraceCoachReportTeamAdmin(admin.ModelAdmin):
    list_display = ['session', 'side', 'goals', 'shots', 'passes', 'possession_time_s', 'created_at']
    list_filter = ['side']
    search_fields = ['session__session_id']


class TraceTouchLeaderboardAdmin(admin.ModelAdmin):
    list_display = ['session', 'object_id', 'object_side', 'touches', 'created_at']
    list_filter = ['object_side']
    search_fields = ['session__session_id', 'object_id']


class TracePossessionSegmentAdmin(admin.ModelAdmin):
    list_display = ['session', 'side', 'start_ms', 'end_ms', 'count', 'duration_s', 'created_at']
    list_filter = ['side']
    search_fields = ['session__session_id']


class TraceClipReelAdmin(admin.ModelAdmin):
    list_display = ['session', 'event_id', 'object_id', 'side', 'start_ms', 'duration_ms', 'label']
    list_filter = ['side']
    search_fields = ['session__session_id', 'event_id', 'object_id']


class TracePassAdmin(admin.ModelAdmin):
    list_display = ['session', 'side', 'from_object_id', 'to_object_id', 'start_ms', 'duration_ms']
    list_filter = ['side']
    search_fields = ['session__session_id', 'from_object_id', 'to_object_id']


class TracePassingNetworkAdmin(admin.ModelAdmin):
    list_display = ['session', 'side', 'from_object_id', 'to_object_id', 'passes_count']
    list_filter = ['side']
    search_fields = ['session__session_id', 'from_object_id', 'to_object_id']


# Register the new aggregate models with custom admin_site
admin_site.register(TraceVisionPlayerStats, TraceVisionPlayerStatsAdmin)
admin_site.register(TraceVisionSessionStats, TraceVisionSessionStatsAdmin)
admin_site.register(TraceCoachReportTeam, TraceCoachReportTeamAdmin)
admin_site.register(TraceTouchLeaderboard, TraceTouchLeaderboardAdmin)
admin_site.register(TracePossessionSegment, TracePossessionSegmentAdmin)
admin_site.register(TraceClipReel, TraceClipReelAdmin)
admin_site.register(TracePass, TracePassAdmin)
admin_site.register(TracePassingNetwork, TracePassingNetworkAdmin)
