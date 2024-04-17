from django.urls import path
from .views import RegisterAPI, SendOTPAPI, VerifyOTPAPI, LoginAPI
from .views import OnboardingAPI

urlpatterns = [
    path('auth/register', RegisterAPI.as_view(), name='register'),
    path('auth/sendOTP', SendOTPAPI.as_view(), name='send-otp'),
    path('auth/verifyOTP', VerifyOTPAPI.as_view(), name='verify-otp'),
    path('auth/login', LoginAPI.as_view(), name='login'),
    path('onboarding/<str:field>', OnboardingAPI.as_view(), name='onboarding'),
]