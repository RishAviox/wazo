from django.urls import path
from .views import (
    TraceVisionProcessesList, 
    TraceVisionProcessDetail, 
    TraceVisionProcessView, 
    TraceVisionProcessResultView, 
    TraceVisionPollStatusView, 
    TraceVisionSchedulerStatusView,
    TraceVisionSessionResultView,
    TraceVisionPlayerStatsView,
    TraceVisionPlayerStatsDetailView
)

urlpatterns = [
    path("processes/", TraceVisionProcessesList.as_view(), name="tracevision-processes-list"),
    path("processes/<int:pk>/", TraceVisionProcessDetail.as_view(), name="tracevision-processes-detail"),
    path("process/", TraceVisionProcessView.as_view(), name="tracevision-process"),
    path("process/result/<int:pk>/", TraceVisionProcessResultView.as_view(), name="tracevision-process-result"),
    path("process/poll/<int:pk>/", TraceVisionPollStatusView.as_view(), name="tracevision-poll-status"),
    path("session/result/<int:pk>/", TraceVisionSessionResultView.as_view(), name="tracevision-session-result"), # TODO: Remove this on prod
    path("scheduler/status/", TraceVisionSchedulerStatusView.as_view(), name="tracevision-scheduler-status"),
    
    # Player stats endpoints
    path('sessions/<int:pk>/stats/', TraceVisionPlayerStatsView.as_view(), name='player-stats'),
    path('sessions/<int:pk>/stats/<int:player_id>/', TraceVisionPlayerStatsDetailView.as_view(), name='player-stats-detail'),
]
