from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

from calendar_entry.models import CalendarEventEntry, CalendarGoalEntry
from calendar_entry.serializers import (
    CalendarEventCreateSerializer,
    CalendarEventSerializer,
    CalendarGoalCreateSerializer,
    CalendarGoalSerializer
)


class EventListCreateView(generics.ListCreateAPIView):
    queryset = CalendarEventEntry.objects.all()
    serializer_class = CalendarEventCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class GoalListCreateView(generics.ListCreateAPIView):
    queryset = CalendarGoalEntry.objects.all()
    serializer_class = CalendarGoalCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class EventRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CalendarEventEntry.objects.all()
    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """
        Ensure that the user can only access their own operations.
        """
        obj = super().get_object()
        
        # Check if the authenticated user is the owner of the event
        if obj.user != self.request.user:
            raise PermissionDenied("You do not have permission to modify this operation.")
        
        return obj


class GoalRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CalendarGoalEntry.objects.all()
    serializer_class = CalendarGoalSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """
        Ensure that the user can only access their own operations.
        """
        obj = super().get_object()
        
        # Check if the authenticated user is the owner of the event
        if obj.user != self.request.user:
            raise PermissionDenied("You do not have permission to modify this operation.")
        
        return obj
