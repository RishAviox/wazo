from django.urls import path
from .views import *

urlpatterns = [
    # update_wellness
    path("chat-wellness" , ChatwellnessAPIView.as_view() , name="chat-wellness"),
    # log_rpe
    path("chat-rpe" , RPEChatAPIView.as_view() , name="chat-rpe"),
    # how am i doing?
    path("wellness-overview" , WellnessOverviewAPIView.as_view() , name="wellness-overview"),
    
    # get all the events and goals
    path("calendar" , CalendarAPIView.as_view() , name="calendar"),
    
    # create event
    path("calendar-event" , CalendarEventAPIViewSet.as_view({'post': 'create'}), name="calendar-event-entry"),
    # Update and delete event
    path("calendar-event/<int:pk>" , CalendarEventAPIViewSet.as_view({
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name="calendar-event-entry"),
    
    # create goal
    path("calendar-goal" , CalendarGoalAPIViewSet.as_view({'post': 'create'}), name="calendar-goal-entry"),
    # Update and delete goal
    path("calendar-goal/<int:pk>" , CalendarGoalAPIViewSet.as_view({
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name="calendar-goal-entry"),
    
    path("game-overview" , GameOverviewAPIView.as_view() , name="game-overview"),
]