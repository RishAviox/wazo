from django.urls import path
from .views import *

urlpatterns = [ 
    # greeting and insight
    path('overview/<str:user_id>', MatchOverviewAPIView.as_view(), name='match-overview'),
    path('key-tactical-insight-report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'key_tactical_insight_report'})),
    path('individual-player-performance-report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'individual_player_performance'})),
    path('team-performance-report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'team_performance_report'})),
    path('set-piece-analysis-report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'set_piece_analysis_report'})),
    path('fitness-recovery-suggestion/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'fitness_recovery_suggestion'})),
    path('training-recommendation-report/<str:user_id>', MatchOverviewAPIViewset.as_view({'get': 'training_recommendation_report'})),
    path('match-summary/<str:user_id>', MatchSummaryView.as_view(), name='match_summary')
]