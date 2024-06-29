from django.urls import path
from .views.auth import SendOTPAPI, LoginAPI, LogoutAPI, RefreshTokenAPI
from .views.chatbot_admin import AdminTokenObtainView, DailyWellnessUserResponseCreateView, RPEUserResponseCreateView
from .views.onboarding import OnboardingAPI, OnboardingFlowEntrypoint
from .views.user import WajoUserProfileDetails
from .views.card import CardSuggestedActionsAPI, StatusCardMetricAPI

urlpatterns = [
    path('auth/sendOTP', SendOTPAPI.as_view(), name='send-otp'),
    path('auth/login', LoginAPI.as_view(), name='login'),
    path('auth/logout', LogoutAPI.as_view(), name='logout'),
    path('auth/refresh', RefreshTokenAPI.as_view(), name='refresh'),
    path('onboarding/<str:field>', OnboardingAPI.as_view(), name='onboarding'),
    path('onboarding_flow/entrypoint', OnboardingFlowEntrypoint.as_view(), name='onboarding-flow-entrypoint'),
    path('user-details', WajoUserProfileDetails.as_view(), name='user-profile-details'),
    path('card-suggested-actions/<str:card>', CardSuggestedActionsAPI.as_view(), name='card-suggested-actions'),
    path('status-card-metrics', StatusCardMetricAPI.as_view(), name='status-card-metrics'),

    # obtain admin(staff) for chatbot to push data to API
    path('admin/login', AdminTokenObtainView.as_view(), name='admin_token_obtain'),
    path('admin/daily-wellness-response', DailyWellnessUserResponseCreateView.as_view(), name='create_daily_wellness_user_response'),
    path('admin/rpe-response', RPEUserResponseCreateView.as_view(), name='create_rpe_user_response'),
]