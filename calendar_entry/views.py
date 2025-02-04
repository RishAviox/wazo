from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from accounts.models import WajoUser
from .permissions import IsAdminUser
from calendar_entry.models import CalendarEventEntry, CalendarGoalEntry
from calendar_entry.serializers import (
    CalendarEventCreateSerializer,
    CalendarEventSerializer,
    CalendarGoalCreateSerializer,
    CalendarGoalSerializer
)


class CalendarEntryListView(APIView):
    def get(self, request, user_id):
        user = get_object_or_404(WajoUser, phone_no=user_id)
        response = {}
        events = CalendarEventEntry.objects.filter(user=user)
        serializer = CalendarEventSerializer(events, many=True)
        response["events"] = serializer.data
        goals = CalendarGoalEntry.objects.filter(user=user)
        serializer = CalendarGoalSerializer(goals, many=True)
        response["goals"] = serializer.data

        return Response(data=response)


class EventCreateView(generics.CreateAPIView):
    queryset = CalendarEventEntry.objects.all()
    serializer_class = CalendarEventCreateSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def perform_create(self, serializer):
        user = get_object_or_404(WajoUser, phone_no=self.request.data.get('user_id'))
        serializer.save(user=user)


class GoalCreateView(generics.CreateAPIView):
    queryset = CalendarGoalEntry.objects.all()
    serializer_class = CalendarGoalCreateSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def perform_create(self, serializer):
        user = get_object_or_404(WajoUser, phone_no=self.request.data.get('user_id'))
        serializer.save(user=user)


class EventRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CalendarEventEntry.objects.all()
    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_object(self):
        """
        Ensure that the user can only access their own operations.
        """
        user_id = self.kwargs['user_id']
        user = get_object_or_404(WajoUser, phone_no=user_id)
        obj = super().get_object()
        
        # Check if the authenticated user is the owner of the event
        if obj.user != user:
            raise PermissionDenied("You do not have permission to perform this operation.")
        
        return obj


class GoalRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CalendarGoalEntry.objects.all()
    serializer_class = CalendarGoalSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_object(self):
        """
        Ensure that the user can only access their own operations.
        """
        user_id = self.kwargs['user_id']
        user = get_object_or_404(WajoUser, phone_no=user_id)
        obj = super().get_object()
        
        # Check if the authenticated user is the owner of the event
        if obj.user != user:
            raise PermissionDenied("You do not have permission to perform this operation.")
        
        return obj
