from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TraceVisionProcessesList,
    TraceVisionProcessDetail,
    TraceVisionProcessView,
    TraceVisionPollStatusView,
    TraceVisionPlayerStatsView,
    TraceVisionPlayerStatsDetailView,
    GetTracePlayerReelsView,
    GetAvailableHighlightDatesView,
    CoachViewSpecificTeamPlayers,
    LinkUserToGameView,
    GenerateHighlightClipReelView,
    MapUserToPlayerView,
    DeleteErroredTraceSessionView,
    GetPlayerByTokenView,
    HighlightNotesView,
    TraceClipReelViewSet,
    TraceClipReelCommentViewSet,
    TraceClipReelNoteViewSet,
    GameUsersListView,
    SessionHighlightsView,
    BulkHighlightShareView,
)


# Create router for ViewSets
router = DefaultRouter()
router.register(r"clip-reels", TraceClipReelViewSet, basename="clipreel")
router.register(r"comments", TraceClipReelCommentViewSet, basename="comment")
router.register(r"notes", TraceClipReelNoteViewSet, basename="note")

urlpatterns = [
    path(
        "process/",
        TraceVisionProcessesList.as_view(),
        name="tracevision-processes-list-create",
    ),
    path(
        "process/create/",
        TraceVisionProcessView.as_view(),
        name="tracevision-process-create",
    ),
    path(
        "process/<int:pk>/",
        TraceVisionProcessDetail.as_view(),
        name="tracevision-processes-detail",
    ),
    path(
        "process/<int:pk>/",
        DeleteErroredTraceSessionView.as_view(),
        name="tracevision-process-delete-error",
    ),
    path(
        "process/poll-status/<int:pk>/",
        TraceVisionPollStatusView.as_view(),
        name="tracevision-poll-status",
    ),
    # Player stats endpoints
    path(
        "process/<int:pk>/stats/",
        TraceVisionPlayerStatsView.as_view(),
        name="player-stats",
    ),
    path(
        "process/<int:pk>/stats/<int:player_id>/",
        TraceVisionPlayerStatsDetailView.as_view(),
        name="player-stats-detail",
    ),
    path(
        "highlights/<int:session_id>/",
        GetTracePlayerReelsView.as_view(),
        name="player-reels",
    ),
    path(
        "highlights/dates/",
        GetAvailableHighlightDatesView.as_view(),
        name="available-highlight-dates",
    ),
    path(
        "coach/players/", CoachViewSpecificTeamPlayers.as_view(), name="coach-players"
    ),
    path("link-user-to-game/", LinkUserToGameView.as_view(), name="link-user-to-game"),
    path(
        "highlights/generate/",
        GenerateHighlightClipReelView.as_view(),
        name="generate-highlight-clip-reel",
    ),
    path(
        "players/map-user/",
        MapUserToPlayerView.as_view(),
        name="map-user-to-player",
    ),
    path(
        "players/by-token/",
        GetPlayerByTokenView.as_view(),
        name="get-player-by-token",
    ),
    # Highlight notes endpoint
    path(
        "highlights/<int:highlight_id>/notes/",
        HighlightNotesView.as_view(),
        name="highlight-notes",
    ),
    # Session users list endpoint
    path(
        "sessions/<int:session_id>/users/",
        GameUsersListView.as_view(),
        name="session-users-list",
    ),
    # Session highlights endpoint with role-based filtering
    path(
        "sessions/<int:session_id>/highlights/",
        SessionHighlightsView.as_view(),
        name="session-highlights",
    ),
    # Bulk highlight sharing endpoint
    path(
        "highlights/share/",
        BulkHighlightShareView.as_view(),
        name="bulk-highlight-share",
    ),
    # Include router URLs for ClipReel comment system
    path("", include(router.urls)),
]
