from django.urls import path
from .views import *

urlpatterns = [
    path('entrypoint', OnboardingFlowEntrypoint.as_view(), name='onboarding-flow-entrypoint'),
    path('<str:field>', OnboardingAPI.as_view(), name='onboarding'),
]