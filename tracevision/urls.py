from django.urls import path
from .views import (
    TraceVisionProcessesList, 
    TraceVisionProcessDetail, 
    TraceVisionProcessView,
    TraceVisionPollStatusView, 
    TraceVisionPlayerStatsView,
    TraceVisionPlayerStatsDetailView,
    GetTracePlayerReelsView,
    CoachViewSpecificTeamPlayers,
)

urlpatterns = [
    path("process/", TraceVisionProcessesList.as_view(), name="tracevision-processes-list-create"),
    path("process/create/", TraceVisionProcessView.as_view(), name="tracevision-process-create"),
    path("process/<int:pk>/", TraceVisionProcessDetail.as_view(), name="tracevision-processes-detail"),
    path("process/poll-status/<int:pk>/", TraceVisionPollStatusView.as_view(), name="tracevision-poll-status"),
    
    # Player stats endpoints
    path('process/<int:pk>/stats/', TraceVisionPlayerStatsView.as_view(), name='player-stats'),
    path('process/<int:pk>/stats/<int:player_id>/', TraceVisionPlayerStatsDetailView.as_view(), name='player-stats-detail'),
    path('highlights/', GetTracePlayerReelsView.as_view(), name='player-reels'),
    path('coach/players/', CoachViewSpecificTeamPlayers.as_view(), name='coach-players'),
]
