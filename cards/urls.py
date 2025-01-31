from django.urls import path
from .views import *

urlpatterns = [ 
    # greeting and insight
    path('greeting', GreetingAPI.as_view(), name='greeting'),
    path('insight/<str:card>/', InsightAPI.as_view(), name='insight'),

    # suggested actions for cards
    path('suggested-actions', CardSuggestedActionsAPI.as_view(), name='card-suggested-actions'),
    
    # card stats
    path('daily-snapshot', DailySnapshortCardAPI.as_view(), name='daily-snapshot'),    
    path('status-card-metrics', StatusCardMetricAPI.as_view(), name='status-card-metrics'),
    path('rpe-metrics', RPEMetricAPI.as_view(), name='rpe-metrics'),
    path('attacking-skills', AttackingSkillsAPI.as_view(), name='attacking-skills-metrics'),
    path('videocard-defensive', VideoCardDefensiveAPI.as_view(), name='videocard-defensive-metrics'),
    path('videocard-distributions', VideoCardDistributionsAPI.as_view(), name='videocard-distributions-metrics'),
    path('gps-athletic-skills', GPSAthleticSkillsAPI.as_view(), name='gps-athletic-skills-metrics'),
    path('gps-football-abilities', GPSFootballAbilitiesAPI.as_view(), name='gps-football-abilities-metrics'),
    
    # video card
    path('video-analysis', VideoAnalysisCardAPI.as_view(), name='video-analysis'),
    
    # video card
    path('video-card-json', VideoCardJSONAPI_Deprecated.as_view(), name='video-card-json'),
    path('v1/video-card-json', VideoCardJSONAPI.as_view(), name='video-card-json-v1'),
    
    # training card json
    path('training-card-json', TrainingCardJSONAPI.as_view(), name='training-card-json'),
    # news card json
    path('news-card-json', NewsCardJSONAPI.as_view(), name='news-card-json'),
]