from django.urls import path

from calendar_entry.views import (
    EventCreateView,
    CalendarEntryListView,
    GoalCreateView,
    EventRetrieveUpdateDestroyView,
    GoalRetrieveUpdateDestroyView
)


urlpatterns = [
    path('entry/<str:user_id>', CalendarEntryListView.as_view(), name='calendar-entry-list'),
    path('event/', EventCreateView.as_view(), name='calendar-event-list-create'),
    path('goal/', GoalCreateView.as_view(), name='calendar-goal-list-create'),
    path(
        'event/<str:user_id>/<int:pk>/',
        EventRetrieveUpdateDestroyView.as_view(),
        name='calendar-event-retrieve-update-destroy'
    ),
    path(
        'goal/<str:user_id>/<int:pk>/',
        GoalRetrieveUpdateDestroyView.as_view(),
        name='calendar-goal-retrieve-update-destroy'
    ),
]
