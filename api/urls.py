from django.urls import path
from .views.auth import SendOTPAPI, LoginAPI, LogoutAPI
from .views.onboarding import OnboardingAPI, OnboardingFlowEntrypoint
from .views.user import WajoUserProfileDetails

urlpatterns = [
    path('auth/sendOTP', SendOTPAPI.as_view(), name='send-otp'),
    path('auth/login', LoginAPI.as_view(), name='login'),
    path('auth/logout', LogoutAPI.as_view(), name='logout'),
    path('onboarding/<str:field>', OnboardingAPI.as_view(), name='onboarding'),
    path('onboarding_flow/entrypoint', OnboardingFlowEntrypoint.as_view(), name='onboarding-flow-entrypoint'),
    path('user-details', WajoUserProfileDetails.as_view(), name='user-profile-details'),
]