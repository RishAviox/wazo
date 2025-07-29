from django.urls import path
from .views import MatchDataTracevisionListCreateView, MatchDataTracevisionDetailView

urlpatterns = [
    path('match-data/', MatchDataTracevisionListCreateView.as_view(), name='match-data-list-create'),
    path('match-data/<int:pk>/', MatchDataTracevisionDetailView.as_view(), name='match-data-detail'),
]
