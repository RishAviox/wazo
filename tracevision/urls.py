from django.urls import path

from .views import TraceVisionProcessView

urlpatterns = [
    path('match-data/', TraceVisionProcessView.as_view(), name='match-data-create'),
]
