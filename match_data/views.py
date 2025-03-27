from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.viewsets import ModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny

from .permissions import IsAdminUser
from .models import *
from .utils import (
    get_match, get_match_details,
    get_key_match_events,
    generate_key_match_events_obj,
    get_my_team,
    generate_performance_metric_obj,
    get_player_rating,
    get_strengths_and_weakness,
    get_tactical_adjustments,
    get_tactical_formation_breakdown,
    get_next_steps,
    get_final_score,
    get_latest_game,
    get_player,
    get_historical_context,
    MatchSummaryReport,
    KeyTacticalInsightReport,
    IndividualPlayerPerformanceReport,
    TeamPerformanceReport,
    SetPieceAnalysisReport,
    FitnessRecoverySuggestion,
    TrainingRecommendationReport
)


class MatchOverviewAPIView(APIView):
    """
    API to return match overview including final score, summary, and smart note.
    """
    permission_classes = [IsAdminUser]
    def get(self, request, user_id):
        # Fetch match data
        try:
            response_data = {}
            player = get_player(user_id)
            my_team = get_my_team(player)
            latest_match = get_latest_game(team=my_team)
            match_data = get_match(match_id=latest_match.id)
            if my_team:
                response_data["matchOverview"] = {
                    "finalScore": get_final_score(match_data, my_team),
                    "summary": "Coach, your team showcased strong control during this match. Despite defensive lapses, the ability to dominate possession and capitalize on key moments secured a crucial victory. Let’s delve into the analysis to refine and build on this performance.",
                    "smartNote": "Your team maintained 68% possession, showcasing midfield dominance. However, 64 turnovers exposed vulnerabilities, offering opportunities for counterattacks. This match also marked the third consecutive game where your team conceded from a set piece—defensive organization on dead-ball situations needs urgent attention."
                }

                response_data["historicalContext"] = get_historical_context(match_data, my_team)    # TODO: Need to be dynamic on basis of historical data

            event_data = get_match_details(match=match_data)

            events = get_key_match_events(events=event_data)

            # Making key match events object
            event_list: list = generate_key_match_events_obj(events)

            response_data["keyMatchEvents"] = {
                "events": event_list,
                "momentOfTheMatch": "Player A’s stunning free-kick goal in the 87th minute showcased exceptional set-piece preparation and was decisive for the win."
            }

            if my_team:
                team_stats = generate_performance_metric_obj(team=my_team, match=match_data)

                response_data["performanceMetrics"] = {
                    "metrics": team_stats
                }
            
            player_ratings = get_player_rating()
            response_data["playerRatings"] = {
                "ratings": player_ratings,
                "standoutPerformers": {
                    "playerA": "Delivered in key moments with precision and composure.",
                    "playerB": "Orchestrated the game’s tempo through sharp passing.",
                    "playerC": "Kept the defensive line organized under pressure."
                },
                "areasOfImprovement": {
                    "playerD": "Missed key tackles; focus on defensive positioning.",
                    "playerE": "Distribution accuracy requires refinement."
                }
            }

            analysis = get_strengths_and_weakness()
            tactical_adjustments = get_tactical_adjustments()

            response_data["tacticalAnalysisAndAdjustments"] = {
                "analysis": analysis,
                "forOurTeam": tactical_adjustments['forOurTeam'],
                "forOpponent": tactical_adjustments['forOpponent']
            }

            response_data["tacticalFormationBreakdown"] = get_tactical_formation_breakdown()
            response_data["whatsNext"] = get_next_steps()

            return Response(response_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Something went wrong", "detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def generate_smart_note(self, possession, turnovers):
        return (
            f"Your team maintained {possession}% possession, showcasing midfield dominance. "
            f"However, {turnovers} turnovers exposed vulnerabilities, offering opportunities for counterattacks. "
        )


class MatchOverviewAPIViewset(ModelViewSet):

    permission_classes = [IsAdminUser]

    @action(detail=True, methods=['GET'])
    def key_tactical_insight_report(self, request, user_id: str):
        report = KeyTacticalInsightReport()
        insight_report = {"KeyTacticalInsightsReport": report.get_tactical_insights_report()}
        return Response(data=insight_report, status=status.HTTP_200_OK)


    @action(detail=False, methods=["GET"])
    def individual_player_performance(self, request, user_id: str):
        report = IndividualPlayerPerformanceReport()
        individual_player_performance_report = {"IndividualPlayerPerformance": report.get_report()}
        return Response(data=individual_player_performance_report, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=["GET"])
    def team_performance_report(self, request, user_id: str):
        report = TeamPerformanceReport()
        team_performance_report = {"TeamPerformanceOverviewReport": report.get_report()}
        return Response(data=team_performance_report, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=["GET"])
    def set_piece_analysis_report(self, request, user_id: str):
        report = SetPieceAnalysisReport()
        set_piece_analysis_report = {"SetPieceAnalysisReport": report.get_report()}
        return Response(data=set_piece_analysis_report, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=["GET"])
    def fitness_recovery_suggestion(self, request, user_id: str):
        report = FitnessRecoverySuggestion()
        fitness_recovery = {"FitnessRecoverySuggestions": report.get_report()}
        return Response(data=fitness_recovery, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['GET'])
    def training_recommendation_report(self, request, user_id: str):
        report = TrainingRecommendationReport()
        recommendation_report = {"TrainingRecommendationsReport": report.get_report()}
        return Response(data=recommendation_report, status=status.HTTP_200_OK)


class MatchSummaryView(APIView):
    def get(self, request, user_id: str):
        report = MatchSummaryReport()
        summary = report.get_match_summary()
        return Response(data=summary, status=status.HTTP_200_OK)
