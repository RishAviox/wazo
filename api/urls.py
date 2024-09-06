from django.urls import path
from .views.auth import SendOTPAPI, LoginAPI, LogoutAPI, RefreshTokenAPI
from .views.chatbot_admin import (
                        AdminTokenObtainView, RPEUserResponseCreateView,
                        DailyWellnessUserResponseCreateView, 
                        RecurringEventsCreateView, OneTimeEventsCreateView,
                    )
from .views.onboarding import OnboardingAPI, OnboardingFlowEntrypoint
from .views.user import WajoUserProfileDetails, NotificationsAPI
from .views.card import (
                    CardSuggestedActionsAPI, ____CardSuggestedActionsAPI, ____StatusCardMetricAPI, StatusCardMetricAPI, DailySnapshortCardAPI, 
                    PerformanceMetricsAPI, DefensivePerformanceMetricsAPI, OffensivePerformanceMetricsAPI,
                    GreetingAPI, InsightAPI, VideoAnalysisCardAPI, GameStatsAPI, SeasonOverviewMetricsAPI,
                    WajoPerformanceIndexAPI
                )

urlpatterns = [
    path('auth/sendOTP', SendOTPAPI.as_view(), name='send-otp'),
    path('auth/login', LoginAPI.as_view(), name='login'),
    path('auth/logout', LogoutAPI.as_view(), name='logout'),
    path('auth/refresh', RefreshTokenAPI.as_view(), name='refresh'),
    path('onboarding/<str:field>', OnboardingAPI.as_view(), name='onboarding'),
    path('onboarding_flow/entrypoint', OnboardingFlowEntrypoint.as_view(), name='onboarding-flow-entrypoint'),
    path('user-details', WajoUserProfileDetails.as_view(), name='user-profile-details'),
    
    # old builds and v1
    path('card-suggested-actions/<str:card>', ____CardSuggestedActionsAPI.as_view(), name='____card-suggested-actions'),
    path('v1/card-suggested-actions', CardSuggestedActionsAPI.as_view(), name='card-suggested-actions'),
    
    # for old app builds, send dummy data, v1 is the latest one
    path('status-card-metrics', ____StatusCardMetricAPI.as_view(), name='____status-card-metrics'),
    path('v1/status-card-metrics', StatusCardMetricAPI.as_view(), name='status-card-metrics'),
    
    path('daily-snapshot', DailySnapshortCardAPI.as_view(), name='daily-snapshot'),
    path('performance-metrics', PerformanceMetricsAPI.as_view(), name='performance-metrics'),
    path('defensive-performance-metrics', DefensivePerformanceMetricsAPI.as_view(), name='defensive-performance-metrics'),
    path('offensive-performance-metrics', OffensivePerformanceMetricsAPI.as_view(), name='offensive-performance-metrics'),
    # openai greeting and insight
    path('greeting', GreetingAPI.as_view(), name='greeting'),
    path('insight/<str:card>', InsightAPI.as_view(), name='insight'),
    # video card
    path('video-analysis', VideoAnalysisCardAPI.as_view(), name='video-analysis'),
    # game stats
    path('game-stats', GameStatsAPI.as_view(), name='game-stats'),
    # season overiview metrics
    path('season-overview-metrics', SeasonOverviewMetricsAPI.as_view(), name='season-overview-metrics'),
    # wajo performance index metrics
    path('wajo-performance-index', WajoPerformanceIndexAPI.as_view(), name='wajo-performance-index-metrics'),
    path('notifications/<str:fcm_token>', NotificationsAPI.as_view(), name='wajo-notifications'),

    # obtain admin(staff) for chatbot to push data to API
    path('admin/login', AdminTokenObtainView.as_view(), name='admin_token_obtain'),
    path('admin/daily-wellness-response', DailyWellnessUserResponseCreateView.as_view(), name='create_daily_wellness_user_response'),
    path('admin/rpe-response', RPEUserResponseCreateView.as_view(), name='create_rpe_user_response'),
    path('admin/recurring-event', RecurringEventsCreateView.as_view(), name='create_recurring_event'),
    path('admin/one-time-event', OneTimeEventsCreateView.as_view(), name='create_one_time_event'),
]