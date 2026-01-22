from django.contrib import admin
from .models import (
    TraceSession,
    TracePlayer,
    TraceHighlight,
    TraceObject,
    TraceHighlightObject,
    TraceVisionPlayerStats,
    TraceVisionSessionStats,
    TraceCoachReportTeam,
    TraceTouchLeaderboard,
    TracePossessionSegment,
    TraceClipReel,
    TracePass,
    TracePassingNetwork,
    TracePossessionStats,
    TraceClipReelShare,
    TraceClipReelComment,
    TraceClipReelCommentLike,
    TraceClipReelCommentEditHistory,
    TraceClipReelNote,
    TraceClipReelNoteShare,
)
from core.admin import admin_site


class TraceSessionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "session_id",
        "match_date",
        "age_group",
        "home_team",
        "away_team",
        "home_score",
        "away_score",
        "final_score",
        "status",
        "created_at",
    ]
    search_fields = ["session_id", "home_team__name", "away_team__name", "user__email"]
    list_filter = [
        "match_date",
        "age_group",
        "status",
        "home_team",
        "away_team",
        "created_at",
    ]
    readonly_fields = ["id", "created_at", "updated_at", "get_pitch_dimensions_display"]
    date_hierarchy = "match_date"

    fieldsets = (
        (
            "Session Information",
            {"fields": ("id", "user", "session_id", "match_date", "age_group")},
        ),
        (
            "Match Details",
            {
                "fields": (
                    "game",
                    "home_team",
                    "away_team",
                    "home_score",
                    "away_score",
                    "final_score",
                )
            },
        ),
        (
            "Pitch Configuration",
            {"fields": ("pitch_size", "get_pitch_dimensions_display")},
        ),
        (
            "Video & Data",
            {"fields": ("video_url", "blob_video_url", "start_time", "status")},
        ),
        (
            "Match Timing",
            {
                "fields": (
                    "match_start_time",
                    "first_half_end_time",
                    "second_half_start_time",
                    "match_end_time",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Game Statistics",
            {"fields": ("basic_game_stats",), "classes": ("collapse",)},
        ),
        ("Results & Storage", {"fields": ("result", "result_blob_url")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_pitch_dimensions_display(self, obj):
        """Display pitch dimensions in a readable format"""
        return obj.get_pitch_dimensions()

    get_pitch_dimensions_display.short_description = "Pitch Dimensions"


class TracePlayerAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "jersey_number",
        "team_name",
        "position",
        "sessions_count",
        "is_mapped",
        "created_at",
    ]
    search_fields = ["name", "object_id", "team__name", "position", "user__email"]
    list_filter = ["team", "position", "created_at"]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "is_mapped",
        "team_name",
        "sessions_count",
    ]
    date_hierarchy = "created_at"
    filter_horizontal = ["sessions"]

    fieldsets = (
        (
            "Player Information",
            {
                "fields": (
                    "id",
                    "object_id",
                    "name",
                    "jersey_number",
                    "position",
                    "language_metadata",
                )
            },
        ),
        (
            "Relationships",
            {"fields": ("sessions", "team", "user", "is_mapped", "sessions_count")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def sessions_count(self, obj):
        """Display the number of sessions this player participates in"""
        return obj.sessions.count()

    sessions_count.short_description = "Sessions"


class TraceHighlightAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "highlight_id",
        "video_id",
        "session",
        "player",
        "event_type",
        "match_time",
        "half",
        "start_offset",
        "duration",
        "created_at",
    ]
    search_fields = ["highlight_id", "session__session_id", "player__name"]
    list_filter = ["event_type", "source", "half", "session__match_date", "created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Highlight Information",
            {
                "fields": (
                    "id",
                    "highlight_id",
                    "video_id",
                    "start_offset",
                    "duration",
                    "video_time",
                )
            },
        ),
        (
            "Event Details",
            {
                "fields": (
                    "event_type",
                    "source",
                    "match_time",
                    "half",
                    "event_metadata",
                )
            },
        ),
        (
            "Performance Impact",
            {"fields": ("performance_impact", "team_impact"), "classes": ("collapse",)},
        ),
        ("Relationships", {"fields": ("session", "player")}),
        ("Media & Tags", {"fields": ("video_stream", "tags")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class TraceObjectAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "object_id",
        "type",
        "side",
        "role",
        "session",
        "player",
        "tracking_processed",
        "created_at",
    ]
    search_fields = [
        "object_id",
        "type",
        "side",
        "role",
        "session__session_id",
        "player__name",
    ]
    list_filter = [
        "type",
        "side",
        "role",
        "tracking_processed",
        "session__match_date",
        "created_at",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Object Information", {"fields": ("id", "object_id", "type", "side", "role")}),
        ("Relationships", {"fields": ("session", "player")}),
        (
            "Feature Vectors",
            {"fields": ("appearance_fv", "color_fv"), "classes": ("collapse",)},
        ),
        (
            "Tracking Data",
            {"fields": ("tracking_url", "tracking_blob_url", "tracking_processed")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class TraceHighlightObjectAdmin(admin.ModelAdmin):
    list_display = ["id", "highlight", "trace_object", "player", "created_at"]
    search_fields = [
        "highlight__highlight_id",
        "trace_object__object_id",
        "player__name",
    ]
    list_filter = ["created_at"]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Relationship Information",
            {"fields": ("id", "highlight", "trace_object", "player")},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class TraceVisionPlayerStatsAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "player",
        "side",
        "total_distance_meters",
        "max_speed_mps",
        "sprint_count",
        "performance_score",
        "last_calculated",
    ]
    list_filter = ["side", "calculation_method", "last_calculated"]
    search_fields = ["player__name", "session__session_id"]
    readonly_fields = ["created_at", "last_calculated"]

    fieldsets = (
        ("Session & Player", {"fields": ("session", "player", "side")}),
        (
            "Movement Statistics",
            {
                "fields": (
                    "total_distance_meters",
                    "avg_speed_mps",
                    "max_speed_mps",
                    "total_time_seconds",
                )
            },
        ),
        (
            "Sprint Analysis",
            {
                "fields": (
                    "sprint_count",
                    "sprint_distance_meters",
                    "sprint_time_seconds",
                )
            },
        ),
        (
            "Position & Tactics",
            {"fields": ("avg_position_x", "avg_position_y", "position_variance")},
        ),
        (
            "Performance Metrics",
            {
                "fields": (
                    "performance_score",
                    "stamina_rating",
                    "work_rate",
                    "heatmap_data",
                )
            },
        ),
        (
            "Calculation Info",
            {
                "fields": (
                    "calculation_method",
                    "calculation_version",
                    "last_calculated",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )


class TraceVisionSessionStatsAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "total_tracking_points",
        "data_coverage_percentage",
        "quality_score",
        "processing_status",
        "created_at",
    ]
    list_filter = ["processing_status", "quality_score", "created_at"]
    search_fields = ["session__session_id", "session__home_team", "session__away_team"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        ("Session Information", {"fields": ("session",)}),
        (
            "Data Quality Metrics",
            {
                "fields": (
                    "total_tracking_points",
                    "data_coverage_percentage",
                    "quality_score",
                )
            },
        ),
        ("Team Statistics", {"fields": ("home_team_stats", "away_team_stats")}),
        ("Match Analysis", {"fields": ("possession_data", "tactical_analysis")}),
        ("Processing Status", {"fields": ("processing_status", "processing_errors")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


class TraceCoachReportTeamAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "side",
        "goals",
        "shots",
        "passes",
        "possession_time_s",
        "created_at",
    ]
    list_filter = ["side", "created_at"]
    search_fields = ["session__session_id"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Team Information", {"fields": ("id", "session", "side")}),
        (
            "Match Statistics",
            {"fields": ("goals", "shots", "passes", "possession_time_s")},
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )


class TraceTouchLeaderboardAdmin(admin.ModelAdmin):
    list_display = ["session", "player", "object_side", "touches", "created_at"]
    list_filter = ["object_side", "created_at"]
    search_fields = ["session__session_id", "player__name"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Touch Information",
            {"fields": ("id", "session", "player", "object_side", "touches")},
        ),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )


class TracePossessionSegmentAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "side",
        "start_ms",
        "end_ms",
        "count",
        "duration_s",
        "highlight",
        "created_at",
    ]
    list_filter = ["side", "created_at", "highlight__event_type"]
    search_fields = ["session__session_id", "highlight__highlight_id"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Possession Information",
            {
                "fields": (
                    "id",
                    "session",
                    "side",
                    "start_ms",
                    "end_ms",
                    "count",
                    "duration_s",
                )
            },
        ),
        ("Highlight Association", {"fields": ("highlight",), "classes": ("collapse",)}),
        (
            "Clock Times",
            {"fields": ("start_clock", "end_clock"), "classes": ("collapse",)},
        ),
        ("Team Metrics", {"fields": ("team_metrics",), "classes": ("collapse",)}),
        ("Player Metrics", {"fields": ("player_metrics",), "classes": ("collapse",)}),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )


class TraceClipReelAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "ratio",
        "event_id",
        "video_type",
        "video_variant_name",
        "side",
        "primary_player",
        "generation_status",
        "is_generated",
        "created_at",
    ]
    list_filter = [
        "side",
        "video_type",
        "ratio",
        "generation_status",
        "event_type",
        "created_at",
    ]
    search_fields = [
        "session__session_id",
        "event_id",
        "ratio",
        "primary_player__name",
        "label",
    ]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "is_generated",
        "generation_duration",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Core Information",
            {
                "fields": (
                    "id",
                    "session",
                    "highlight",
                    "event_id",
                    "event_type",
                    "side",
                )
            },
        ),
        (
            "Video Details",
            {
                "fields": (
                    "video_type",
                    "ratio",
                    "video_variant_name",
                    "label",
                    "description",
                    "tags",
                )
            },
        ),
        ("Timing", {"fields": ("start_ms", "duration_ms", "start_clock", "end_clock")}),
        ("Players", {"fields": ("primary_player", "involved_players")}),
        (
            "Generation Status",
            {
                "fields": (
                    "generation_status",
                    "is_generated",
                    "generation_started_at",
                    "generation_completed_at",
                    "generation_duration",
                )
            },
        ),
        (
            "Video Files",
            {
                "fields": (
                    "video_url",
                    "video_thumbnail_url",
                    "video_size_mb",
                    "video_duration_seconds",
                )
            },
        ),
        ("Video Quality", {"fields": ("resolution", "frame_rate", "bitrate")}),
        (
            "Generation Metadata",
            {
                "fields": ("generation_errors", "generation_metadata"),
                "classes": ("collapse",),
            },
        ),
        ("Legacy", {"fields": ("video_stream",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    filter_horizontal = ["involved_players"]


class TracePassAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "side",
        "from_player",
        "to_player",
        "start_ms",
        "duration_ms",
        "created_at",
    ]
    list_filter = ["side", "created_at"]
    search_fields = ["session__session_id", "from_player__name", "to_player__name"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "created_at"


class TracePassingNetworkAdmin(admin.ModelAdmin):
    list_display = [
        "session",
        "side",
        "from_player",
        "to_player",
        "passes_count",
        "created_at",
    ]
    list_filter = ["side", "created_at"]
    search_fields = ["session__session_id", "from_player__name", "to_player__name"]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "created_at"


# Register all models with custom admin_site
class TracePossessionStatsAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "session",
        "possession_type",
        "side",
        "team",
        "player",
        "created_at",
    ]
    list_filter = ["possession_type", "side", "created_at", "session__match_date"]
    search_fields = [
        "session__session_id",
        "team__name",
        "player__name",
        "player__jersey_number",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Basic Information",
            {"fields": ("session", "possession_type", "side", "team", "player")},
        ),
        ("Metrics", {"fields": ("metrics",), "classes": ("collapse",)}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("session", "team", "player")


class TraceClipReelShareAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "clip_reel",
        "shared_by",
        "shared_with",
        "can_comment",
        "is_active",
        "shared_at",
    ]
    list_filter = ["can_comment", "is_active", "shared_at", "created_at"]
    search_fields = [
        "clip_reel__id",
        "shared_by__phone_no",
        "shared_by__name",
        "shared_with__phone_no",
        "shared_with__name",
    ]
    readonly_fields = ["id", "shared_at", "created_at", "updated_at"]
    date_hierarchy = "shared_at"

    fieldsets = (
        (
            "Share Information",
            {"fields": ("id", "clip_reel", "highlight", "shared_by", "shared_with")},
        ),
        ("Permissions", {"fields": ("can_comment", "is_active")}),
        (
            "Timestamps",
            {"fields": ("shared_at", "created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "clip_reel", "highlight", "shared_by", "shared_with"
        )


class TraceClipReelCommentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "clip_reel",
        "author",
        "visibility",
        "likes_count",
        "replies_count",
        "is_edited",
        "is_deleted",
        "created_at",
    ]
    list_filter = [
        "visibility",
        "is_edited",
        "is_deleted",
        "created_at",
        "updated_at",
    ]
    search_fields = [
        "content",
        "author__phone_no",
        "author__name",
        "clip_reel__id",
    ]
    readonly_fields = [
        "id",
        "likes_count",
        "replies_count",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Comment Information",
            {"fields": ("id", "clip_reel", "highlight", "author", "parent_comment")},
        ),
        ("Content", {"fields": ("content", "visibility", "mentions")}),
        (
            "Status",
            {
                "fields": (
                    "is_edited",
                    "is_deleted",
                    "deleted_at",
                    "likes_count",
                    "replies_count",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "clip_reel", "highlight", "author", "parent_comment"
        )


class TraceClipReelCommentLikeAdmin(admin.ModelAdmin):
    list_display = ["id", "comment", "user", "created_at"]
    list_filter = ["created_at"]
    search_fields = [
        "comment__id",
        "comment__content",
        "user__phone_no",
        "user__name",
    ]
    readonly_fields = ["id", "created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("Like Information", {"fields": ("id", "comment", "user")}),
        ("Timestamps", {"fields": ("created_at",), "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("comment", "user")


class TraceClipReelCommentEditHistoryAdmin(admin.ModelAdmin):
    list_display = ["id", "comment", "edited_by", "edited_at"]
    list_filter = ["edited_at"]
    search_fields = [
        "comment__id",
        "comment__content",
        "previous_content",
        "edited_by__phone_no",
        "edited_by__name",
    ]
    readonly_fields = ["id", "edited_at"]
    date_hierarchy = "edited_at"

    fieldsets = (
        ("Edit Information", {"fields": ("id", "comment", "edited_by", "edited_at")}),
        ("Content", {"fields": ("previous_content",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("comment", "edited_by")


class TraceClipReelNoteAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "clip_reel",
        "author",
        "is_deleted",
        "created_at",
        "updated_at",
    ]
    list_filter = ["is_deleted", "created_at", "updated_at", "author__role"]
    search_fields = [
        "content",
        "author__phone_no",
        "author__name",
        "clip_reel__id",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Note Information",
            {"fields": ("id", "clip_reel", "highlight", "author")},
        ),
        ("Content", {"fields": ("content",)}),
        ("Status", {"fields": ("is_deleted", "deleted_at")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "clip_reel", "highlight", "author"
        )


class TraceClipReelNoteShareAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "note",
        "shared_by",
        "shared_with_user",
        "shared_with_group",
        "is_active",
        "shared_at",
    ]
    list_filter = ["shared_with_group", "is_active", "shared_at"]
    search_fields = [
        "note__id",
        "note__content",
        "shared_by__phone_no",
        "shared_by__name",
        "shared_with_user__phone_no",
        "shared_with_user__name",
    ]
    readonly_fields = ["id", "shared_at"]
    date_hierarchy = "shared_at"

    fieldsets = (
        (
            "Share Information",
            {"fields": ("id", "note", "shared_by")},
        ),
        (
            "Share Target",
            {"fields": ("shared_with_user", "shared_with_group")},
        ),
        ("Status", {"fields": ("is_active", "shared_at")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "note", "shared_by", "shared_with_user"
        )


admin_site.register(TraceSession, TraceSessionAdmin)
admin_site.register(TracePlayer, TracePlayerAdmin)
admin_site.register(TraceHighlight, TraceHighlightAdmin)
admin_site.register(TraceObject, TraceObjectAdmin)
admin_site.register(TraceHighlightObject, TraceHighlightObjectAdmin)
admin_site.register(TraceVisionPlayerStats, TraceVisionPlayerStatsAdmin)
admin_site.register(TraceVisionSessionStats, TraceVisionSessionStatsAdmin)
admin_site.register(TraceCoachReportTeam, TraceCoachReportTeamAdmin)
admin_site.register(TraceTouchLeaderboard, TraceTouchLeaderboardAdmin)
admin_site.register(TracePossessionSegment, TracePossessionSegmentAdmin)
admin_site.register(TraceClipReel, TraceClipReelAdmin)
admin_site.register(TracePass, TracePassAdmin)
admin_site.register(TracePassingNetwork, TracePassingNetworkAdmin)
admin_site.register(TracePossessionStats, TracePossessionStatsAdmin)
admin_site.register(TraceClipReelShare, TraceClipReelShareAdmin)
admin_site.register(TraceClipReelComment, TraceClipReelCommentAdmin)
admin_site.register(TraceClipReelCommentLike, TraceClipReelCommentLikeAdmin)
admin_site.register(TraceClipReelCommentEditHistory, TraceClipReelCommentEditHistoryAdmin)
admin_site.register(TraceClipReelNote, TraceClipReelNoteAdmin)
admin_site.register(TraceClipReelNoteShare, TraceClipReelNoteShareAdmin)
