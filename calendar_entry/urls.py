from django.urls import path

from calendar_entry.views import (
    EventListCreateView,
    GoalListCreateView,
    EventRetrieveUpdateDestroyView,
    GoalRetrieveUpdateDestroyView
)


urlpatterns = [
    path('event/', EventListCreateView.as_view(), name='calendar-event-list-create'),
    path('goal/', GoalListCreateView.as_view(), name='calendar-goal-list-create'),
    path(
        'event/<int:pk>/',
        EventRetrieveUpdateDestroyView.as_view(),
        name='calendar-event-retrieve-update-destroy'
    ),
    path(
        'goal/<int:pk>/',
        GoalRetrieveUpdateDestroyView.as_view(),
        name='calendar-goal-retrieve-update-destroy'
    ),
]
