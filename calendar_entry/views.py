from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from django.db.models import Q
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
        # Get the user object based on the phone number
        user = get_object_or_404(WajoUser, phone_no=user_id)
        
        # Initialize the response dictionary
        response = {}

        # Get start_date and end_date from query parameters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        repeat_type = request.query_params.get('repeat_type')
        custom_repeat = request.query_params.get('custom_repeat')

        # Convert start_date and end_date to datetime objects if they are provided
        try:
            if start_date:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError("Invalid date format. Use 'YYYY-MM-DD'.")

        # Filter events based on the user and date range
        event_query = Q(user=user)
        if start_date and end_date:
            event_query &= Q(date__gte=start_date, date__lte=end_date)
        if repeat_type:
            event_query &= Q(repeat=repeat_type)
        
        if custom_repeat:
            try:
                custom_repeat_days = eval(custom_repeat) # Ensure input safety
                event_query &= Q(custom_repeat__days=custom_repeat_days)
            except Exception as e:
                raise ValidationError("Invalid format for custom_repeat.")

        # Fetch and serialize events
        events = CalendarEventEntry.objects.filter(event_query)
        event_serializer = CalendarEventSerializer(events, many=True)
        response["events"] = event_serializer.data

        # Filter goals based on the user and date range
        goals = CalendarGoalEntry.objects.filter(user=user)
        if start_date and end_date:
            goals = goals.filter(start_date__gte=start_date, end_date__lte=end_date)
        goal_serializer = CalendarGoalSerializer(goals, many=True)
        response["goals"] = goal_serializer.data

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
