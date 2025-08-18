from django.urls import path

from .views import (
    TraceVisionProcessView, 
    TraceVisionProcessesList, 
    TraceVisionProcessDetail, 
    TraceVisionPollStatusView, 
    TraceVisionSchedulerStatusView,
    TraceVisionSessionResultView
)

urlpatterns = [
    path('process/create/', TraceVisionProcessView.as_view(), name='match-data-create'),
    path("process/list/", TraceVisionProcessesList.as_view(), name="tracevision-list"),
    path("process/detail/<int:pk>/", TraceVisionProcessDetail.as_view(), name="tracevision-detail"),
    path("process/poll-status/<int:pk>/", TraceVisionPollStatusView.as_view(), name="tracevision-poll-status"),
    path("session/result/<int:pk>/", TraceVisionSessionResultView.as_view(), name="tracevision-session-result"), # TODO: Remove this on prod
    path("scheduler/status/", TraceVisionSchedulerStatusView.as_view(), name="tracevision-scheduler-status"),
]
