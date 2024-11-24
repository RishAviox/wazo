from django.urls import path
from .views import *

urlpatterns = [ 
    # greeting and insight
    path('greeting', GreetingAPI.as_view(), name='greeting'),
    path('insight/<str:card>', InsightAPI.as_view(), name='insight'),

    # suggested actions for cards
    path('suggested-actions', CardSuggestedActionsAPI.as_view(), name='card-suggested-actions'),
    
    # card stats
    path('daily-snapshot', DailySnapshortCardAPI.as_view(), name='daily-snapshot'),    
    path('status-card-metrics', StatusCardMetricAPI.as_view(), name='status-card-metrics'),
    path('attacking-skills', AttackingSkillsAPI.as_view(), name='attacking-skills-metrics'),
    path('videocard-defensive', VideoCardDefensiveAPI.as_view(), name='videocard-defensive-metrics'),
    path('videocard-distributions', VideoCardDistributionsAPI.as_view(), name='videocard-distributions-metrics'),
    path('gps-athletic-skills', GPSAthleticSkillsAPI.as_view(), name='gps-athletic-skills-metrics'),
    path('gps-football-abilities', GPSFootballAbilitiesAPI.as_view(), name='gps-football-abilities-metrics'),
    
    # video card
    path('video-analysis', VideoAnalysisCardAPI.as_view(), name='video-analysis'),
   
]