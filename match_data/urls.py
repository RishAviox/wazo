from django.urls import path
from .views import *

urlpatterns = [ 
    # greeting and insight
    path('overview/<str:user_id>', MatchOverviewAPIView.as_view(), name='match-overview'),
    path('key_tactical_insight_report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'key_tactical_insight_report'})),
    path('individual_player_performance_report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'individual_player_performance'})),
    path('team_performance_report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'team_performance_report'})),
    path('set_piece_analysis_report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'set_piece_analysis_report'})),
    path('fitness_recovery_suggestion/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'fitness_recovery_suggestion'})),
    path('training_recommendation_report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'training_recommendation_report'}))
]