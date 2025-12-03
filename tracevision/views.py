import logging
from django.db import models
from django.db.models import Q
from django.conf import settings
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework import serializers
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from teams.models import Team
from tracevision.models import (
    TraceClipReel,
    TraceSession,
    TraceVisionPlayerStats,
    TracePlayer,
    TracePossessionSegment,
    TracePossessionStats,
    TraceHighlight,
)
from tracevision.tasks import (
    generate_overlay_highlights_task,
    process_trace_sessions_task,
)
from tracevision.serializers import (
    TraceVisionProcessesSerializer,
    TraceVisionProcessSerializer,
    TraceSessionListSerializer,
    CoachViewSpecificTeamPlayersSerializer,
    HighlightDateSessionSerializer,
    HighlightClipReelSerializer,
    MatchInfoSerializer,
    PossessionTeamMetricsSerializer,
    PossessionPlayerMetricsSerializer,
    GenerateHighlightClipReelSerializer,
)
from tracevision.services import TraceVisionService
from games.models import GameUserRole, Game
from tracevision.tasks import map_players_to_users_task


logger = logging.getLogger()

CUSTOMER_ID = int(settings.TRACEVISION_CUSTOMER_ID)
API_KEY = settings.TRACEVISION_API_KEY
GRAPHQL_URL = settings.TRACEVISION_GRAPHQL_URL


class HighlightPagination(PageNumberPagination):
    """Custom pagination class for highlights"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'
    
    def get_paginated_response(self, data):
        """Override to return custom pagination response format with highlights"""
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page': self.page.number,
            'page_size': self.get_page_size(self.request),
            'total_pages': self.page.paginator.num_pages,
            'highlights': data  # Use 'highlights' instead of 'results'
        })


class TraceVisionProcessesList(ListAPIView):
    serializer_class = TraceSessionListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Get games where user has GameUserRole
        user_games = Game.objects.filter(
            game_roles__user=self.request.user
        ).values_list("id", flat=True)

        # Get sessions where:
        # 1. User is the original uploader
        # 2. User has a GameUserRole for the game
        # 3. User's team matches one of the game teams (backward compatibility)
        # 4. User has mapped TracePlayers in the session
        base_queryset = TraceSession.objects.filter(
            Q(user=self.request.user)
            | Q(game__id__in=user_games)
            | Q(home_team=self.request.user.team)
            | Q(away_team=self.request.user.team)
            | Q(trace_players__user=self.request.user)
        ).distinct()

        serializer = self.serializer_class(data=self.request.query_params)
        if not serializer.is_valid():
            # Return empty queryset instead of Response object
            return TraceSession.objects.none()

        return self.serializer_class.get_filtered_queryset(
            base_queryset, serializer.validated_data
        )

    def list(self, request, *args, **kwargs):
        """
        Override list method to handle validation errors properly
        """
        # Validate query parameters first
        serializer = self.serializer_class(data=request.query_params)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid query parameters", "details": serializer.errors},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        # If validation passes, proceed with normal list behavior
        return super().list(request, *args, **kwargs)

    def get_paginated_response(self, data):
        """
        Override to add custom response format
        """
        response = super().get_paginated_response(data)
        response.data["success"] = True
        return response


class TraceVisionProcessDetail(RetrieveAPIView):
    serializer_class = TraceVisionProcessesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Get games where user has GameUserRole
        user_games = Game.objects.filter(
            game_roles__user=self.request.user
        ).values_list("id", flat=True)

        # Get sessions where user is uploader OR has GameUserRole OR team matches
        return TraceSession.objects.filter(
            Q(user=self.request.user)
            | Q(game__id__in=user_games)
            | Q(home_team=self.request.user.team)
            | Q(away_team=self.request.user.team)
        ).distinct()


class TraceVisionProcessView(APIView):
    """
    API endpoint to trigger TraceVision session creation and video processing
    for a given TraceSession instance according to Figma requirements.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            serializer = TraceVisionProcessSerializer(
                data=request.data, context={"request": request}
            )

            if not serializer.is_valid():
                logger.error(f"Serializer validation failed: {serializer.errors}")
                return Response(
                    {"error": "Validation failed", "details": serializer.errors},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            try:
                session = serializer.save()
            except serializers.ValidationError as e:
                # Handle duplicate game/video errors from serializer
                error_data = e.detail
                if isinstance(error_data, dict) and "error" in error_data:
                    status_code = (
                        http_status.HTTP_409_CONFLICT
                        if "already" in str(error_data.get("error", "")).lower()
                        else http_status.HTTP_400_BAD_REQUEST
                    )
                    return Response(error_data, status=status_code)
                return Response(
                    {"error": "Validation failed", "details": error_data},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "success": True,
                    "id": session.id,
                    "session_id": session.session_id,
                    "age_group": session.age_group,
                    "pitch_size": session.pitch_size,
                    "pitch_dimensions": session.get_pitch_dimensions(),
                    "message": "TraceVision session created and video processing started successfully",
                    "video_source": (
                        "link"
                        if serializer.validated_data.get("video_link")
                        else "file_upload"
                    ),
                    "game_date": (
                        session.match_date.isoformat() if session.match_date else None
                    ),
                    "game_time": (
                        serializer.validated_data.get("game_time").isoformat()
                        if serializer.validated_data.get("game_time")
                        else None
                    ),
                    "match_start_time": session.match_start_time,
                    "first_half_end_time": session.first_half_end_time,
                    "second_half_start_time": session.second_half_start_time,
                    "match_end_time": session.match_end_time,
                    "basic_game_stats": (
                        session.basic_game_stats.url
                        if session.basic_game_stats
                        else None
                    ),
                },
                status=http_status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.exception(f"Error while processing TraceVision request: {str(e)}")
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TraceVisionPollStatusView(APIView):
    """
    API endpoint to actively poll TraceVision API for latest session status and data.
    This is used when user refreshes the app to get real-time updates.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            # Get games where user has GameUserRole
            user_games = Game.objects.filter(game_roles__user=request.user).values_list(
                "id", flat=True
            )

            # Get session where user is uploader OR has GameUserRole OR team matches
            session = TraceSession.objects.filter(
                Q(id=pk)
                & (
                    Q(user=request.user)
                    | Q(game__id__in=user_games)
                    | Q(home_team=request.user.team)
                    | Q(away_team=request.user.team)
                )
            ).get()

            # Check if user wants to force refresh cache
            force_refresh = (
                request.query_params.get("force_refresh", "false").lower() == "true"
            )

            # Initialize service
            tracevision_service = TraceVisionService()

            # Get status data (with caching)
            status_data = tracevision_service.get_session_status(
                session, force_refresh=force_refresh
            )

            if not status_data:
                return Response(
                    {
                        "error": "Failed to retrieve status from TraceVision API",
                        "session_id": session.session_id,
                    },
                    status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            new_status = status_data.get("status")
            previous_status = session.status

            # Update session status if it has changed
            if new_status and new_status != previous_status:
                session.status = new_status
                session.save()
                logger.info(
                    f"Updated session {session.session_id} status from {previous_status} to {new_status}"
                )

                # If status changed to completed, fetch and save result data
                if new_status == "processed":
                    result_data = tracevision_service.get_session_result(session)
                    if result_data:
                        session.result = result_data
                        session.save()
                        logger.info(
                            f"Updated result data for completed session {session.session_id}"
                        )

            # Prepare response data
            response_data = {
                "success": True,
                "id": session.id,
                "session_id": session.session_id,
                "status": session.status,
                "previous_status": previous_status,
                "status_updated": (
                    new_status != previous_status if new_status else False
                ),
                "result": session.result,
                "match_date": session.match_date,
                "home_team": session.home_team.name if session.home_team else None,
                "away_team": session.away_team.name if session.away_team else None,
                "home_score": session.home_score,
                "away_score": session.away_score,
                "home_team_jersey_color": (
                    session.home_team.jersey_color if session.home_team else None
                ),
                "away_team_jersey_color": (
                    session.away_team.jersey_color if session.away_team else None
                ),
                "age_group": session.age_group,
                "pitch_size": session.pitch_size,
                "pitch_dimensions": session.get_pitch_dimensions(),
                "final_score": session.final_score,
                "start_time": session.start_time,
                "video_url": session.video_url,
            }

            # If session is processed, include session URL and highlights
            if session.status == "processed":
                # Get highlights for this session
                highlights = session.highlights.all().order_by("start_offset")
                highlights_data = []

                for highlight in highlights:
                    highlight_data = {
                        "id": highlight.id,
                        "highlight_id": highlight.highlight_id,
                        "start_offset": highlight.start_offset,
                        "duration": highlight.duration,
                        "event_type": highlight.event_type,
                        "match_time": highlight.match_time,
                        "half": highlight.half,
                        "tags": highlight.tags,
                        "video_stream": highlight.video_stream,
                        "performance_impact": highlight.performance_impact,
                        "team_impact": highlight.team_impact,
                        "event_metadata": highlight.event_metadata,
                    }

                    # Include primary player info if available
                    if (
                        hasattr(highlight, "primary_player")
                        and highlight.primary_player
                    ):
                        highlight_data["primary_player"] = {
                            "id": highlight.primary_player.id,
                            "name": highlight.primary_player.name,
                            "jersey_number": highlight.primary_player.jersey_number,
                        }

                    highlights_data.append(highlight_data)

                # Add session URL and highlights to response
                response_data.update(
                    {
                        "session_url": f"/api/vision/process/{session.id}/",
                        "highlights": highlights_data,
                        "highlights_count": len(highlights_data),
                        "metadata": {
                            "home_team": (
                                session.home_team.name if session.home_team else None
                            ),
                            "away_team": (
                                session.away_team.name if session.away_team else None
                            ),
                            "home_score": session.home_score,
                            "away_score": session.away_score,
                            "home_team_jersey_color": (
                                session.home_team.jersey_color
                                if session.home_team
                                else None
                            ),
                            "away_team_jersey_color": (
                                session.away_team.jersey_color
                                if session.away_team
                                else None
                            ),
                            "age_group": session.age_group,
                            "pitch_size": session.pitch_size,
                            "pitch_dimensions": session.get_pitch_dimensions(),
                            "final_score": session.final_score,
                            "start_time": session.start_time,
                            "match_date": session.match_date,
                            "video_url": session.video_url,
                            "fetched_at": datetime.now().isoformat(),
                        },
                    }
                )

            return Response(response_data, status=http_status.HTTP_200_OK)

        except TraceSession.DoesNotExist:
            return Response(
                {"error": "Session not found"}, status=http_status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception(f"Error while polling TraceVision status: {str(e)}")
            return Response(
                {"error": "Internal server error"},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TraceVisionPlayerStatsView(APIView):
    """
    API endpoint to manage and retrieve player performance statistics.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        """
        Trigger player stats calculation for a session or generate overlay highlights

        Query Parameters:
        - task_type: 'process_sessions' (default) or 'generate_overlays'
        """
        try:
            # Get games where user has GameUserRole
            user_games = Game.objects.filter(game_roles__user=request.user).values_list(
                "id", flat=True
            )

            # Get session where user is uploader OR has GameUserRole OR team matches
            session = TraceSession.objects.filter(
                Q(id=pk)
                & (
                    Q(user=request.user)
                    | Q(game__id__in=user_games)
                    | Q(home_team=request.user.team)
                    | Q(away_team=request.user.team)
                )
            ).get()

            # Get task type from query parameters
            task_type = request.query_params.get("task_type", "process_sessions")

            # Validate task type
            if task_type not in ["process_sessions", "generate_overlays"]:
                return Response(
                    {
                        "error": "Invalid task type",
                        "details": "task_type must be 'process_sessions' or 'generate_overlays'",
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            # Check if session is processed (only for process_sessions task)
            if task_type == "process_sessions" and session.status != "processed":
                return Response(
                    {
                        "error": "Session is not processed yet",
                        "details": f"Current status: {session.status}. Wait for processing to complete.",
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            # Trigger the appropriate async task
            if task_type == "process_sessions":
                task = process_trace_sessions_task.delay(session.id)
                message = "Player stats calculation started"
                logger.info(
                    f"Queued player stats calculation for session {session.session_id}"
                )
            else:  # generate_overlays
                task = generate_overlay_highlights_task.delay(
                    session_id=session.session_id
                )
                message = "Overlay highlights generation started"
                logger.info(
                    f"Queued overlay highlights generation for session {session.session_id}"
                )

            return Response(
                {
                    "success": True,
                    "message": message,
                    "task_id": task.id,
                    "session_id": session.session_id,
                    "task_type": task_type,
                    "status": "processing",
                },
                status=http_status.HTTP_202_ACCEPTED,
            )

        except TraceSession.DoesNotExist:
            return Response(
                {
                    "error": "Session not found",
                    "details": "No TraceVision session found with the given ID for this user",
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.exception(
                f"Error starting stats calculation for session {pk}: {str(e)}"
            )
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def get(self, request, pk):
        """
        Get possession segment data (team and player metrics) for a session.

        Query Parameters:
        - team_id: Filter by specific team ID (optional)
        - player_id: Filter by specific player ID (optional)
        """
        try:
            # Get games where user has GameUserRole
            user_games = Game.objects.filter(game_roles__user=request.user).values_list(
                "id", flat=True
            )

            # Get session where user is uploader OR has GameUserRole OR team matches
            session = (
                TraceSession.objects.select_related("home_team", "away_team")
                .filter(
                    Q(id=pk)
                    & (
                        Q(user=request.user)
                        | Q(game__id__in=user_games)
                        | Q(home_team=request.user.team)
                        | Q(away_team=request.user.team)
                    )
                )
                .get()
            )

            # Get filter parameters
            team_id_filter = request.query_params.get("team_id", None)
            player_id_filter = request.query_params.get("player_id", None)

            # Validate filters - if both provided, ensure they're from the same side
            if team_id_filter and player_id_filter:
                try:
                    team_id = team_id_filter  # Team ID is a string (CharField)
                    player_id = int(player_id_filter)

                    # Get the team and player
                    team = Team.objects.get(id=team_id)
                    player = TracePlayer.objects.select_related("team").get(
                        id=player_id
                    )

                    # Determine sides
                    team_side = None
                    if session.home_team and team.id == session.home_team.id:
                        team_side = "home"
                    elif session.away_team and team.id == session.away_team.id:
                        team_side = "away"

                    player_side = None
                    if player.team:
                        if session.home_team and player.team.id == session.home_team.id:
                            player_side = "home"
                        elif (
                            session.away_team and player.team.id == session.away_team.id
                        ):
                            player_side = "away"

                    # Validate they're from the same side - return simple 404 if not
                    if team_side and player_side and team_side != player_side:
                        return Response(
                            {
                                "error": "Not found",
                                "details": "No stats found with the team_id & player_id",
                            },
                            status=http_status.HTTP_404_NOT_FOUND,
                        )

                except (Team.DoesNotExist, TracePlayer.DoesNotExist, ValueError):
                    return Response(
                        {
                            "error": "Not found",
                            "details": "No stats found with the team_id & player_id",
                        },
                        status=http_status.HTTP_404_NOT_FOUND,
                    )

            # Get team metrics from last TracePossessionSegment for each side
            team_metrics_data = {}

            # Determine which sides to query
            sides_to_query = ["home", "away"]
            if team_id_filter:
                team_id = team_id_filter  # Team ID is a string (CharField)
                if session.home_team and team_id == session.home_team.id:
                    sides_to_query = ["home"]
                elif session.away_team and team_id == session.away_team.id:
                    sides_to_query = ["away"]
                else:
                    return Response(
                        {
                            "error": "Team not found",
                            "details": f"Team {team_id} is not associated with this session",
                        },
                        status=http_status.HTTP_404_NOT_FOUND,
                    )

            for side in sides_to_query:
                # Get the last segment for this side (cumulative metrics)
                last_segment = (
                    TracePossessionSegment.objects.filter(session=session, side=side)
                    .order_by("-end_ms")
                    .only("team_metrics", "side")
                    .first()
                )

                if last_segment and last_segment.team_metrics:
                    team = session.home_team if side == "home" else session.away_team
                    metrics = last_segment.team_metrics

                    # Format team metrics data
                    team_metrics_data[side] = {
                        "team": team,
                        "possession_time_ms": metrics.get("possession_time_ms", 0),
                        "possession_count": metrics.get("possession_count", 0),
                        "avg_duration_ms": metrics.get("avg_duration_ms", 0.0),
                        "avg_passes": metrics.get("avg_passes", 0.0),
                        "longest_possession_ms": metrics.get(
                            "longest_possession_ms", 0
                        ),
                        "turnovers": metrics.get("turnovers", 0),
                        "total_touches": metrics.get("total_touches", 0),
                        "total_passes": metrics.get("total_passes", 0),
                        "possession_percentage": metrics.get(
                            "possession_percentage", 0.0
                        ),
                    }
                else:
                    team = session.home_team if side == "home" else session.away_team
                    team_metrics_data[side] = {
                        "team": team,
                        "possession_time_ms": 0,
                        "possession_count": 0,
                        "avg_duration_ms": 0.0,
                        "avg_passes": 0.0,
                        "longest_possession_ms": 0,
                        "turnovers": 0,
                        "total_touches": 0,
                        "total_passes": 0,
                        "possession_percentage": 0.0,
                    }

            # Get player metrics from TracePossessionStats
            player_stats_query = TracePossessionStats.objects.filter(
                session=session, possession_type="player"
            ).select_related("player", "player__team")

            # optimize by filtering directly on team through player relationship
            if team_id_filter:
                team_id = team_id_filter
                # This ensures we only get players from the specified team
                player_stats_query = player_stats_query.filter(player__team_id=team_id)

            if player_id_filter:
                try:
                    player_id = int(player_id_filter)
                    player_stats_query = player_stats_query.filter(player_id=player_id)
                except ValueError:
                    return Response(
                        {
                            "error": "Invalid player_id",
                            "details": "player_id must be a valid integer",
                        },
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )

            player_stats_list = list(player_stats_query.all())

            # Format player metrics data
            player_metrics_data = []
            for player_stat in player_stats_list:
                metrics = player_stat.metrics or {}

                # Calculate possession_percentage from involvement_percentage if available
                possession_percentage = metrics.get(
                    "possession_percentage", metrics.get("involvement_percentage", 0.0)
                )

                player_data = {
                    "player": player_stat.player,
                    "involvement_count": metrics.get(
                        "involvement_count", metrics.get("possessions_involved", 0)
                    ),
                    "total_duration_ms": metrics.get("total_duration_ms", 0),
                    "total_touches": metrics.get(
                        "total_touches", metrics.get("touches_in_possession", 0)
                    ),
                    "total_passes": metrics.get(
                        "total_passes", metrics.get("passes_in_possession", 0)
                    ),
                    "possession_percentage": possession_percentage,
                }
                player_metrics_data.append(player_data)

            # Serialize the data with request context for perspective transformation
            team_metrics_serialized = {}
            for side, team_data in team_metrics_data.items():
                # Add side to team_data for transformation
                team_data["side"] = side
                serializer = PossessionTeamMetricsSerializer(
                    team_data, context={"request": request, "session": session}
                )
                team_metrics_serialized[side] = serializer.data

            # Serialize player metrics with session and request context
            player_metrics_serialized = []
            for player_data in player_metrics_data:
                serializer = PossessionPlayerMetricsSerializer(
                    player_data, context={"request": request, "session": session}
                )
                player_metrics_serialized.append(serializer.data)

            return Response(
                {
                    "success": True,
                    "data": {
                        "team_metrics": team_metrics_serialized,
                        "player_metrics": player_metrics_serialized,
                    },
                },
                status=http_status.HTTP_200_OK,
            )

        except TraceSession.DoesNotExist:
            return Response(
                {
                    "error": "Session not found",
                    "details": "No TraceVision session found with the given ID for this user",
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.exception(
                f"Error getting possession stats for session {pk}: {str(e)}"
            )
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TraceVisionPlayerStatsDetailView(APIView):
    """
    API endpoint to get detailed statistics for a specific player in a session.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk, player_id):
        """
        Get detailed performance statistics for a specific player
        """
        try:
            # Get games where user has GameUserRole
            user_games = Game.objects.filter(game_roles__user=request.user).values_list(
                "id", flat=True
            )

            # Get session where user is uploader OR has GameUserRole OR team matches
            session = TraceSession.objects.filter(
                Q(id=pk)
                & (
                    Q(user=request.user)
                    | Q(game__id__in=user_games)
                    | Q(home_team=request.user.team)
                    | Q(away_team=request.user.team)
                )
            ).get()

            # Get player stats
            try:
                player_stats = TraceVisionPlayerStats.objects.get(
                    session=session, player_id=player_id
                )
            except TraceVisionPlayerStats.DoesNotExist:
                return Response(
                    {
                        "error": "Player stats not found",
                        "details": f"No statistics found for player {player_id} in session {session.session_id}",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # Get heatmap data
            heatmap_data = player_stats.heatmap_data

            # Format detailed response
            detailed_stats = {
                "player_id": player_stats.player.id,
                "player_name": player_stats.player.name,
                "team_id": player_stats.team.id,
                "team_name": player_stats.team.name,
                "jersey_number": player_stats.player_mapping.jersey_number,
                "side": player_stats.player_mapping.side,
                # Comprehensive movement analysis
                "movement_analysis": {
                    "total_distance_meters": player_stats.total_distance_meters,
                    "total_time_seconds": player_stats.total_time_seconds,
                    "distance_per_minute": player_stats.distance_per_minute,
                    "avg_speed_mps": player_stats.avg_speed_mps,
                    "max_speed_mps": player_stats.max_speed_mps,
                    "speed_analysis": {
                        "avg_speed": player_stats.avg_speed_mps,
                        "max_speed": player_stats.max_speed_mps,
                        "speed_efficiency": (
                            (
                                player_stats.avg_speed_mps
                                / player_stats.max_speed_mps
                                * 100
                            )
                            if player_stats.max_speed_mps > 0
                            else 0
                        ),
                    },
                },
                # Sprint analysis
                "sprint_analysis": {
                    "sprint_count": player_stats.sprint_count,
                    "sprint_distance_meters": player_stats.sprint_distance_meters,
                    "sprint_time_seconds": player_stats.sprint_time_seconds,
                    "sprint_percentage": player_stats.sprint_percentage,
                    "avg_sprint_distance": (
                        player_stats.sprint_distance_meters / player_stats.sprint_count
                        if player_stats.sprint_count > 0
                        else 0
                    ),
                    "avg_sprint_duration": (
                        player_stats.sprint_time_seconds / player_stats.sprint_count
                        if player_stats.sprint_count > 0
                        else 0
                    ),
                },
                # Position and tactical analysis
                "position_analysis": {
                    "avg_position_x": player_stats.avg_position_x,
                    "avg_position_y": player_stats.avg_position_y,
                    "position_variance": player_stats.position_variance,
                    "movement_range": {
                        "x_range": player_stats.position_variance
                        * 2,  # Approximate range
                        "y_range": player_stats.position_variance * 2,
                    },
                },
                # Performance metrics
                "performance_metrics": {
                    "overall_score": player_stats.performance_score,
                    "stamina_rating": player_stats.stamina_rating,
                    "work_rate": player_stats.work_rate,
                    "fitness_index": (
                        player_stats.stamina_rating + player_stats.work_rate
                    )
                    / 2,
                },
                # Heatmap visualization data
                "heatmap_data": heatmap_data,
                # Metadata
                "calculation_info": {
                    "method": player_stats.calculation_method,
                    "version": player_stats.calculation_version,
                    "last_calculated": (
                        player_stats.last_calculated.isoformat()
                        if player_stats.last_calculated
                        else None
                    ),
                },
            }

            return Response(
                {
                    "success": True,
                    "session_id": session.session_id,
                    "player_stats": detailed_stats,
                },
                status=http_status.HTTP_200_OK,
            )

        except TraceSession.DoesNotExist:
            return Response(
                {
                    "error": "Session not found",
                    "details": "No TraceVision session found with the given ID for this user",
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.exception(
                f"Error getting detailed player stats for session {pk}, player {player_id}: {str(e)}"
            )
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GetTracePlayerReelsView(ListAPIView):
    """
    API endpoint to get highlights for a specific session.
    URL: highlights/<session_id>/
    Query Parameters:
    - player_id: Filter by specific player ID (optional)
    - generation_status: Filter by generation status of clip reels (optional)
    - event_type: Filter by event type (optional)
    - half: Filter by half (1 or 2) (optional)
    """

    permission_classes = [IsAuthenticated]
    serializer_class = HighlightClipReelSerializer
    pagination_class = HighlightPagination

    def get_queryset(self):
        """Get optimized queryset for highlights"""
        session_id = self.kwargs.get("session_id")

        # Get games where user has GameUserRole
        user_games = Game.objects.filter(
            game_roles__user=self.request.user
        ).values_list("id", flat=True)

        # Get session and verify user has access
        try:
            session = (
                TraceSession.objects.select_related("home_team", "away_team")
                .filter(
                    Q(id=session_id)
                    & (
                        Q(user=self.request.user)
                        | Q(game__id__in=user_games)
                        | Q(home_team=self.request.user.team)
                        | Q(away_team=self.request.user.team)
                    )
                )
                .get()
            )
        except TraceSession.DoesNotExist:
            return TraceHighlight.objects.none()

        # Base queryset with optimized selects
        queryset = (
            TraceHighlight.objects.filter(session=session)
            .select_related("player__team", "session__home_team", "session__away_team")
            .prefetch_related("clip_reels")  # Prefetch clip reels for videos
        )

        # Apply filters from query parameters
        # video_type filter removed - not needed anymore
        
        generation_status = self.request.query_params.get("generation_status")
        if generation_status:
            # Filter highlights that have clip reels with this status
            queryset = queryset.filter(clip_reels__generation_status=generation_status).distinct()

        event_type = self.request.query_params.get("event_type")
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        # Filter by player_id if provided
        player_id = self.request.query_params.get("player_id")
        if player_id:
            try:
                player_id = int(player_id)
                queryset = queryset.filter(
                    models.Q(player_id=player_id)
                    | models.Q(highlight_objects__player_id=player_id)
                ).distinct()
            except ValueError:
                # Invalid player_id - return empty queryset
                return TraceHighlight.objects.none()

        # Filter by half if specified
        half = self.request.query_params.get("half")
        if half:
            try:
                half_num = int(half)
                if half_num in [1, 2]:
                    queryset = queryset.filter(half=half_num)
                else:
                    # Invalid half - return empty queryset
                    return TraceHighlight.objects.none()
            except ValueError:
                # Invalid half - return empty queryset
                return TraceHighlight.objects.none()

        return queryset

    def get_serializer_context(self):
        """Add session and request to serializer context for perspective transformation"""
        context = super().get_serializer_context()
        session_id = self.kwargs.get("session_id")
        try:
            # Get games where user has GameUserRole
            user_games = Game.objects.filter(
                game_roles__user=self.request.user
            ).values_list("id", flat=True)

            context["session"] = (
                TraceSession.objects.select_related("home_team", "away_team")
                .filter(
                    Q(id=session_id)
                    & (
                        Q(user=self.request.user)
                        | Q(game__id__in=user_games)
                        | Q(home_team=self.request.user.team)
                        | Q(away_team=self.request.user.team)
                    )
                )
                .get()
            )
        except TraceSession.DoesNotExist:
            context["session"] = None
        # Request is already in context from super(), but ensure it's there
        if "request" not in context:
            context["request"] = self.request
        return context

    def list(self, request, *args, **kwargs):
        """Override list to add match_info and custom response format"""
        session_id = kwargs.get("session_id")

        # Get games where user has GameUserRole
        user_games = Game.objects.filter(game_roles__user=request.user).values_list(
            "id", flat=True
        )

        # Get session for match_info
        try:
            session = (
                TraceSession.objects.select_related("home_team", "away_team")
                .filter(
                    Q(id=session_id)
                    & (
                        Q(user=request.user)
                        | Q(game__id__in=user_games)
                        | Q(home_team=request.user.team)
                        | Q(away_team=request.user.team)
                    )
                )
                .get()
            )
        except TraceSession.DoesNotExist:
            return Response(
                {
                    "error": "Session not found",
                    "details": f"No session found with ID {session_id} for this user",
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )

        # Validate query parameters
        player_id = request.query_params.get("player_id")
        if player_id:
            try:
                int(player_id)
            except ValueError:
                return Response(
                    {
                        "error": "Invalid player_id",
                        "details": "player_id must be a valid integer",
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

        half = request.query_params.get("half")
        if half:
            try:
                half_num = int(half)
                if half_num not in [1, 2]:
                    return Response(
                        {"error": "Invalid half", "details": "half must be 1 or 2"},
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )
            except ValueError:
                return Response(
                    {"error": "Invalid half", "details": "half must be 1 or 2"},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

        # Get queryset and apply filters
        queryset = self.filter_queryset(self.get_queryset())
        
        # Order queryset for consistent pagination
        queryset = queryset.order_by('-created_at', '-id')

        # Paginate queryset at database level (more efficient)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            # Serialize only the paginated results
            serializer = self.get_serializer(page, many=True)
            highlights = serializer.data
            
            # Get paginated response
            paginated_response = self.get_paginated_response(highlights)
            
            # Serialize match_info with request context for perspective transformation
            match_info_serializer = MatchInfoSerializer(
                session, context={"request": request}
            )
            match_info = match_info_serializer.data
            
            # Build response with match_info
            response_data = paginated_response.data
            response_data['match_info'] = match_info
            
            return Response(response_data, status=http_status.HTTP_200_OK)

        # Fallback if pagination is not applied (shouldn't happen with ListAPIView)
        serializer = self.get_serializer(queryset, many=True)
        highlights = serializer.data
        
        # Serialize match_info
        match_info_serializer = MatchInfoSerializer(
            session, context={"request": request}
        )
        match_info = match_info_serializer.data
        
        return Response({
            "highlights": highlights,
            "match_info": match_info,
            "count": len(highlights),
            "next": None,
            "previous": None,
        }, status=http_status.HTTP_200_OK)


class GetAvailableHighlightDatesView(APIView):
    """
    API endpoint to get list of dates on which highlights are available.
    Returns sessions grouped by date with match info and players.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            user_role = user.role
            
            # Check if user is a coach
            is_coach = user_role == "Coach"
            
            if is_coach:
                # For coaches: get sessions where coach's team is in the game OR coach is coaching players from either team
                coach_team = user.team
                coach_teams = list(user.teams_coached.values_list('id', flat=True))  # Get team IDs efficiently
                
                # Build query for coach access - must have highlights (clip_reels exist)
                coach_queries = models.Q()
                
                # 1. Coach's team is one of the teams in the session
                if coach_team:
                    coach_queries |= models.Q(home_team=coach_team) | models.Q(away_team=coach_team)
                
                # 2. Coach is in the team's coach field for either home_team or away_team
                if coach_teams:
                    coach_queries |= models.Q(home_team_id__in=coach_teams) | models.Q(away_team_id__in=coach_teams)
                
                # 3. Coach is coaching players (through WajoUser.coach) who have highlights in the session
                # Get TracePlayers for coached users in a single optimized query
                coached_trace_player_ids = list(
                    TracePlayer.objects.filter(user__coach=user)
                    .values_list('id', flat=True)
                )
                if coached_trace_player_ids:
                    coach_queries |= (
                        models.Q(clip_reels__primary_player_id__in=coached_trace_player_ids)
                        | models.Q(clip_reels__involved_players__id__in=coached_trace_player_ids)
                    )
                
                # Get all sessions where coach has access AND has highlights
                # Using filter with clip_reels ensures we only get sessions with highlights
                if coach_queries:
                    sessions_with_highlights = (
                        TraceSession.objects.filter(coach_queries)
                        .filter(clip_reels__isnull=False)  # Ensure sessions have highlights
                        .select_related("home_team", "away_team")
                        .distinct()
                        .order_by("-match_date", "-id")
                    )
                else:
                    # No access criteria met, return empty queryset
                    sessions_with_highlights = TraceSession.objects.none()
            else:
                # For players: get sessions where the player has highlights
                player = user.trace_players.first()
                if not player:
                    return Response(
                        {
                            "success": False,
                            "message": "No player found for this user",
                            "data": {},
                        },
                        status=http_status.HTTP_404_NOT_FOUND,
                    )
                
                # Get sessions with teams where the player has highlights
                sessions_with_highlights = (
                    TraceSession.objects.filter(
                        models.Q(clip_reels__primary_player=player)
                        | models.Q(clip_reels__involved_players=player)
                    )
                    .select_related("home_team", "away_team")
                    .distinct()
                    .order_by("-match_date", "-id")
                )

            try:

                # Prefetch all players for teams in these sessions
                # Get unique team IDs from sessions
                team_ids = set()
                for session in sessions_with_highlights:
                    if session.home_team:
                        team_ids.add(session.home_team.id)
                    if session.away_team:
                        team_ids.add(session.away_team.id)

                # Get all TracePlayers for these teams (NOT filtered by session)
                # This ensures we get players even if they weren't created for this specific session
                all_players = TracePlayer.objects.filter(
                    team_id__in=team_ids
                ).select_related("team", "session")

                # Create a mapping of team_id -> players for quick lookup
                players_by_team = {}
                for player_obj in all_players:
                    team_id = player_obj.team_id
                    if team_id not in players_by_team:
                        players_by_team[team_id] = []
                    players_by_team[team_id].append(player_obj)

                # Attach prefetched players to sessions based on teams
                # Get players from home_team and away_team for each session
                for session in sessions_with_highlights:
                    session._prefetched_players = []
                    if session.home_team and session.home_team.id in players_by_team:
                        session._prefetched_players.extend(
                            players_by_team[session.home_team.id]
                        )
                    if session.away_team and session.away_team.id in players_by_team:
                        session._prefetched_players.extend(
                            players_by_team[session.away_team.id]
                        )

            except Exception as db_error:
                logger.exception(
                    f"Database error while fetching sessions: {str(db_error)}"
                )
                return Response(
                    {
                        "success": False,
                        "message": "Something went wrong",
                        "data": {},
                        "error": "Unable to retrieve session data. Please try again later.",
                    },
                    status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Group sessions by date
            sessions_by_date = {}
            try:
                for session in sessions_with_highlights:
                    try:
                        date_key = (
                            session.match_date.strftime("%Y-%m-%d")
                            if session.match_date
                            else None
                        )
                        if not date_key:
                            continue

                        if date_key not in sessions_by_date:
                            sessions_by_date[date_key] = []

                        # Serialize session data with request context for perspective transformation
                        serializer = HighlightDateSessionSerializer(
                            session, context={"request": request}
                        )
                        sessions_by_date[date_key].append(serializer.data)
                    except (AttributeError, ValueError, KeyError) as session_error:
                        logger.warning(
                            f"Error processing session {session.id if hasattr(session, 'id') else 'unknown'}: {str(session_error)}"
                        )
                        continue
                    except Exception as serialization_error:
                        logger.warning(
                            f"Serialization error for session {session.id if hasattr(session, 'id') else 'unknown'}: {str(serialization_error)}"
                        )
                        continue
            except Exception as processing_error:
                logger.exception(f"Error processing sessions: {str(processing_error)}")
                return Response(
                    {
                        "success": False,
                        "message": "Error processing session data",
                        "data": {},
                        "error": "Unable to process session information. Please try again later.",
                    },
                    status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            return Response(
                {
                    "success": True,
                    "message": "Available highlight dates retrieved successfully",
                    "data": sessions_by_date,
                },
                status=http_status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(
                f"Unexpected error fetching available highlight dates: {str(e)}"
            )
            return Response(
                {
                    "success": False,
                    "message": "An unexpected error occurred",
                    "data": {},
                    "error": "Unable to retrieve highlight dates. Please try again later.",
                },
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CoachViewSpecificTeamPlayers(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return Response(
                {
                    "error": "Unauthorized",
                    "details": "You are not authorized to access this resource",
                },
            )
        role = request.user.role
        if role == "Coach":
            team = request.user.team
            players = team.players.all()
            print(players)
            serializer = CoachViewSpecificTeamPlayersSerializer(players, many=True)
            return Response(
                {"success": True, "players": serializer.data},
            )
        else:
            return Response(
                {
                    "error": "Unauthorized",
                    "details": "You are not authorized to access this resource",
                },
            )


class GeneratingAgainClipReelsView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return Response(
                {
                    "error": "Unauthorized",
                    "details": "You are not authorized to access this resource",
                },
            )
        role = request.user.role
        if role == "User":
            clip_reel_id = request.data.get("clip_reel_id")
            clip_reel = TraceClipReel.objects.get(id=clip_reel_id)
            clip_reel.generation_status = "pending"
            generate_overlay_highlights_task.delay(None, [clip_reel.id])
            clip_reel.save()
            return Response(
                {"success": True, "message": "Clip reel generation started"},
            )
        if role == "Coach":
            team = request.user.team
            players = team.players.all()
            for player in players:
                clip_reels = player.primary_clip_reels.all()
                for clip_reel in clip_reels:
                    clip_reel.generation_status = "pending"
                    generate_overlay_highlights_task.delay(None, [clip_reel.id])
                    clip_reel.save()
            return Response(
                {"success": True, "message": "Clip reel generation started"},
                status=http_status.HTTP_200_OK,
            )


class LinkUserToGameView(APIView):
    """
    API endpoint to link a user to an existing game.
    This allows users to access games they didn't originally upload.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Link the authenticated user to an existing game.
        User's role is determined by their WajoUser.role field.

        Request body:
        - game_id: ID of the game to link to (required)
        """
        try:
            game_id = request.data.get("game_id")
            if not game_id:
                return Response(
                    {
                        "error": "game_id is required",
                        "details": "Please provide a game_id in the request body",
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            # Get the game
            try:
                game = Game.objects.select_related("trace_session").get(id=game_id)
            except Game.DoesNotExist:
                return Response(
                    {
                        "error": "Game not found",
                        "details": f"No game found with ID {game_id}",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # Check if user has access (team matches one of game teams OR coach of team)
            user_team = request.user.team
            user_role = request.user.role

            has_access = False

            # Check if user's team matches one of the game teams
            if user_team and game.teams.filter(id=user_team.id).exists():
                has_access = True

            # Check if user is a coach of one of the game teams
            if user_role == "Coach" and user_team:
                if game.teams.filter(id=user_team.id).exists():
                    has_access = True

            # Also allow if user is already linked (update existing link)
            if GameUserRole.objects.filter(game=game, user=request.user).exists():
                has_access = True

            if not has_access:
                return Response(
                    {
                        "error": "Access denied",
                        "details": "You don't have permission to link to this game. Your team must be one of the teams in this game, or you must be a coach of one of the teams.",
                    },
                    status=http_status.HTTP_403_FORBIDDEN,
                )

            # Get or create GameUserRole (role comes from user.role)
            game_user_role, created = GameUserRole.objects.get_or_create(
                game=game, user=request.user
            )

            # Trigger player mapping task for this game
            if game.trace_session:
                try:
                    map_players_to_users_task.delay(game_id=game.id)
                    logger.info(
                        f"Triggered player mapping for game {game.id} after user link"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to trigger player mapping for game {game.id}: {e}"
                    )

            user_role = request.user.role or "No Role"
            return Response(
                {
                    "success": True,
                    "message": "User linked to game successfully",
                    "game": {
                        "id": game.id,
                        "type": game.type,
                        "name": game.name,
                        "date": game.date.isoformat() if game.date else None,
                    },
                    "user_role": user_role,
                    "created": created,
                },
                status=(
                    http_status.HTTP_201_CREATED if created else http_status.HTTP_200_OK
                ),
            )

        except Exception as e:
            logger.exception(f"Error linking user to game: {str(e)}")
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GenerateHighlightClipReelView(APIView):
    """
    API endpoint to generate highlight clip reel with specific tags and ratio.
    
    Request body:
    - highlight_id: ID of the TraceHighlight (required)
    - tags: List of overlay tags (e.g., ["with_player_title", "without_circle"]) (required)
    - ratio: Video aspect ratio - "original" or "9:16" (required)
    - is_default: Whether this should be the default video (optional, default: False)
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            # Validate input using serializer
            serializer = GenerateHighlightClipReelSerializer(data=request.data)
            
            if not serializer.is_valid():
                return Response(
                    {"error": "Validation failed", "details": serializer.errors},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            # Extract validated data
            validated_data = serializer.validated_data
            highlight_id = validated_data["highlight_id"]
            tags = validated_data["tags"]
            ratio = validated_data["ratio"]
            is_default = validated_data.get("is_default", False)

            # Get the TraceHighlight with related objects
            try:
                highlight = TraceHighlight.objects.select_related(
                    "session",
                    "player",
                    "player__user",
                ).get(id=highlight_id)
            except TraceHighlight.DoesNotExist:
                return Response(
                    {"error": f"TraceHighlight with id {highlight_id} not found"},
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            session = highlight.session

            # Check if user is the primary player of this highlight
            if not highlight.player:
                return Response(
                    {
                        "error": "Highlight has no primary player",
                        "details": "This highlight is not associated with any player",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            if highlight.player.user != request.user:
                return Response(
                    {
                        "error": "Unauthorized",
                        "details": "You must be the primary player of this highlight to generate clip reels",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # Check if a TraceClipReel already exists with the same highlight, tags, and ratio
            # Sort tags for consistent comparison
            sorted_tags = sorted(tags)
            existing_clip_reels = TraceClipReel.objects.filter(
                highlight=highlight, ratio=ratio
            )  # Get all existing clip reels for this highlight and ratio

            # Check if any existing clip reel has the same tags (sorted)
            for clip_reel in existing_clip_reels:
                existing_tags = sorted(clip_reel.tags) if clip_reel.tags else []
                if existing_tags == sorted_tags:
                    return Response(
                        {
                            "success": False,
                            "message": "Clip reel already exists",
                            "details": "A clip reel with the same tags and ratio already exists for this highlight",
                            "data": {
                                "clip_reel_id": clip_reel.id,
                                "highlight_id": highlight.highlight_id,
                                "tags": clip_reel.tags,
                                "ratio": clip_reel.ratio,
                                "generation_status": clip_reel.generation_status,
                                "video_url": clip_reel.video_url if clip_reel.video_url else None,
                            },
                        },
                        status=http_status.HTTP_200_OK,
                    )

            # Print the information (as requested for now)
            print("=" * 80)
            print("HIGHLIGHT CLIP REEL GENERATION REQUEST")
            print("=" * 80)
            print(f"Highlight ID: {highlight.id} (highlight_id: {highlight.highlight_id})")
            print(f"Session ID: {session.id}")
            print(f"Primary Player: {highlight.player.name} (User: {request.user})")
            print(f"Tags: {tags}")
            print(f"Ratio: {ratio}")
            print(f"Is Default: {is_default}")
            print(f"Event Type: {highlight.event_type}")
            print(f"Start Offset: {highlight.start_offset}ms")
            print(f"Duration: {highlight.duration}ms")
            print("=" * 80)

            # TODO: Here you would trigger the actual video generation
            # For now, we just print the information as requested
            # In the future, this would call a task like:
            # generate_highlight_clip_reel_task.delay(highlight_id, tags, ratio, is_default)

            return Response(
                {
                    "success": True,
                    "message": "Highlight generation request received",
                    "data": {
                        "highlight_id": highlight.id,
                        "highlight_id_string": highlight.highlight_id,
                        "session_id": session.id,
                        "tags": tags,
                        "ratio": ratio,
                        "is_default": is_default,
                    },
                },
                status=http_status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception(f"Error in GenerateHighlightClipReelView: {str(e)}")
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
