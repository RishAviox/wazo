from django.urls import path

from .views import TraceVisionProcessView, TraceVisionProcessesList, TraceVisionProcessDetail, TraceVisionPollStatusView

urlpatterns = [
    path('process/create/', TraceVisionProcessView.as_view(), name='match-data-create'),
    path("process/list/", TraceVisionProcessesList.as_view(), name="tracevision-list"),
    path("process/detail/<int:pk>/", TraceVisionProcessDetail.as_view(), name="tracevision-detail"),
    path("process/poll-status/<int:pk>/", TraceVisionPollStatusView.as_view(), name="tracevision-poll-status"),
    # path("process/result/<int:pk>/", TraceVisionProcessResultView.as_view(), name="tracevision-result"), # TODO: Create a API to check or the poll the result from the tracevision forcefully, when user want to check the result.
]
