from django.urls import path

from .views import TraceVisionProcessView, TraceVisionProcessesList, TraceVisionProcessDetail

urlpatterns = [
    path('process/create/', TraceVisionProcessView.as_view(), name='match-data-create'),
    path("process/list/", TraceVisionProcessesList.as_view(), name="tracevision-list"),
    path("process/detail/<int:pk>/", TraceVisionProcessDetail.as_view(), name="tracevision-detail"),
]
