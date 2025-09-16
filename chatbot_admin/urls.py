from django.urls import path
from .views import *


urlpatterns = [
    # obtain admin(staff) for chatbot to push data to API
    path('daily-wellness-response', DailyWellnessUserResponseCreateView.as_view(), name='create_daily_wellness_user_response'),
    path('login', AdminTokenObtainView.as_view(), name='admin_token_obtain'),
    path('rpe-response', RPEUserResponseCreateView.as_view(), name='create_rpe_user_response'),
    path('recurring-event', RecurringEventsCreateView.as_view(), name='create_recurring_event'),
    path('one-time-event', OneTimeEventsCreateView.as_view(), name='create_one_time_event'),
]