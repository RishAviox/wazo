import logging
from django.db import models
from django.db.models import Q, Prefetch
from django.conf import settings
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as http_status
from rest_framework import serializers
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework import viewsets
from rest_framework.decorators import action
from tracevision.permissions import HasClipReelAccess


from teams.models import Team
from tracevision.models import (
    TraceClipReel,
    TraceSession,
    TraceVisionPlayerStats,
    TracePlayer,
    TracePossessionSegment,
    TracePossessionStats,
    TraceHighlight,
    PlayerUserMapping,
    TraceClipReelShare,
    TraceClipReelComment,
    TraceClipReelCommentLike,
    TraceClipReelNote,
    TraceClipReelNoteShare,
)
from tracevision.tasks import (
    generate_overlay_highlights_task,
    process_trace_sessions_task,
    compute_aggregates_task,
    reprocess_game_timeline_task,
    process_excel_match_highlights_task,
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
    MapUserToPlayerSerializer,
    TraceClipReelShareSerializer,
    TraceClipReelCommentSerializer,
    TraceClipReelCommentEditSerializer,
    TraceClipReelCommentLikeSerializer,
    TraceClipReelNoteSerializer,
    TraceClipReelNoteShareSerializer,
    TraceClipReelCaptionSerializer,
    BulkHighlightShareSerializer,
)
from tracevision.services import TraceVisionService
from games.models import GameUserRole, Game
from tracevision.tasks import map_players_to_users_task
from tracevision.utils import (
    get_localized_game_name,
    get_localized_team_name,
    get_localized_player_name,
)


logger = logging.getLogger()

CUSTOMER_ID = int(settings.TRACEVISION_CUSTOMER_ID)
API_KEY = settings.TRACEVISION_API_KEY
GRAPHQL_URL = settings.TRACEVISION_GRAPHQL_URL

permission_classes = [IsAuthenticated, HasClipReelAccess]





class HighlightPagination(PageNumberPagination):
    """Custom pagination class for highlights"""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        """Override to return custom pagination response format with highlights"""
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "total_pages": self.page.paginator.num_pages,
                "highlights": data,  # Use 'highlights' instead of 'results'
            }
        )


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

            # Get user language preference
            user_language = getattr(request.user, "selected_language", "en") or "en"

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
                "home_team": (
                    get_localized_team_name(session.home_team, user_language)
                    if session.home_team
                    else None
                ),
                "away_team": (
                    get_localized_team_name(session.away_team, user_language)
                    if session.away_team
                    else None
                ),
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
                            "name": get_localized_player_name(
                                highlight.primary_player, user_language
                            ),
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
                                get_localized_team_name(
                                    session.home_team, user_language
                                )
                                if session.home_team
                                else None
                            ),
                            "away_team": (
                                get_localized_team_name(
                                    session.away_team, user_language
                                )
                                if session.away_team
                                else None
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
        Trigger player stats calculation for a session, generate overlay highlights, recalculate possession segments,
        or create Excel highlights

        Query Parameters:
        - task_type: 'process_sessions' (default), 'generate_overlays', 'recalculate_possession', 'reprocess_timeline', or 'reprocess_excel_highlights'
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
            if task_type not in [
                "process_sessions",
                "generate_overlays",
                "recalculate_possession",
                "reprocess_timeline",
                "reprocess_excel_highlights",
            ]:
                return Response(
                    {
                        "error": "Invalid task type",
                        "details": "task_type must be 'process_sessions', 'generate_overlays', 'recalculate_possession', 'reprocess_timeline', or 'reprocess_excel_highlights'",
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            # Check if session is processed (required for process_sessions and recalculate_possession tasks)
            if (
                task_type in ["process_sessions", "recalculate_possession"]
                and session.status != "processed"
            ):
                return Response(
                    {
                        "error": "Session is not processed yet",
                        "details": f"Current status: {session.status}. Wait for processing to complete.",
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            # Check if session has Excel file (required for reprocess_excel_highlights task)
            if task_type == "reprocess_excel_highlights" and not session.basic_game_stats:
                return Response(
                    {
                        "error": "Excel file not found",
                        "details": "Session does not have a basic_game_stats Excel file. Please upload an Excel file first.",
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
            elif task_type == "generate_overlays":
                task = generate_overlay_highlights_task.delay(
                    session_id=session.session_id
                )
                message = "Overlay highlights generation started"
                logger.info(
                    f"Queued overlay highlights generation for session {session.session_id}"
                )
            elif task_type == "reprocess_timeline":
                task = reprocess_game_timeline_task.delay(session.id)
                message = "Game timeline reprocessing started"
                logger.info(
                    f"Queued game timeline reprocessing for session {session.session_id}"
                )
            elif task_type == "reprocess_excel_highlights":
                task = process_excel_match_highlights_task.delay(
                    session.session_id
                )
                message = "Excel highlights creation started"
                logger.info(
                    f"Queued Excel highlights creation for session {session.session_id}"
                )
            else:  # recalculate_possession
                task = compute_aggregates_task.delay(
                    session.session_id, only_possession_segments=True
                )
                message = "Possession segments recalculation started"
                logger.info(
                    f"Queued possession segments recalculation for session {session.session_id}"
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

            # Get user language preference
            user_language = getattr(request.user, "selected_language", "en") or "en"

            # Format detailed response
            detailed_stats = {
                "player_id": player_stats.player.id,
                "player_name": get_localized_player_name(
                    player_stats.player, user_language
                ),
                "team_id": player_stats.team.id,
                "team_name": get_localized_team_name(player_stats.team, user_language),
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
            .prefetch_related(
                Prefetch(
                    "clip_reels",
                    queryset=TraceClipReel.objects.select_related(
                        "primary_player", "primary_player__team"
                    ),
                )
            )  # Prefetch clip reels with primary_player for videos
        )

        # Apply filters from query parameters
        # video_type filter removed - not needed anymore

        generation_status = self.request.query_params.get("generation_status")
        if generation_status:
            # Filter highlights that have clip reels with this status
            queryset = queryset.filter(
                clip_reels__generation_status=generation_status
            ).distinct()

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

        try:
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
            queryset = queryset.order_by("-created_at", "-id")

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
                response_data["match_info"] = match_info

                return Response(response_data, status=http_status.HTTP_200_OK)

            # Fallback if pagination is not applied (shouldn't happen with ListAPIView)
            serializer = self.get_serializer(queryset, many=True)
            highlights = serializer.data

            # Serialize match_info
            match_info_serializer = MatchInfoSerializer(
                session, context={"request": request}
            )
            match_info = match_info_serializer.data

            return Response(
                {
                    "highlights": highlights,
                    "match_info": match_info,
                    "count": len(highlights),
                    "next": None,
                    "previous": None,
                },
                status=http_status.HTTP_200_OK,
            )
        except Exception as e:
            logger.exception(f"Error getting trace player reels: {str(e)}")
            return Response(
                {
                    "error": "Internal server error",
                    "details": str(e),
                },
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


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
                coach_teams = list(
                    user.teams_coached.values_list("id", flat=True)
                )  # Get team IDs efficiently

                # Build query for coach access - must have highlights (clip_reels exist)
                coach_queries = models.Q()

                # 1. Coach's team is one of the teams in the session
                if coach_team:
                    coach_queries |= models.Q(home_team=coach_team) | models.Q(
                        away_team=coach_team
                    )

                # 2. Coach is in the team's coach field for either home_team or away_team
                if coach_teams:
                    coach_queries |= models.Q(home_team_id__in=coach_teams) | models.Q(
                        away_team_id__in=coach_teams
                    )

                # 3. Coach is coaching players (through WajoUser.coach) who have highlights in the session
                # Get TracePlayers for coached users in a single optimized query
                coached_trace_player_ids = list(
                    TracePlayer.objects.filter(user__coach=user).values_list(
                        "id", flat=True
                    )
                )
                if coached_trace_player_ids:
                    coach_queries |= models.Q(
                        clip_reels__primary_player_id__in=coached_trace_player_ids
                    ) | models.Q(
                        clip_reels__involved_players__id__in=coached_trace_player_ids
                    )

                # Get all sessions where coach has access AND has highlights
                # Using filter with clip_reels ensures we only get sessions with highlights
                if coach_queries:
                    sessions_with_highlights = (
                        TraceSession.objects.filter(coach_queries)
                        .filter(
                            clip_reels__isnull=False
                        )  # Ensure sessions have highlights
                        .select_related("home_team", "away_team", "game")
                        .prefetch_related(
                            Prefetch(
                                "highlights",
                                queryset=TraceHighlight.objects.filter(
                                    event_type="goal"
                                ).select_related("player", "player__team"),
                                to_attr="_prefetched_goal_highlights"
                            ),
                            "session_stats"
                        )
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
                    .select_related("home_team", "away_team", "game")
                    .prefetch_related(
                        Prefetch(
                            "highlights",
                            queryset=TraceHighlight.objects.filter(
                                event_type="goal"
                            ).select_related("player", "player__team"),
                            to_attr="_prefetched_goal_highlights"
                        ),
                        "session_stats"
                    )
                    .distinct()
                    .order_by("-match_date", "-id")
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


class GenerateHighlightsWithIds(APIView):
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
            # Get user language preference
            user_language = getattr(request.user, "selected_language", "en") or "en"

            return Response(
                {
                    "success": True,
                    "message": "User linked to game successfully",
                    "game": {
                        "id": game.id,
                        "type": game.type,
                        "name": get_localized_game_name(game, user_language),
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
    API endpoint to trigger highlight generation for a given clip reel ID.
    Clip reel is already created in advance, this endpoint only triggers generation.

    Request body:
    - clip_reel_id: TraceClipReel ID (required)

    Authorization:
    - Coach: Must be coach of the team that the clip reel's primary player belongs to
    - Player: Must be the user of the primary player, or belong to the same team as the primary player
    - Others: 403 Forbidden
    """

    permission_classes = [IsAuthenticated]

    def _check_authorization_batch(
        self, user, user_role, user_teams_coached_ids, clip_reel
    ):
        """
        Batch authorization check (optimized to avoid N+1 queries).
        Uses pre-fetched user_teams_coached_ids instead of querying for each clip reel.

        Args:
            user: The requesting user
            user_role: The user's role
            user_teams_coached_ids: Pre-fetched set of team IDs the user coaches (for Coach role)
            clip_reel: The clip reel to check authorization for

        Returns:
            tuple: (is_authorized: bool, error_message: str or None)
        """
        primary_player = clip_reel.primary_player
        player_team = primary_player.team
        player_team_id = player_team.id if player_team else None

        logger.info(f"user_role: {user_role}")
        logger.info(f"user_teams_coached_ids: {user_teams_coached_ids}")
        logger.info(f"player_team_id: {player_team_id}")
        logger.info(f"primary_player: {primary_player}")
        logger.info(f"player_team: {player_team}")
        logger.info(f"user: {user}")
        logger.info(f"clip_reel: {clip_reel}")

        # Coach authorization: must be coach of the team that the primary player belongs to
        if user_role == "Coach":
            # Use pre-fetched teams_coached_ids (no query)
            if player_team_id and player_team_id in user_teams_coached_ids:
                return True, None
            return (
                False,
                "You must be a coach of the team for which you are requesting highlights",
            )

        # Player authorization: must be the user of the primary player, or belong to the same team
        if user_role == "Player":
            # Check if user is the primary player's user (already prefetched)
            if primary_player.user == user:
                return True, None
            # Check if user belongs to the same team as the primary player
            if user.team and player_team_id and user.team.id == player_team_id:
                return True, None
            return False, "You must belong to the same team as the primary player"

        # Others: 403 Forbidden
        return False, "Only coaches and players can generate highlights"

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
            clip_reel_id = validated_data["clip_reel_id"]

            # Fetch clip reel with related objects (optimized to avoid N+1 queries)
            try:
                clip_reel = (
                    TraceClipReel.objects.select_related(
                        "highlight",
                        "highlight__session",
                        "highlight__player",
                        "highlight__player__user",
                        "highlight__player__team",
                        "primary_player",
                        "primary_player__user",
                        "primary_player__team",
                    )
                    .prefetch_related(
                        "primary_player__user__teams_coached",  # Prefetch teams_coached to avoid N+1
                    )
                    .get(id=clip_reel_id)
                )
            except TraceClipReel.DoesNotExist:
                return Response(
                    {
                        "error": "Invalid clip reel ID",
                        "details": f"Clip reel with ID {clip_reel_id} was not found",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # Validate clip reel has required fields
            if not clip_reel.primary_player:
                return Response(
                    {
                        "error": "Clip reel has no primary player",
                        "details": "This clip reel is not associated with any primary player",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            if not clip_reel.highlight:
                return Response(
                    {
                        "error": "Clip reel has no associated highlight",
                        "details": "This clip reel is not associated with any highlight",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # Pre-fetch user's teams_coached once (to avoid N+1 queries in authorization check)
            user = request.user
            user_role = user.role
            user_teams_coached_ids = set()
            if user_role == "Coach":
                # Prefetch all teams the user coaches in a single query
                user_teams_coached_ids = set(
                    user.teams_coached.values_list("id", flat=True)
                )

            # Check authorization (optimized, no N+1 queries)
            is_authorized, error_message = self._check_authorization_batch(
                user, user_role, user_teams_coached_ids, clip_reel
            )

            if not is_authorized:
                return Response(
                    {
                        "error": "Unauthorized",
                        "details": error_message,
                    },
                    status=http_status.HTTP_403_FORBIDDEN,
                )

            # Process clip reel
            clip_reels_to_generate = []
            # Check if already generated (completed with video_url)
            if clip_reel.generation_status == "completed" and clip_reel.video_url:
                return Response(
                    {
                        "success": True,
                        "message": "Clip reel already generated",
                        "data": {
                            "clip_reel_id": clip_reel.id,
                            "highlight_id": clip_reel.highlight.highlight_id,
                            "tags": clip_reel.tags,
                            "ratio": clip_reel.ratio,
                            "is_default": clip_reel.is_default,
                            "generation_status": clip_reel.generation_status,
                            "video_url": clip_reel.video_url,
                            "status": "already_generated",
                        },
                    },
                    status=http_status.HTTP_200_OK,
                )

            # Mark as pending and add to generation queue
            clip_reel.generation_status = "pending"
            clip_reel.save(update_fields=["generation_status"])
            clip_reels_to_generate.append(clip_reel.id)

            # Get tags, is_default, and ratio from the clip reel
            clip_reel_tags = clip_reel.tags or []
            clip_reel_is_default = (
                clip_reel.is_default if clip_reel.is_default is not None else False
            )
            clip_reel_ratio = clip_reel.ratio or "original"

            # Trigger background generation task with clip reel's tags and is_default
            try:
                generate_overlay_highlights_task.delay(
                    clip_reel_ids=clip_reels_to_generate,
                    tags=clip_reel_tags,
                    is_default=clip_reel_is_default,
                    ratios=[clip_reel_ratio] if clip_reel_ratio else None,
                )
                logger.info(
                    f"Triggered background generation for clip reel: {clip_reel_id} "
                    f"with tags: {clip_reel_tags}, is_default: {clip_reel_is_default}, ratio: {clip_reel_ratio}"
                )
            except Exception as e:
                logger.exception(
                    f"Failed to trigger background generation task: {str(e)}"
                )
                # Update status back to failed
                clip_reel.generation_status = "failed"
                clip_reel.save(update_fields=["generation_status"])
                return Response(
                    {
                        "error": "Failed to queue generation task",
                        "details": str(e),
                    },
                    status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Return success response
            return Response(
                {
                    "success": True,
                    "message": "Highlight generation request queued",
                    "data": {
                        "clip_reel_id": clip_reel.id,
                        "highlight_id": clip_reel.highlight.highlight_id,
                        "tags": clip_reel.tags,
                        "ratio": clip_reel.ratio,
                        "is_default": clip_reel.is_default,
                        "generation_status": "pending",
                        "video_url": None,
                        "status": "queued_for_generation",
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


class MapUserToPlayerView(APIView):
    """
    API endpoint to map a WajoUser to a TracePlayer.
    Only coaches can perform this mapping, and they must be coaches of the team
    that the player belongs to (or both teams in the session).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Map a WajoUser to a TracePlayer.

        Request body:
        {
            "user_id": "1234567890",  # Phone number of WajoUser
            "player_id": 123           # ID of TracePlayer
        }

        Validations:
        1. user_id must be a valid WajoUser
        2. player_id must be a valid TracePlayer
        3. Only coaches can map (must be coach of player's team or both teams)
        4. The user's team must match the TracePlayer's team (home_team or away_team)
        """
        try:
            from accounts.models import WajoUser

            # Validate input
            serializer = MapUserToPlayerSerializer(data=request.data)
            if not serializer.is_valid():
                return Response(
                    {"error": "Validation failed", "details": serializer.errors},
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            user_id = serializer.validated_data["user_id"]
            player_id = serializer.validated_data["player_id"]

            # Validation 1: Check if user_id is a valid WajoUser
            try:
                wajo_user = WajoUser.objects.select_related("team").get(
                    phone_no=user_id
                )
            except WajoUser.DoesNotExist:
                return Response(
                    {
                        "error": "User not found",
                        "details": f"WajoUser with phone_no '{user_id}' does not exist",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # Validation 2: Check if player_id is a valid TracePlayer
            try:
                trace_player = TracePlayer.objects.select_related(
                    "team", "session", "user"
                ).get(id=player_id)
            except TracePlayer.DoesNotExist:
                return Response(
                    {
                        "error": "Player not found",
                        "details": f"TracePlayer with ID '{player_id}' does not exist",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # Validation 3: Check if requesting user is a coach
            requesting_user = request.user
            if requesting_user.role != "Coach":
                return Response(
                    {
                        "error": "Unauthorized",
                        "details": "You are not authorized to map the user to the player. Only coaches can perform this action.",
                    },
                    status=http_status.HTTP_403_FORBIDDEN,
                )

            # Check if requesting user is a coach of the player's team or both teams
            player_team = trace_player.team

            # Get teams the requesting user coaches
            user_teams_coached_ids = set(
                requesting_user.teams_coached.values_list("id", flat=True)
            )

            # Check if user is coach of player's team
            is_coach_of_player_team = (
                player_team and player_team.id in user_teams_coached_ids
            )

            # Check if user is coach of both teams in any of the player's sessions
            is_coach_of_both_teams = False
            player_sessions = trace_player.sessions.select_related(
                "home_team", "away_team"
            ).all()
            for session in player_sessions:
                if session.home_team and session.away_team:
                    if (
                        session.home_team.id in user_teams_coached_ids
                        and session.away_team.id in user_teams_coached_ids
                    ):
                        is_coach_of_both_teams = True
                        break

            if not (is_coach_of_player_team or is_coach_of_both_teams):
                return Response(
                    {
                        "error": "Unauthorized",
                        "details": "You are not authorized to map the user to the player. You must be a coach of the team that the player belongs to, or both teams.",
                    },
                    status=http_status.HTTP_403_FORBIDDEN,
                )

            # Validation 4: Check if user's team matches TracePlayer's team (home_team or away_team)
            if not wajo_user.team:
                return Response(
                    {
                        "error": "User team not set",
                        "details": "The WajoUser must have a team assigned before mapping to a TracePlayer",
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            user_team = wajo_user.team
            player_team = trace_player.team

            # Check if user's team matches player's team
            if user_team.id != player_team.id:
                return Response(
                    {
                        "error": "Team mismatch",
                        "details": f"The user's team ({user_team.name or user_team.id}) does not match the player's team ({player_team.name or player_team.id})",
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            # Validation 5: Check if player is already mapped to another user
            # One TracePlayer can only be mapped to one WajoUser
            if trace_player.user:
                if trace_player.user == wajo_user:
                    # Already mapped to the same user - return success without remapping
                    logger.info(
                        f"TracePlayer {player_id} is already mapped to user {user_id}. "
                        f"No action needed."
                    )
                    return Response(
                        {
                            "success": True,
                            "message": "User is already mapped to this player",
                        },
                        status=http_status.HTTP_200_OK,
                    )
                else:
                    # Already mapped to a different user - prevent remapping
                    existing_user = trace_player.user
                    logger.warning(
                        f"TracePlayer {player_id} is already mapped to user {existing_user.phone_no}. "
                        f"Cannot remap to {user_id}. One TracePlayer can only be mapped to one WajoUser."
                    )
                    return Response(
                        {
                            "error": "Player already mapped",
                            "details": f"This TracePlayer is already mapped to user {existing_user.phone_no}. "
                            f"One TracePlayer can only be mapped to one WajoUser. "
                            f"To remap, first unmap the existing user.",
                        },
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )

            # Perform the mapping (player is not mapped yet)
            trace_player.user = wajo_user
            trace_player.save(update_fields=["user"])

            # Create mapping history record
            PlayerUserMapping.objects.create(
                trace_player=trace_player,
                wajo_user=wajo_user,
                mapped_by=requesting_user,
                mapping_source="api",
            )

            logger.info(
                f"Successfully mapped TracePlayer {player_id} to WajoUser {user_id} by coach {requesting_user.phone_no}"
            )

            return Response(
                {
                    "success": True,
                    "message": "User mapped to player successfully",
                },
                status=http_status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception(f"Error in MapUserToPlayerView: {str(e)}")
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GetPlayerByTokenView(APIView):
    """
    API endpoint to get TracePlayer details by account creation token.
    Used by frontend to display player information before account creation.
    """

    def get(self, request):
        """
        Get TracePlayer details by account_creation_token.

        Query Parameters:
        - token: Account creation token (required)
        """
        token = request.query_params.get("token")

        if not token:
            return Response(
                {
                    "error": "Token is required",
                    "details": "Please provide account_creation_token as query parameter",
                },
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        try:
            trace_player = (
                TracePlayer.objects.select_related("team")
                .prefetch_related("sessions__home_team", "sessions__away_team")
                .get(
                    account_creation_token=token,
                    user__isnull=True,  # Only return if not already linked to a user
                )
            )

            # Get first session info (or most recent)
            session = trace_player.sessions.order_by(
                "-match_date", "-created_at"
            ).first()

            # Get user language preference (default to 'en' if not authenticated)
            user_language = "en"
            if request.user.is_authenticated:
                user_language = getattr(request.user, "selected_language", "en") or "en"

            # Build sessions list
            sessions_data = []
            for sess in trace_player.sessions.all():
                sessions_data.append(
                    {
                        "id": sess.id,
                        "session_id": sess.session_id,
                        "match_date": (
                            sess.match_date.isoformat() if sess.match_date else None
                        ),
                        "home_team": (
                            get_localized_team_name(sess.home_team, user_language)
                            if sess.home_team
                            else None
                        ),
                        "away_team": (
                            get_localized_team_name(sess.away_team, user_language)
                            if sess.away_team
                            else None
                        ),
                    }
                )

            return Response(
                {
                    "success": True,
                    "player": {
                        "id": trace_player.id,
                        "name": get_localized_player_name(trace_player, user_language),
                        "jersey_number": trace_player.jersey_number,
                        "position": trace_player.position,
                        "team": {
                            "id": trace_player.team.id if trace_player.team else None,
                            "name": (
                                get_localized_team_name(
                                    trace_player.team, user_language
                                )
                                if trace_player.team
                                else None
                            ),
                        },
                        "primary_session": (
                            {
                                "id": session.id if session else None,
                                "session_id": session.session_id if session else None,
                                "match_date": (
                                    session.match_date.isoformat()
                                    if session and session.match_date
                                    else None
                                ),
                                "home_team": (
                                    get_localized_team_name(
                                        session.home_team, user_language
                                    )
                                    if session and session.home_team
                                    else None
                                ),
                                "away_team": (
                                    get_localized_team_name(
                                        session.away_team, user_language
                                    )
                                    if session and session.away_team
                                    else None
                                ),
                            }
                            if session
                            else None
                        ),
                        "sessions": sessions_data,  # All sessions this player participates in
                        "language_metadata": trace_player.language_metadata or {},
                    },
                },
                status=http_status.HTTP_200_OK,
            )

        except TracePlayer.DoesNotExist:
            return Response(
                {
                    "error": "Invalid or expired token",
                    "details": "The provided token is invalid or has already been used",
                },
                status=http_status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.exception(f"Error getting player by token: {str(e)}")
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class DeleteErroredTraceSessionView(APIView):
    """
    API endpoint to delete/soft-delete a Game and its TraceSession
    when the TraceSession status is 'process_error'.
    - Game is soft-deleted (WajoModel.delete)
    - TraceSession is hard-deleted (cascade removes related Trace* data)
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            # Only allow the original uploader (creator) to delete their errored session
            session = (
                TraceSession.objects.select_related("game", "home_team", "away_team")
                .filter(id=pk, user=request.user)
                .first()
            )

            if not session:
                return Response(
                    {
                        "error": "Session not found",
                        "details": "No TraceVision session found with the given ID for this user",
                    },
                    status=http_status.HTTP_404_NOT_FOUND,
                )

            # Only allow cleanup for sessions that failed processing
            if session.status != "process_error":
                return Response(
                    {
                        "error": "Invalid session status",
                        "details": f"Only sessions with status 'process_error' can be deleted. Current status: {session.status}",
                    },
                    status=http_status.HTTP_400_BAD_REQUEST,
                )

            game = session.game

            # Soft-delete the canonical Game if it exists
            game_info = None
            if game:
                # Get user language preference
                user_language = getattr(request.user, "selected_language", "en") or "en"
                game_info = {
                    "id": game.id,
                    "type": game.type,
                    "name": get_localized_game_name(game, user_language),
                    "date": game.date.isoformat() if game.date else None,
                }
                game.delete()

            # Hard-delete the TraceSession (and cascades)
            session_id = session.id
            session_session_id = session.session_id
            video_url = session.video_url
            session.delete()

            return Response(
                {
                    "success": True,
                    "message": "Errored TraceSession and its Game (if any) were deleted successfully",
                    "deleted_session": {
                        "id": session_id,
                        "session_id": session_session_id,
                        "video_url": video_url,
                    },
                    "deleted_game": game_info,
                },
                status=http_status.HTTP_200_OK,
            )

        except Exception as e:
            logger.exception(f"Error deleting errored TraceSession {pk}: {str(e)}")
            return Response(
                {"error": "Internal server error", "details": str(e)},
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )



class HighlightNotesView(APIView):
    """
    Combined POST/GET endpoint for highlight notes.
    POST: Create a new note on a clip reel within a highlight
    GET: List all notes visible to the requesting user for a specific highlight
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, highlight_id):
        """
        Create a new note on a highlight.
        
        Request body:
        {
            "content": str,
            "share_with_coach_id": uuid (optional),
            "share_with_team_coaches": bool (optional)
        }
        """
        from tracevision.serializers import TraceClipReelNoteSerializer
        from django.shortcuts import get_object_or_404
        
        # Validate user is Player or Coach
        if request.user.role not in ["Player", "Coach"]:
            return Response(
                {"error": "Only Players and Coaches can create notes."},
                status=http_status.HTTP_403_FORBIDDEN,
            )
        
        # Get highlight
        highlight = get_object_or_404(TraceHighlight, id=highlight_id)
        # NOTE or TODO: Take the clip reel id for the higlight and if not provided then use the first clip reel of the highlight
        
        # Get the first clip reel for this highlight
        clip_reel = TraceClipReel.objects.filter(highlight=highlight).first()
        if not clip_reel:
            return Response(
                {"error": "No clip reel found for this highlight."},
                status=http_status.HTTP_404_NOT_FOUND,
            )
        
        # Prepare data for serializer
        data = {
            "clip_reel_id": clip_reel.id,
            "highlight_id": highlight_id,
            "content": request.data.get("content"),
        }
        
        # Create note
        serializer = TraceClipReelNoteSerializer(data=data, context={"request": request})
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)
        
        note = serializer.save()
        
        # Handle sharing if requested
        share_with_coach_id = request.data.get("share_with_coach_id")
        share_with_team_coaches = request.data.get("share_with_team_coaches", False)
        
        shares_created = []
        
        if share_with_coach_id:
            # Share with specific coach
            from accounts.models import WajoUser
            try:
                coach = WajoUser.objects.get(id=share_with_coach_id, role="Coach")
                
                # Validate that coach belongs to player's team or is assigned to player
                author = request.user
                is_valid_coach = False
                
                # Check if coach is part of the author's team
                if author.team:
                    team_coaches = author.team.coach.all()
                    if coach in team_coaches:
                        is_valid_coach = True
                
                # Check if coach is assigned to the player
                if not is_valid_coach and hasattr(author, 'coach'):
                    if author.coach.filter(id=coach.id).exists():
                        is_valid_coach = True
                
                if not is_valid_coach:
                    return Response(
                        {
                            "error": "You can only share notes with coaches from your team or coaches assigned to you.",
                            "note": serializer.data,
                        },
                        status=http_status.HTTP_400_BAD_REQUEST,
                    )
                
                # Coach is valid, create share
                share = note.share_with_user(coach, request.user)
                shares_created.append({
                    "id": str(share.id),
                    "shared_with_user": str(coach.id),
                    "shared_with_user_name": coach.name or coach.phone_no,
                })
            except WajoUser.DoesNotExist:
                # Note created but sharing failed
                return Response(
                    {
                        "message": "Note created but coach not found for sharing.",
                        "note": serializer.data,
                    },
                    status=http_status.HTTP_201_CREATED,
                )
        
        if share_with_team_coaches:
            # Share with all team coaches
            share = note.share_with_group("team_coaches", request.user)
            shares_created.append({
                "id": str(share.id),
                "shared_with_group": "team_coaches",
            })
        
        # Return created note with shares
        response_data = {
            "message": "Note created successfully",
            "note": serializer.data,
        }
        
        if shares_created:
            response_data["shares"] = shares_created
        
        return Response(response_data, status=http_status.HTTP_201_CREATED)
    
    def get(self, request, highlight_id):
        """
        List all notes visible to the requesting user for this highlight.
        Returns notes authored by user or shared with user.
        """
        from tracevision.serializers import TraceClipReelNoteSerializer
        from django.shortcuts import get_object_or_404
        
        # Get highlight
        highlight = get_object_or_404(TraceHighlight, id=highlight_id)
        
        # Get all notes for clip reels in this highlight
        notes = TraceClipReelNote.objects.filter(
            highlight=highlight,
            is_deleted=False
        ).select_related("author", "clip_reel")
        
        # Filter notes based on can_view permission
        accessible_notes = [note for note in notes if note.can_view(request.user)]
        
        serializer = TraceClipReelNoteSerializer(
            accessible_notes,
            many=True,
            context={"request": request}
        )
        
        return Response(
            {
                "count": len(accessible_notes),
                "results": serializer.data
            },
            status=http_status.HTTP_200_OK,
        )


# ============================================================================
# TraceClipReel Comment System ViewSets
# ============================================================================


class TraceClipReelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for TraceClipReel operations including sharing and caption management.
    """

    queryset = TraceClipReel.objects.all()
    serializer_class = HighlightClipReelSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    @action(detail=True, methods=["post"], url_path="share")
    def share_reel(self, request, pk=None):
        """
        Share clip reel with another user.
        """
        clip_reel = self.get_object()

        data = request.data.copy()
        data["clip_reel_id"] = clip_reel.id
        data["highlight_id"] = clip_reel.highlight.id if clip_reel.highlight else None

        serializer = TraceClipReelShareSerializer(
            data=data,
            context={"request": request},
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": "Reel shared successfully",
                "data": serializer.data,
            },
            status=http_status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="shares")
    def list_shares(self, request, pk=None):
        """
        List all shares for this clip reel.
        GET /api/tracevision/clip-reels/{id}/shares/
        """
        from tracevision.permissions import IsClipReelOwner

        clip_reel = self.get_object()

        # Only owner can see who reel is shared with
        permission = IsClipReelOwner()
        if not permission.has_object_permission(request, self, clip_reel):
            return Response(
                {"error": "Only the reel owner can view shares."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        shares = TraceClipReelShare.objects.filter(clip_reel=clip_reel, is_active=True)
        serializer = TraceClipReelShareSerializer(shares, many=True, context={"request": request})

        return Response({"shares": serializer.data}, status=http_status.HTTP_200_OK)

    @action(detail=True, methods=["delete"], url_path="shares/(?P<share_id>[^/.]+)")
    def revoke_share(self, request, pk=None, share_id=None):
        """
        Revoke share access (set is_active=False).
        DELETE /api/tracevision/clip-reels/{id}/shares/{share_id}/
        """
        from tracevision.permissions import IsClipReelOwner

        clip_reel = self.get_object()

        # Only owner can revoke shares
        permission = IsClipReelOwner()
        if not permission.has_object_permission(request, self, clip_reel):
            return Response(
                {"error": "Only the reel owner can revoke shares."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        try:
            share = TraceClipReelShare.objects.get(id=share_id, clip_reel=clip_reel)
            share.is_active = False
            share.save()

            return Response(
                {"message": "Share revoked successfully"},
                status=http_status.HTTP_200_OK,
            )
        except TraceClipReelShare.DoesNotExist:
            return Response(
                {"error": "Share not found"},
                status=http_status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["get"], url_path="shared-with-me")
    def shared_with_me(self, request):
        shares = (
            TraceClipReelShare.objects
            .filter(shared_with=request.user, is_active=True)
            .select_related("clip_reel")
        )

        clip_reels = [share.clip_reel for share in shares]

        serializer = HighlightClipReelSerializer(
            clip_reels,
            many=True,
            context={"request": request},
        )

        return Response(
            {"clip_reels": serializer.data},
            status=http_status.HTTP_200_OK,
        )

    @action(detail=False, methods=["get"], url_path="shared-by-me")
    def shared_by_me(self, request):
        """
        List all clip reels shared by the current user.
        Returns shares with recipient details (player_id, name, role).
        
        GET /api/vision/clip-reels/shared-by-me/
        """
        shares = (
            TraceClipReelShare.objects
            .filter(shared_by=request.user, is_active=True)
            .select_related("clip_reel", "shared_with", "highlight")
            .order_by("-shared_at")
        )
        
        serializer = TraceClipReelShareSerializer(
            shares,
            many=True,
            context={"request": request},
        )
        
        return Response(
            {"shares": serializer.data},
            status=http_status.HTTP_200_OK,
        )


    @action(detail=True, methods=["patch"], url_path="caption")
    def update_caption(self, request, pk=None):
        """
        Add or update caption for clip reel.
        PATCH /api/tracevision/clip-reels/{id}/caption/
        """
        clip_reel = self.get_object()

        serializer = TraceClipReelCaptionSerializer(
            clip_reel, data=request.data, partial=True, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Caption updated successfully", "data": serializer.data},
                status=http_status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        """
        Handle comments on clip reel.
        GET /api/vision/clip-reels/{id}/comments/ - List comments
        POST /api/vision/clip-reels/{id}/comments/ - Add comment
        """
        clip_reel = self.get_object()

        if request.method == "GET":
            # List comments (filtered by visibility)
            from tracevision.permissions import HasClipReelAccess

            # Check if user has access to reel
            permission = HasClipReelAccess()
            if not permission.has_object_permission(request, self, clip_reel):
                return Response(
                    {"error": "You don't have access to this reel."},
                    status=http_status.HTTP_403_FORBIDDEN,
                )

            # Filter comments based on visibility
            comments = TraceClipReelComment.objects.filter(
                clip_reel=clip_reel, is_deleted=False, parent_comment__isnull=True
            )

            # Filter by visibility
            user = request.user
            is_owner = clip_reel.primary_player and clip_reel.primary_player.user == user

            if not is_owner:
                # Non-owners only see public comments and their own private comments
                comments = comments.filter(
                    Q(visibility="public") | Q(author=user)
                )

            serializer = TraceClipReelCommentSerializer(
                comments, many=True, context={"request": request}
            )

            return Response({"comments": serializer.data}, status=http_status.HTTP_200_OK)

        elif request.method == "POST":
            # Add a comment
            from tracevision.permissions import CanCommentOnClipReel

            # Check if user can comment
            permission = CanCommentOnClipReel()
            if not permission.has_object_permission(request, self, clip_reel):
                return Response(
                    {"error": "You don't have permission to comment on this reel."},
                    status=http_status.HTTP_403_FORBIDDEN,
                )

            data = request.data.copy()
            data["clip_reel_id"] = clip_reel.id
            data["highlight_id"] = clip_reel.highlight.id if clip_reel.highlight else None

            serializer = TraceClipReelCommentSerializer(data=data, context={"request": request})

            if serializer.is_valid():
                serializer.save()
                return Response(
                    {"message": "Comment added successfully", "data": serializer.data},
                    status=http_status.HTTP_201_CREATED,
                )

            return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="notes")
    def add_note(self, request, pk=None):
        """
        Add a private note to clip reel.
        POST /api/tracevision/clip-reels/{id}/notes/
        """
        from tracevision.permissions import IsPlayerOrCoach

        clip_reel = self.get_object()

        # Check if user is Player or Coach
        permission = IsPlayerOrCoach()
        if not permission.has_permission(request, self):
            return Response(
                {"error": "Only Players and Coaches can create notes."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data["clip_reel_id"] = clip_reel.id
        data["highlight_id"] = clip_reel.highlight.id if clip_reel.highlight else None

        serializer = TraceClipReelNoteSerializer(data=data, context={"request": request})

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Note created successfully", "data": serializer.data},
                status=http_status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="notes")
    def list_notes(self, request, pk=None):
        """
        List notes on clip reel (only accessible ones).
        GET /api/tracevision/clip-reels/{id}/notes/
        """
        clip_reel = self.get_object()
        user = request.user

        # Get all notes for this reel
        notes = TraceClipReelNote.objects.filter(clip_reel=clip_reel, is_deleted=False)

        # Filter notes based on can_view permission
        accessible_notes = [note for note in notes if note.can_view(user)]

        serializer = TraceClipReelNoteSerializer(
            accessible_notes, many=True, context={"request": request}
        )

        return Response({"notes": serializer.data}, status=http_status.HTTP_200_OK)


class TraceClipReelCommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing comments (edit, delete, like, reply).
    """

    queryset = TraceClipReelComment.objects.filter(is_deleted=False)
    serializer_class = TraceClipReelCommentSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Use different serializer for update"""
        if self.action == "update" or self.action == "partial_update":
            return TraceClipReelCommentEditSerializer
        return TraceClipReelCommentSerializer

    def partial_update(self, request, *args, **kwargs):
        """
        Edit comment (PATCH).
        PATCH /api/tracevision/comments/{id}/
        """
        from tracevision.permissions import IsCommentAuthor

        comment = self.get_object()

        # Only author can edit
        permission = IsCommentAuthor()
        if not permission.has_object_permission(request, self, comment):
            return Response(
                {"error": "Only the comment author can edit it."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(comment, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Comment updated successfully",
                    "data": TraceClipReelCommentSerializer(
                        comment, context={"request": request}
                    ).data,
                },
                status=http_status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete comment.
        DELETE /api/tracevision/comments/{id}/
        """
        from tracevision.permissions import IsCommentAuthor

        comment = self.get_object()

        # Only author can delete
        permission = IsCommentAuthor()
        if not permission.has_object_permission(request, self, comment):
            return Response(
                {"error": "Only the comment author can delete it."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        comment.soft_delete()

        return Response(
            {"message": "Comment deleted successfully"},
            status=http_status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="like")
    def like_comment(self, request, pk=None):
        """
        Like a comment.
        POST /api/tracevision/comments/{id}/like/
        """
        comment = self.get_object()

        # Check if user can view comment
        if not comment.can_view(request.user):
            return Response(
                {"error": "You don't have access to this comment."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        # Check if already liked
        if TraceClipReelCommentLike.objects.filter(
            comment=comment, user=request.user
        ).exists():
            return Response(
                {"error": "You have already liked this comment."},
                status=http_status.HTTP_400_BAD_REQUEST,
            )

        like = TraceClipReelCommentLike.objects.create(
            comment=comment, user=request.user
        )

        return Response(
            {
                "message": "Comment liked successfully",
                "likes_count": comment.likes_count,
            },
            status=http_status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["delete"], url_path="like")
    def unlike_comment(self, request, pk=None):
        """
        Unlike a comment.
        DELETE /api/tracevision/comments/{id}/like/
        """
        comment = self.get_object()

        try:
            like = TraceClipReelCommentLike.objects.get(
                comment=comment, user=request.user
            )
            like.delete()

            return Response(
                {
                    "message": "Comment unliked successfully",
                    "likes_count": comment.likes_count,
                },
                status=http_status.HTTP_200_OK,
            )
        except TraceClipReelCommentLike.DoesNotExist:
            return Response(
                {"error": "You haven't liked this comment."},
                status=http_status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"], url_path="reply")
    def add_reply(self, request, pk=None):
        """
        Add a reply to a comment.
        POST /api/tracevision/comments/{id}/reply/
        """
        parent_comment = self.get_object()

        # Check if user can view parent comment
        if not parent_comment.can_view(request.user):
            return Response(
                {"error": "You don't have access to this comment."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        # Check if user can comment on the reel
        from tracevision.permissions import CanCommentOnClipReel

        permission = CanCommentOnClipReel()
        if not permission.has_object_permission(
            request, self, parent_comment.clip_reel
        ):
            return Response(
                {"error": "You don't have permission to comment on this reel."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        data = request.data.copy()
        data["clip_reel_id"] = parent_comment.clip_reel.id
        data["highlight_id"] = parent_comment.highlight.id
        data["parent_comment"] = parent_comment.id

        serializer = TraceClipReelCommentSerializer(data=data, context={"request": request})

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Reply added successfully", "data": serializer.data},
                status=http_status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["get"], url_path="replies")
    def list_replies(self, request, pk=None):
        """
        List replies to a comment.
        GET /api/tracevision/comments/{id}/replies/
        """
        parent_comment = self.get_object()

        # Check if user can view parent comment
        if not parent_comment.can_view(request.user):
            return Response(
                {"error": "You don't have access to this comment."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        replies = TraceClipReelComment.objects.filter(
            parent_comment=parent_comment, is_deleted=False
        )

        serializer = TraceClipReelCommentSerializer(
            replies, many=True, context={"request": request}
        )

        return Response({"replies": serializer.data}, status=http_status.HTTP_200_OK)


class TraceClipReelNoteViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing notes (edit, delete, share).
    """

    queryset = TraceClipReelNote.objects.filter(is_deleted=False)
    serializer_class = TraceClipReelNoteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        return TraceClipReel.objects.filter(
            Q(primary_player__user=user) |
            Q(
                shares__shared_with=user,
                shares__is_active=True
            )
        ).distinct()

    def partial_update(self, request, *args, **kwargs):
        """
        Edit note (PATCH).
        PATCH /api/tracevision/notes/{id}/
        """
        from tracevision.permissions import IsNoteAuthor

        note = self.get_object()

        # Only author can edit
        permission = IsNoteAuthor()
        if not permission.has_object_permission(request, self, note):
            return Response(
                {"error": "Only the note author can edit it."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(note, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Note updated successfully", "data": serializer.data},
                status=http_status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete note.
        DELETE /api/tracevision/notes/{id}/
        """
        from tracevision.permissions import IsNoteAuthor

        note = self.get_object()

        # Only author can delete
        permission = IsNoteAuthor()
        if not permission.has_object_permission(request, self, note):
            return Response(
                {"error": "Only the note author can delete it."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        note.soft_delete()

        return Response(
            {"message": "Note deleted successfully"},
            status=http_status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="share")
    def share_note(self, request, pk=None):
        """
        Share note with user or group.
        POST /api/tracevision/notes/{id}/share/
        """
        note = self.get_object()

        data = request.data.copy()
        data["note"] = note.id

        serializer = TraceClipReelNoteShareSerializer(
            data=data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Note shared successfully", "data": serializer.data},
                status=http_status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=http_status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["delete"], url_path="shares/(?P<share_id>[^/.]+)")
    def revoke_share(self, request, pk=None, share_id=None):
        """
        Revoke note share.
        DELETE /api/tracevision/notes/{id}/shares/{share_id}/
        """
        from tracevision.permissions import IsNoteAuthor

        note = self.get_object()

        # Only author can revoke shares
        permission = IsNoteAuthor()
        if not permission.has_object_permission(request, self, note):
            return Response(
                {"error": "Only the note author can revoke shares."},
                status=http_status.HTTP_403_FORBIDDEN,
            )

        try:
            share = TraceClipReelNoteShare.objects.get(id=share_id,clip_reel=clip_reel,is_active=True,)
            share.is_active = False
            share.save()

            return Response(
                {"message": "Note share revoked successfully"},
                status=http_status.HTTP_200_OK,
            )
        except TraceClipReelNoteShare.DoesNotExist:
            return Response(
                {"error": "Share not found"},
                status=http_status.HTTP_404_NOT_FOUND,
            )


class GameUsersListView(APIView):
    """
    List all players and coaches associated with a specific game via session.
    Includes users from home team, away team, and GameUserRole.
    Filters out users without contact information (email or phone).
    
    GET /api/vision/sessions/{session_id}/users/
    
    Query Parameters:
    - role: Filter by role - "Player", "Coach", or "all" (default: "all")
    - registered_only: Show only registered users (default: true)
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, session_id):
        """
        List users associated with a game via session.
        
        Args:
            session_id: ID of the TraceSession
            
        Query Parameters:
            role: "Player", "Coach", or "all" (default: "all")
            registered_only: Boolean (default: true)
        """
        from tracevision.serializers import GameUserSerializer
        from django.shortcuts import get_object_or_404
        from accounts.models import WajoUser
        
        # Get query parameters
        role_filter = request.query_params.get("role", "all").strip()
        registered_only = request.query_params.get("registered_only", "true").lower() in ["true", "1", "yes"]
        
        # Validate role parameter
        if role_filter not in ["Player", "Coach", "all"]:
            return Response(
                {
                    "error": "Invalid role parameter",
                    "details": "Role must be 'Player', 'Coach', or 'all'"
                },
                status=http_status.HTTP_400_BAD_REQUEST
            )
        
        # Get session
        session = get_object_or_404(TraceSession, id=session_id)
        
        # Collect user IDs from multiple sources
        user_ids = set()
        
        # Source 1: Users from GameUserRole (if game exists)
        if session.game:
            game_user_roles = GameUserRole.objects.filter(
                game=session.game,
                deleted_at__isnull=True
            ).select_related("user")
            
            user_ids.update([gur.user.id for gur in game_user_roles if gur.user])
        
        # Source 2: Players from home team
        if session.home_team:
            home_players = WajoUser.objects.filter(
                team=session.home_team,
                role="Player"
            ).values_list("id", flat=True)
            user_ids.update(home_players)
            
            # Coaches of home team
            home_coaches = WajoUser.objects.filter(
                teams_coached=session.home_team,
                role="Coach"
            ).values_list("id", flat=True)
            user_ids.update(home_coaches)
        
        # Source 3: Players from away team
        if session.away_team:
            away_players = WajoUser.objects.filter(
                team=session.away_team,
                role="Player"
            ).values_list("id", flat=True)
            user_ids.update(away_players)
            
            # Coaches of away team
            away_coaches = WajoUser.objects.filter(
                teams_coached=session.away_team,
                role="Coach"
            ).values_list("id", flat=True)
            user_ids.update(away_coaches)
        
        # Query users with all collected IDs
        users_queryset = WajoUser.objects.filter(id__in=user_ids)
        
        # Filter 1: Exclude users without contact information
        # User must have at least email OR phone_no
        users_queryset = users_queryset.filter(
            Q(email__isnull=False, email__gt="") | 
            Q(phone_no__isnull=False, phone_no__gt="")
        )
        
        # Filter 2: Registration status
        if registered_only:
            users_queryset = users_queryset.filter(is_registered=True)
        
        # Filter 3: Role filter
        if role_filter != "all":
            users_queryset = users_queryset.filter(role=role_filter)
        
        # Order by role (Coach first, then Player) and name
        users_queryset = users_queryset.order_by("role", "name")
        
        # Separate users by team (only include users with team association)
        home_team_users = []
        away_team_users = []
        
        for user in users_queryset:
            # Check if user belongs to home team
            if session.home_team and user.team and user.team.id == session.home_team.id:
                home_team_users.append(user)
            # Check if user belongs to away team
            elif session.away_team and user.team and user.team.id == session.away_team.id:
                away_team_users.append(user)
            # Check if user is a coach of home team
            elif session.home_team and user.role == "Coach" and user.teams_coached.filter(id=session.home_team.id).exists():
                home_team_users.append(user)
            # Check if user is a coach of away team
            elif session.away_team and user.role == "Coach" and user.teams_coached.filter(id=session.away_team.id).exists():
                away_team_users.append(user)
            # Skip users not associated with either team
        
        # Serialize each group
        home_team_serializer = GameUserSerializer(
            home_team_users,
            many=True,
            context={"request": request}
        )
        
        away_team_serializer = GameUserSerializer(
            away_team_users,
            many=True,
            context={"request": request}
        )
        
        # Calculate total count (only team-associated users)
        total_count = len(home_team_users) + len(away_team_users)
        
        # Get user's language preference for team name localization
        user_language = "en"
        if request.user:
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        return Response(
            {
                "count": total_count,
                "session_id": session_id,
                "game_id": session.game.id if session.game else None,
                "home_team": {
                    "id": session.home_team.id if session.home_team else None,
                    "name": get_localized_team_name(session.home_team, user_language) if session.home_team else None,
                    "users": home_team_serializer.data
                },
                "away_team": {
                    "id": session.away_team.id if session.away_team else None,
                    "name": get_localized_team_name(session.away_team, user_language) if session.away_team else None,
                    "users": away_team_serializer.data
                },
                "filters": {
                    "role": role_filter,
                    "registered_only": registered_only
                }
            },
            status=http_status.HTTP_200_OK
        )


class SessionHighlightsView(ListAPIView):
    """
    API endpoint to get highlights for a specific session with role-based filtering.
    
    URL: /api/vision/sessions/<session_id>/highlights/
    
    Role-based filtering:
    - Coach: Returns all highlights for all players in the coach's team
    - Player: Returns only the logged-in player's own highlights
    """
    
    permission_classes = [IsAuthenticated]
    serializer_class = HighlightClipReelSerializer
    pagination_class = HighlightPagination
    
    def get_queryset(self):
        """Get highlights filtered by user role and shared highlights"""
        session_id = self.kwargs.get("session_id")
        user = self.request.user
        
        # Get games where user has GameUserRole
        user_games = Game.objects.filter(
            game_roles__user=user
        ).values_list("id", flat=True)
        
        # Get session and verify user has access
        try:
            session = (
                TraceSession.objects.select_related("home_team", "away_team")
                .filter(
                    Q(id=session_id)
                    & (
                        Q(user=user)
                        | Q(game__id__in=user_games)
                        | Q(home_team=user.team)
                        | Q(away_team=user.team)
                    )
                )
                .get()
            )
        except TraceSession.DoesNotExist:
            return TraceHighlight.objects.none()
        
        # Base queryset with optimized selects
        base_queryset = (
            TraceHighlight.objects.filter(session=session)
            .select_related("player__team", "session__home_team", "session__away_team")
            .prefetch_related(
                Prefetch(
                    "clip_reels",
                    queryset=TraceClipReel.objects.select_related(
                        "primary_player", "primary_player__team"
                    ),
                )
            )
        )
        
        # Build role-based filter conditions
        role_filter = Q()
        
        if user.role == "Coach":
            # Get all players that have this coach assigned
            coach_players = user.players.all()
            
            # Get TracePlayer IDs for these WajoUsers
            trace_player_ids = TracePlayer.objects.filter(
                user__in=coach_players
            ).values_list("id", flat=True)
            
            # Filter highlights where the player is in the coach's player list
            role_filter = Q(player_id__in=trace_player_ids)
            
        elif user.role == "Player":
            # Get the player's TracePlayer record(s)
            trace_players = TracePlayer.objects.filter(user=user)
            
            # Filter highlights where the player matches
            role_filter = Q(player__in=trace_players)
        else:
            # For other roles (Referee, etc.), return empty queryset
            return TraceHighlight.objects.none()
        
        # Add filter for highlights shared with the user via TraceClipReelShare
        shared_filter = Q(
            reel_shares__shared_with=user,
            reel_shares__is_active=True
        )
        
        # Combine filters: user's own highlights OR shared highlights
        queryset = base_queryset.filter(role_filter | shared_filter).distinct()
        
        return queryset.order_by("-created_at")
    
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
        
        return context


class BulkHighlightShareView(APIView):
    """
    API endpoint to share a highlight with multiple users in a single request.
    
    POST /api/vision/highlights/share/
    
    Request Body:
    {
        "highlight_id": 123,
        "user_ids": ["uuid1", "uuid2", "uuid3"],
        "can_comment": true
    }
    
    Supports both Player and Coach roles.
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Share a highlight with multiple users"""
        serializer = BulkHighlightShareSerializer(
            data=request.data,
            context={"request": request}
        )
        
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "errors": serializer.errors
                },
                status=http_status.HTTP_400_BAD_REQUEST
            )
        
        try:
            result = serializer.save()
            
            # Calculate summary statistics
            total_created = sum(share["shares_created"] for share in result["shares"])
            total_updated = sum(share["shares_updated"] for share in result["shares"])
            successful_shares = sum(1 for share in result["shares"] if share["status"] == "success")
            skipped_shares = sum(1 for share in result["shares"] if share["status"] == "skipped")
            
            return Response(
                {
                    "success": True,
                    "highlight_id": result["highlight_id"],
                    "clip_reels_count": result["clip_reels_count"],
                    "recipients_count": result["recipients_count"],
                    "summary": {
                        "successful_shares": successful_shares,
                        "skipped_shares": skipped_shares,
                        "total_shares_created": total_created,
                        "total_shares_updated": total_updated
                    },
                    "shares": result["shares"]
                },
                status=http_status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.exception(f"Error sharing highlight: {str(e)}")
            return Response(
                {
                    "success": False,
                    "error": "Internal server error",
                    "details": str(e)
                },
                status=http_status.HTTP_500_INTERNAL_SERVER_ERROR
            )
