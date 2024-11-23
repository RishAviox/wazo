from django.urls import path
from .views import *

urlpatterns = [
    path('<str:field>', OnboardingAPI.as_view(), name='onboarding'),
    path('entrypoint', OnboardingFlowEntrypoint.as_view(), name='onboarding-flow-entrypoint'),
]