from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import BeproMatchData, BeproEventData


class MatchOverviewAPIView(APIView):
    """
    API to return match overview including final score, summary, and smart note.
    """

    def get(self, request, match_id):
        # Fetch match data
        match_data = get_object_or_404(BeproMatchData, match_id=match_id)

        # Fetch match events
        events = BeproEventData.objects.filter(match_id=match_data)

        # Calculate statistics
        possession_percentage = 10 #NOTE
        turnovers = events.filter(event_type='turnover').count()
        set_piece_goals = events.filter(sub_event_type='set_piece', event_type='goal').count()

        response_data = {
            "matchOverview": {
                "finalScore": match_data.final_score(),
                "summary": "Coach, your team showcased strong control during this match. Despite defensive lapses, the ability to dominate possession and capitalize on key moments secured a crucial victory. Let’s delve into the analysis to refine and build on this performance.",
                "smartNote": generate_smart_note(possession_percentage, turnovers, set_piece_goals)
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)

    def generate_smart_note(self, possession, turnovers, set_piece_goals):
        return (
            f"Your team maintained {possession}% possession, showcasing midfield dominance. "
            f"However, {turnovers} turnovers exposed vulnerabilities, offering opportunities for counterattacks. "
        )
