from django.urls import path
from .views.auth import SendOTPAPI, LoginAPI, LogoutAPI
from .views.onboarding import OnboardingAPI, OnboardingFlowEntrypoint
from .views.user import WajoUserProfileDetails
from .views.card import CardSuggestedActionsAPI

urlpatterns = [
    path('auth/sendOTP', SendOTPAPI.as_view(), name='send-otp'),
    path('auth/login', LoginAPI.as_view(), name='login'),
    path('auth/logout', LogoutAPI.as_view(), name='logout'),
    path('onboarding/<str:field>', OnboardingAPI.as_view(), name='onboarding'),
    path('onboarding_flow/entrypoint', OnboardingFlowEntrypoint.as_view(), name='onboarding-flow-entrypoint'),
    path('user-details', WajoUserProfileDetails.as_view(), name='user-profile-details'),
    path('card-suggested-actions/<str:card>', CardSuggestedActionsAPI.as_view(), name='card-suggested-actions'),
]