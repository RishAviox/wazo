import uuid
import logging
import requests
from django.db.models import Q
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


from tracevision.models import (
    TraceSession,
    TraceClipReel,
    TracePlayer,
    TraceHighlight,
    TraceClipReelShare,
    TraceClipReelComment,
    TraceClipReelCommentLike,
    TraceClipReelCommentEditHistory,
    TraceClipReelNote,
    TraceClipReelNoteShare,
)
from tracevision.utils import (
    get_hex_from_color_name,
    get_viewer_team,
    determine_viewer_perspective,
    transform_side_by_perspective,
    check_duplicate_game,
    get_or_create_canonical_game,
    get_localized_team_name,
    get_localized_player_name,
    get_localized_name,
)
from teams.models import Team
from tracevision.models import TraceSession
from games.models import GameUserRole
from tracevision.services import TraceVisionService
from accounts.models import WajoUser

logger = logging.getLogger(__name__)

# Import Celery task at module level to avoid import issues
try:
    from tracevision.tasks import process_excel_and_create_players_task
except ImportError:
    process_excel_and_create_players_task = None
    logger.warning("Could not import process_excel_and_create_players_task")


class TraceClipReelSerializer(serializers.ModelSerializer):
    age_group = serializers.CharField(source="session.age_group", read_only=True)
    match_date = serializers.DateField(source="session.match_date", read_only=True)

    class Meta:
        model = TraceClipReel
        fields = "__all__"
        extra_fields = ["age_group", "match_date"]


class TraceVisionProcessesSerializer(serializers.ModelSerializer):
    home_team_name = serializers.SerializerMethodField()
    away_team_name = serializers.SerializerMethodField()
    home_team_jersey_color = serializers.CharField(
        source="home_team.jersey_color", read_only=True
    )
    away_team_jersey_color = serializers.CharField(
        source="away_team.jersey_color", read_only=True
    )

    def get_home_team_name(self, obj):
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return (
            get_localized_team_name(obj.home_team, user_language)
            if obj.home_team
            else None
        )

    def get_away_team_name(self, obj):
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return (
            get_localized_team_name(obj.away_team, user_language)
            if obj.away_team
            else None
        )

    class Meta:
        model = TraceSession
        fields = "__all__"
        read_only_fields = ["id", "user"]


class TraceSessionListSerializer(serializers.ModelSerializer):
    """
    Serializer for TraceSession list view with essential information and filtering
    """

    home_team_name = serializers.SerializerMethodField()
    away_team_name = serializers.SerializerMethodField()

    def get_home_team_name(self, obj):
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return (
            get_localized_team_name(obj.home_team, user_language)
            if obj.home_team
            else None
        )

    def get_away_team_name(self, obj):
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return (
            get_localized_team_name(obj.away_team, user_language)
            if obj.away_team
            else None
        )

    home_team_jersey_color = serializers.CharField(
        source="home_team.jersey_color", read_only=True
    )
    away_team_jersey_color = serializers.CharField(
        source="away_team.jersey_color", read_only=True
    )
    pitch_dimensions = serializers.CharField(
        source="get_pitch_dimensions", read_only=True
    )

    # Filter fields
    match_date = serializers.DateField(
        required=False, help_text="Filter by exact match date (YYYY-MM-DD)"
    )
    created_at = serializers.DateTimeField(
        required=False, help_text="Filter by creation date (YYYY-MM-DD HH:MM:SS)"
    )
    status = serializers.ChoiceField(
        choices=["waiting_for_data", "processing", "processed", "process_error"],
        required=False,
        # write_only=True,
        help_text="Filter by session status",
    )
    age_group = serializers.ChoiceField(
        choices=["U11_U12", "U13_U14", "U15_U16", "U17_U18", "SENIOR"],
        required=False,
        # write_only=True,
        help_text="Filter by age group",
    )
    team_name = serializers.CharField(
        max_length=100,
        required=False,
        # write_only=True,
        help_text="Filter by team name (searches both home and away teams)",
    )

    class Meta:
        model = TraceSession
        fields = [
            "id",
            "session_id",
            "status",
            "user",
            "match_date",
            "home_team_name",
            "away_team_name",
            "home_score",
            "away_score",
            "home_team_jersey_color",
            "away_team_jersey_color",
            "age_group",
            "pitch_size",
            "pitch_dimensions",
            "final_score",
            "start_time",
            "video_url",
            "created_at",
            "updated_at",
            # Filter fields
            "match_date",
            "created_at",
            "status",
            "age_group",
            "team_name",
        ]
        read_only_fields = [
            "id",
            "session_id",
            "status",
            "user",
            "match_date",
            "home_team",
            "away_team",
            "home_team_name",
            "away_team_name",
            "home_score",
            "away_score",
            "home_team_jersey_color",
            "away_team_jersey_color",
            "age_group",
            "pitch_size",
            "pitch_dimensions",
            "final_score",
            "start_time",
            "video_url",
            "created_at",
            "updated_at",
        ]

    def validate_match_date(self, value):
        """Validate match_date format"""
        if value:
            return value
        return None

    def validate_created_at(self, value):
        """Validate created_at format"""
        if value:
            return value
        return None

    @classmethod
    def get_filtered_queryset(cls, queryset, validated_data):
        """
        Apply filters to queryset based on validated data
        """

        # Created date filter
        if validated_data.get("created_at"):
            queryset = queryset.filter(
                created_at__date=validated_data["created_at"].date()
            )

        # Status filter
        if validated_data.get("status"):
            queryset = queryset.filter(status=validated_data["status"])

        # Match date filter
        if validated_data.get("match_date"):
            queryset = queryset.filter(match_date=validated_data["match_date"])

        # Age group filter
        if validated_data.get("age_group"):
            queryset = queryset.filter(age_group=validated_data["age_group"])

        # Team name filter (searches both home_team and away_team)
        if validated_data.get("team_name"):
            queryset = queryset.filter(
                Q(home_team__name__icontains=validated_data["team_name"])
                | Q(away_team__name__icontains=validated_data["team_name"])
            )

        return queryset.order_by("-updated_at", "-created_at")


class TraceVisionProcessSerializer(serializers.Serializer):
    """
    Serializer for TraceVision process API with validation according to Figma requirements.
    Supports both video link and video file upload options.
    """

    # Video options - either video_link OR video_file, not both
    video_link = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
        help_text="URL to the video file (alternative to video_file upload)",
    )
    video_file = serializers.FileField(
        required=False,
        allow_empty_file=False,
        help_text="Video file to upload (alternative to video_link)",
    )

    # Team information
    home_team_name = serializers.CharField(
        max_length=100, required=True, help_text="Name of the home team"
    )
    away_team_name = serializers.CharField(
        max_length=100, required=True, help_text="Name of the away team"
    )
    home_team_jersey_color = serializers.CharField(
        max_length=7,
        required=True,
        help_text="Hex color code for home team jersey (e.g., #FF0000)",
    )
    away_team_jersey_color = serializers.CharField(
        max_length=7,
        required=True,
        help_text="Hex color code for away team jersey (e.g., #0000FF)",
    )
    final_score = serializers.CharField(
        required=True,
        help_text="Final score of the match in format 'home_score-away_score' (e.g., '2-1', '0-0'). Use '0-0' for no score.",
    )
    game_date = serializers.DateField(
        required=True, help_text="Date of the game (required, format: YYYY-MM-DD)"
    )
    game_time = serializers.TimeField(
        required=False,
        allow_null=True,
        help_text="Time of the game (optional, format: HH:MM:SS)",
    )
    start_time = serializers.DateTimeField(
        required=False, help_text="Start time of the video, if known (optional)"
    )
    match_start_time = serializers.CharField(
        required=False, help_text="Match start time in format 'HH:MM:SS' (optional)"
    )
    first_half_end_time = serializers.CharField(
        required=False, help_text="First half end time in format 'HH:MM:SS' (optional)"
    )
    second_half_start_time = serializers.CharField(
        required=False,
        help_text="Second half start time in format 'HH:MM:SS' (optional)",
    )
    match_end_time = serializers.CharField(
        required=False, help_text="Match end time in format 'HH:MM:SS' (optional)"
    )
    basic_game_stats = serializers.FileField(
        required=False, help_text="Basic game stats file (optional)"
    )

    # Age group and pitch size fields
    age_group = serializers.ChoiceField(
        choices=[
            ("U11_U12", "U11-U12 (9v9)"),
            ("U13_U14", "U13-U14 (11v11)"),
            ("U15_U16", "U15-U16 (11v11)"),
            ("U17_U18", "U17-U18 (11v11)"),
            ("SENIOR", "Senior (18+)"),
        ],
        required=False,
        default="SENIOR",
        allow_blank=True,
        allow_null=True,
        help_text="Age group of the players (defaults to SENIOR if not provided)",
    )

    # Optional custom pitch size (if user wants to override default)
    pitch_length = serializers.FloatField(
        required=False,
        min_value=50,
        max_value=130,
        help_text="Custom pitch length in meters (optional, will use age group default if not provided)",
    )
    pitch_width = serializers.FloatField(
        required=False,
        min_value=30,
        max_value=100,
        help_text="Custom pitch width in meters (optional, will use age group default if not provided)",
    )

    def validate_video_file(self, value):
        """Validate video file field."""
        if value is None:
            return None
        return value

    def validate_video_link(self, value):
        """Validate video link field."""
        if value is None or value == "":
            return None
        return value

    def validate(self, data):
        """Additional validation rules."""

        request = self.context.get("request")
        if request and request.user:
            user = request.user

            # Task 2: A WajoUser (player) should not be able to upload the game if jersey number is not selected
            # Check if user is a player (not a coach)
            if user.role != "Coach":
                if not user.jersey_number:
                    raise serializers.ValidationError(
                        {
                            "error": "Jersey number required",
                            "message": "Please select your jersey number in your profile to upload a game.",
                        }
                    )

            # Check if user belongs to a team (for coaches, check teams_coached)
            # has_team = False
            # if user.role == "Coach":
            #     has_team = user.teams_coached.exists()
            # else:
            #     # For players and other roles, check team ForeignKey
            #     has_team = user.team is not None

            # if not has_team:
            #     raise serializers.ValidationError(
            #         {
            #             "error": "Team required",
            #             "message": "Please select your team in your profile to continue.",
            #         }
            #     )

        # Ensure team names are different
        if data["home_team_name"].lower() == data["away_team_name"].lower():
            raise serializers.ValidationError(
                "Home team and away team names must be different"
            )

        # Ensure either video_link OR video_file is provided, but not both
        video_link = data.get("video_link")
        video_file = data.get("video_file")

        # Check if video_link is empty string and treat as None
        if video_link == "":
            video_link = None

        # Check if video_file is provided - currently not supported
        if video_file:
            raise serializers.ValidationError(
                {
                    "error": "Video file upload not supported",
                    "message": "Video file upload is currently not supported. Please use video_link instead to provide a URL to your video.",
                }
            )

        if not video_link and not video_file:
            raise serializers.ValidationError(
                "Either video_link or video_file must be provided"
            )

        if video_link and video_file:
            raise serializers.ValidationError(
                "Cannot provide both video_link and video_file. Choose one option."
            )
        return data

    def validate_home_team_jersey_color(self, value):
        """Validate hex color format."""

        hex_color = get_hex_from_color_name(value)
        if not hex_color:
            raise serializers.ValidationError(f"Invalid color name: {value}")

        if not hex_color.startswith("#") or len(hex_color) != 7:
            raise serializers.ValidationError(
                "Home team jersey color must be a valid hex color (e.g., #FF0000)"
            )

        # Check if the hex value is valid
        try:
            int(hex_color[1:], 16)
        except ValueError:
            raise serializers.ValidationError(
                "Home team jersey color must be a valid hex color"
            )

        return hex_color

    def validate_away_team_jersey_color(self, value):
        """Validate hex color format."""
        hex_color = get_hex_from_color_name(value)
        if not hex_color:
            raise serializers.ValidationError(f"Invalid color name: {value}")

        if not hex_color.startswith("#") or len(hex_color) != 7:
            raise serializers.ValidationError(
                "Away team jersey color must be a valid hex color (e.g., #0000FF)"
            )

        # Check if the hex value is valid
        try:
            int(hex_color[1:], 16)
        except ValueError:
            raise serializers.ValidationError(
                "Away team jersey color must be a valid hex color"
            )

        return hex_color

    def validate_home_team_name(self, value):
        """Validate home team name is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Home team name cannot be empty")
        return value.strip()

    def validate_away_team_name(self, value):
        """Validate away team name is not empty."""
        if not value.strip():
            raise serializers.ValidationError("Away team name cannot be empty")
        return value.strip()

    def validate_final_score(self, value):
        """Validate final score format (home_score-away_score)."""
        if not value or value.strip() == "":
            raise serializers.ValidationError(
                "Final score is required. Use '0-0' if there is no score."
            )

        value = value.strip()
        # Check if it contains exactly one dash

        if value.count("-") != 1:
            raise serializers.ValidationError(
                "Final score must be in format 'home_score-away_score' (e.g., '2-1', '0-0')"
            )

        # Split and validate both parts
        try:
            home_score_str, away_score_str = value.split("-")

            # Validate both scores are non-negative integers
            home_score = int(home_score_str)
            away_score = int(away_score_str)

            if home_score < 0 or away_score < 0:
                raise serializers.ValidationError(
                    "Both home and away scores must be non-negative integers"
                )

        except ValueError:
            raise serializers.ValidationError(
                "Final score must contain valid integers in format 'home_score-away_score' (e.g., '2-1', '0-0')"
            )

        return value

    def validate_basic_game_stats(self, value):
        """
        Validate that the basic_game_stats CSV file contains all required tabs with correct columns.
        Supports both single-language and multilingual (en/he) sheet formats.
        """
        if not value:
            return value

        import pandas as pd

        try:
            # Read the Excel file
            excel_file = pd.ExcelFile(value)

            # Define required tabs (base names without language suffix)
            required_base_tabs = [
                "Match_Summary",
                "Starting_Lineups",
                "Replacements",
                "Bench",
                "Coaches",
                "Referees",
            ]

            # Define required columns for each tab
            required_columns = {
                "Match_Summary": [],  # No specific columns required
                "Starting_Lineups": [
                    "Team",
                    "Number",
                    "Name",
                    "Role",
                    "Goals",
                    "SubOffMinute",
                    "Cards",
                ],
                "Replacements": [
                    "Team",
                    "Number",
                    "Name",
                    "Role",
                    "Goals",
                    "ReplacerMinute",
                ],
                "Bench": ["Team", "Number", "Name"],
                "Coaches": ["Team", "Coach Name", "Role"],
                "Referees": ["Position", "Name"],
            }

            errors = []
            available_tabs = excel_file.sheet_names

            # Check if all required tabs exist (support both single-language and multilingual formats)
            missing_tabs = []
            found_tabs = {}  # Track which base tabs we found

            for base_tab in required_base_tabs:
                # Check for exact match (single-language format)
                if base_tab in available_tabs:
                    found_tabs[base_tab] = base_tab
                    continue

                # Check for multilingual format (_en and _he suffixes)
                en_tab = f"{base_tab}_en"
                he_tab = f"{base_tab}_he"

                if en_tab in available_tabs or he_tab in available_tabs:
                    # At least one language version exists
                    if en_tab in available_tabs:
                        found_tabs[base_tab] = en_tab
                    elif he_tab in available_tabs:
                        found_tabs[base_tab] = he_tab
                    continue

                # Tab not found in any format
                missing_tabs.append(base_tab)

            if missing_tabs:
                errors.append(
                    f"Missing required tabs: {', '.join(missing_tabs)}. Expected either '{missing_tabs[0]}' or '{missing_tabs[0]}_en'/'{missing_tabs[0]}_he' format."
                )

            # Check columns for each found tab (use English version if available, otherwise Hebrew)
            for base_tab, actual_tab_name in found_tabs.items():
                required_cols = required_columns.get(base_tab, [])
                if not required_cols:  # Skip column check if no columns required
                    continue

                try:
                    df = pd.read_excel(value, sheet_name=actual_tab_name)
                    actual_columns = df.columns.tolist()

                    # Check if all required columns exist
                    missing_columns = []
                    for col in required_cols:
                        if col not in actual_columns:
                            missing_columns.append(col)

                    if missing_columns:
                        errors.append(
                            f"Tab '{actual_tab_name}' is missing required columns: {', '.join(missing_columns)}"
                        )

                except Exception as e:
                    errors.append(f"Error reading tab '{actual_tab_name}': {str(e)}")

            # Check if file is empty or has no data
            if not available_tabs:
                errors.append("The Excel file appears to be empty or corrupted")

            # If there are any errors, raise validation error
            if errors:
                raise serializers.ValidationError(
                    {
                        "error": "Excel file validation failed",
                        "details": errors,
                        "message": "Please fix the Excel file errors before uploading. Session will not be created until Excel data is valid.",
                    }
                )

            return value

        except pd.errors.EmptyDataError:
            raise serializers.ValidationError(
                {
                    "error": "Excel file validation error",
                    "details": "The Excel file appears to be empty or corrupted",
                    "message": "Please upload a valid Excel file with match data.",
                }
            )
        except Exception as e:
            raise serializers.ValidationError(
                {
                    "error": "Excel file validation error",
                    "details": {"error": str(e)},
                    "message": f"Error reading Excel file: {str(e)}. Session will not be created until Excel data is valid.",
                }
            )

    def _validate_and_extract_excel_teams(
        self, excel_file, home_team_name, away_team_name
    ):
        """
        Validate Excel file team names match request team names and extract match data.
        This is called FIRST before any DB operations to prevent creating invalid data.

        Args:
            excel_file: Excel file from request
            home_team_name: Home team name from request
            away_team_name: Away team name from request

        Returns:
            dict: Match data with language_metadata if validation passes

        Raises:
            ValidationError if Excel data doesn't match input team names
        """
        import tempfile
        import os
        from tracevision.utils import extract_multilingual_match_data

        # Create temporary file
        suffix = os.path.splitext(excel_file.name)[1] or ".xlsx"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            for chunk in excel_file.chunks():
                tmp_file.write(chunk)
            tmp_file_path = tmp_file.name

        try:
            # Extract multilingual data
            logger.info(f"Validating Excel file before creating any database objects")
            match_data = extract_multilingual_match_data(tmp_file_path)

            # Extract team names from Excel (both languages)
            excel_teams = {
                "home": {"en": None, "he": None},
                "away": {"en": None, "he": None},
            }

            # Get team names from English and Hebrew sections
            for lang in ["en", "he"]:
                if lang in match_data and "Match_summary" in match_data[lang]:
                    summary = match_data[lang]["Match_summary"]
                    excel_teams["home"][lang] = summary.get("match_home_team")
                    excel_teams["away"][lang] = summary.get("match_away_team")

            # Normalize names for comparison
            def normalize(name):
                return name.strip().lower() if name else ""

            input_home = normalize(home_team_name)
            input_away = normalize(away_team_name)

            # Validate Home Team - must match at least one language
            excel_home_names = [
                normalize(excel_teams["home"]["en"]),
                normalize(excel_teams["home"]["he"]),
            ]
            if input_home not in excel_home_names:
                raise ValidationError(
                    {
                        "error": "Team name mismatch",
                        "message": f"Home team name '{home_team_name}' does not match the Excel file data.",
                        "details": f"Excel file contains: EN='{excel_teams['home']['en']}', HE='{excel_teams['home']['he']}'",
                    }
                )

            # Validate Away Team - must match at least one language
            excel_away_names = [
                normalize(excel_teams["away"]["en"]),
                normalize(excel_teams["away"]["he"]),
            ]
            if input_away not in excel_away_names:
                raise ValidationError(
                    {
                        "error": "Team name mismatch",
                        "message": f"Away team name '{away_team_name}' does not match the Excel file data.",
                        "details": f"Excel file contains: EN='{excel_teams['away']['en']}', HE='{excel_teams['away']['he']}'",
                    }
                )

            # Validation passed - return match data
            logger.info(f"Excel validation passed - team names match")
            return match_data

        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error processing basic_game_stats: {e}", exc_info=True)
            raise ValidationError(
                {
                    "error": "File processing error",
                    "message": f"Failed to process the game stats file: {str(e)}",
                }
            )
        finally:
            # Clean up temp file
            if os.path.exists(tmp_file_path):
                try:
                    os.unlink(tmp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {tmp_file_path}: {e}")

    def _validate_user_team_assignment(self, user, home_team_name, away_team_name):
        """
        Validate that user's team matches the home team (for players only).

        Args:
            user: WajoUser instance
            home_team_name: Home team name from request
            away_team_name: Away team name from request

        Raises:
            ValidationError if team assignment is invalid
        """
        if user.role == "Coach" or not user.team:
            return  # Skip validation for coaches or users without teams

        user_team_name = user.team.name or ""

        # Check if user's team is set as away team (should be home)
        if user_team_name.lower() == away_team_name.lower():
            raise ValidationError(
                {
                    "error": "Team assignment error",
                    "message": f"Your team '{user.team.name or user.team.id}' is set as the away team. You should be on the home team.",
                    "user_team": user.team.name or user.team.id,
                    "away_team": away_team_name,
                    "suggestion": "Swap home and away teams, or update your team selection in your profile.",
                }
            )

        # Check if user's team matches home team
        if user_team_name.lower() != home_team_name.lower():
            raise ValidationError(
                {
                    "error": "Team mismatch",
                    "message": f"Your team '{user.team.name or user.team.id}' does not match the home team '{home_team_name}'.",
                    "user_team": user.team.name or user.team.id,
                    "home_team": home_team_name,
                }
            )

    def _get_or_create_team(self, team_name, jersey_color, team_type="team"):
        """
        Get or create a team by name, validating jersey color.

        Args:
            team_name: Name of the team
            jersey_color: Jersey color to validate/set
            team_type: "home" or "away" for error messages

        Returns:
            Team instance

        Raises:
            ValidationError if jersey color doesn't match existing team
        """
        # Find existing team by name (case-insensitive)
        team_obj = Team.objects.filter(name__iexact=team_name).first()

        if team_obj:
            # Team exists - validate jersey color matches
            if team_obj.jersey_color and team_obj.jersey_color != jersey_color:
                raise ValidationError(
                    {
                        "error": "Jersey color mismatch",
                        "message": f"The {team_type} team '{team_name}' already exists with jersey color '{team_obj.jersey_color}', but you provided '{jersey_color}'.",
                        "team_name": team_name,
                        "team_type": team_type,
                        "existing_color": team_obj.jersey_color,
                        "provided_color": jersey_color,
                    }
                )
        else:
            # Create new team with UUID-based ID
            team_id = uuid.uuid4().hex[:10]
            while Team.objects.filter(id=team_id).exists():
                team_id = uuid.uuid4().hex[:10]

            team_obj = Team.objects.create(
                id=team_id,
                name=team_name,
                jersey_color=jersey_color,
            )

        return team_obj

    def create(self, validated_data):
        """
        Create TraceSession with all related objects (Teams, Game, GameUserRole).
        Handles video import/upload, duplicate checking, and TraceVision session creation.
        """
        # Extract validated data
        video_link = validated_data.get("video_link")
        video_file = validated_data.get("video_file")
        home_team_name = validated_data["home_team_name"]
        away_team_name = validated_data["away_team_name"]
        home_color = validated_data["home_team_jersey_color"]
        away_color = validated_data["away_team_jersey_color"]
        final_score_str = validated_data["final_score"]
        game_date = validated_data["game_date"]
        game_time = validated_data.get("game_time")
        start_time = validated_data.get("start_time")
        age_group = validated_data.get("age_group") or "SENIOR"
        pitch_length = validated_data.get("pitch_length")
        pitch_width = validated_data.get("pitch_width")
        match_start_time = validated_data.get("match_start_time")
        first_half_end_time = validated_data.get("first_half_end_time")
        second_half_start_time = validated_data.get("second_half_start_time")
        match_end_time = validated_data.get("match_end_time")
        basic_game_stats = validated_data.get("basic_game_stats")
        user = self.context["request"].user

        # STEP 1: Validate Excel data FIRST (before any DB operations or API calls)
        # This ensures we don't create teams, games, or TraceVision sessions if Excel is invalid
        language_metadata_content = {}
        if basic_game_stats:
            language_metadata_content = self._validate_and_extract_excel_teams(
                basic_game_stats, home_team_name, away_team_name
            )

        # Set pitch size (custom or default based on age group)
        if pitch_length and pitch_width:
            pitch_size = {"length": pitch_length, "width": pitch_width}
        else:
            pitch_size = TraceSession.DEFAULT_PITCH_SIZES.get(
                age_group, TraceSession.DEFAULT_PITCH_SIZES["SENIOR"]
            )

        # Parse the final score
        home_score, away_score = map(int, final_score_str.split("-"))

        # Validate user team assignment (for players only)
        self._validate_user_team_assignment(user, home_team_name, away_team_name)

        # Create or get teams
        home_team_obj = self._get_or_create_team(home_team_name, home_color, "home")
        away_team_obj = self._get_or_create_team(away_team_name, away_color, "away")

        # Set user's team if not set (for players only)
        if user.role != "Coach" and not user.team:
            user.team = home_team_obj
            user.save(update_fields=["team"])
            logger.info(
                f"Set home_team '{home_team_obj.name}' as team for user {user.phone_no}"
            )

        match_date = game_date
        duplicate_session = check_duplicate_game(
            home_team=home_team_obj, away_team=away_team_obj, match_date=match_date
        )

        if duplicate_session:
            existing_game = duplicate_session.game
            raise ValidationError(
                {
                    "error": "Game already exists",
                    "message": "A game with these teams and date already exists. You can link to the existing game.",
                    "existing_data": {
                        "session": {
                            "id": duplicate_session.id,
                            "session_id": duplicate_session.session_id,
                            "match_date": duplicate_session.match_date.isoformat(),
                            "home_team": (
                                duplicate_session.home_team.name
                                if duplicate_session.home_team
                                else None
                            ),
                            "away_team": (
                                duplicate_session.away_team.name
                                if duplicate_session.away_team
                                else None
                            ),
                            "status": duplicate_session.status,
                        },
                        "game": (
                            {
                                "id": existing_game.id if existing_game else None,
                                "type": existing_game.type if existing_game else None,
                                "name": existing_game.name if existing_game else None,
                                "date": (
                                    existing_game.date.isoformat()
                                    if existing_game and existing_game.date
                                    else None
                                ),
                            }
                            if existing_game
                            else None
                        ),
                    },
                }
            )

        # # Create TraceVision session
        customer_id = int(settings.TRACEVISION_CUSTOMER_ID)
        api_key = settings.TRACEVISION_API_KEY
        graphql_url = settings.TRACEVISION_GRAPHQL_URL

        session_payload = {
            "query": """
                mutation ($token: CustomerToken!, $sessionData: SessionCreateInput!) {
                    createSession(token: $token, sessionData: $sessionData) {
                        session { session_id }
                        success
                        error
                    }
                }
            """,
            "variables": {
                "token": {"customer_id": customer_id, "token": api_key},
                "sessionData": {
                    "type": "soccer_game",
                    "game_info": {
                        "home_team": {
                            "name": home_team_name,
                            "score": home_score,
                            "color": home_color,
                        },
                        "away_team": {
                            "name": away_team_name,
                            "score": away_score,
                            "color": away_color,
                        },
                    },
                    "capabilities": ["tracking", "highlights"],
                },
            },
        }

        session_response = requests.post(
            graphql_url,
            headers={"Content-Type": "application/json"},
            json=session_payload,
        )
        session_json = session_response.json()

        if session_response.status_code != 200 or not session_json.get("data", {}).get(
            "createSession", {}
        ).get("success"):
            raise ValidationError(
                {
                    "error": "TraceVision session creation failed",
                    "details": session_json,
                }
            )

        session_id = session_json["data"]["createSession"]["session"]["session_id"]
        # session_id = "1234567890"

        # Check for duplicate by video_url BEFORE processing video
        video_url_for_db = "http://sfsfsfsf/sfs"
        if video_link:
            video_url_for_db = video_link
            duplicate_session = check_duplicate_game(video_url=video_url_for_db)
            if duplicate_session:
                existing_game = duplicate_session.game
                raise ValidationError(
                    {
                        "error": "Video already processed",
                        "message": "This video has already been uploaded and processed.",
                        "existing_data": {
                            "session": {
                                "id": duplicate_session.id,
                                "session_id": duplicate_session.session_id,
                                "match_date": duplicate_session.match_date.isoformat(),
                                "home_team": (
                                    duplicate_session.home_team.name
                                    if duplicate_session.home_team
                                    else None
                                ),
                                "away_team": (
                                    duplicate_session.away_team.name
                                    if duplicate_session.away_team
                                    else None
                                ),
                                "status": duplicate_session.status,
                            },
                            "game": (
                                {
                                    "id": existing_game.id if existing_game else None,
                                    "type": (
                                        existing_game.type if existing_game else None
                                    ),
                                    "name": (
                                        existing_game.name if existing_game else None
                                    ),
                                    "date": (
                                        existing_game.date.isoformat()
                                        if existing_game and existing_game.date
                                        else None
                                    ),
                                }
                                if existing_game
                                else None
                            ),
                        },
                    }
                )

        # Handle video processing
        if video_link:
            video_url_for_db = TraceVisionService.import_game_video(
                session_id=session_id, video_link=video_link, start_time=start_time
            )
        else:
            # Video file upload is not supported - this should be caught by validation
            # but adding safety check here as well
            raise ValidationError(
                {
                    "error": "Video file upload not supported",
                    "message": "Video file upload is currently not supported. Please use video_link instead to provide a URL to your video.",
                }
            )
        # TODO: Implement video upload functionality later

        # Get or create canonical game
        canonical_game = get_or_create_canonical_game(
            home_team=home_team_obj,
            away_team=away_team_obj,
            match_date=match_date,
            game_type="match",
        )

        # Check if game already has a TraceSession (OneToOne constraint)
        if hasattr(canonical_game, "trace_session") and canonical_game.trace_session:
            existing_session = canonical_game.trace_session
            raise ValidationError(
                {
                    "error": "Game already has a session",
                    "message": "A TraceSession already exists for this game. You can link to the existing game.",
                    "existing_data": {
                        "session": {
                            "id": existing_session.id,
                            "session_id": existing_session.session_id,
                            "match_date": existing_session.match_date.isoformat(),
                            "home_team": (
                                existing_session.home_team.name
                                if existing_session.home_team
                                else None
                            ),
                            "away_team": (
                                existing_session.away_team.name
                                if existing_session.away_team
                                else None
                            ),
                            "status": existing_session.status,
                        },
                        "game": {
                            "id": canonical_game.id,
                            "type": canonical_game.type,
                            "name": canonical_game.name,
                            "date": (
                                canonical_game.date.isoformat()
                                if canonical_game.date
                                else None
                            ),
                        },
                    },
                }
            )

        # Create TraceSession (single creation point)
        session = TraceSession.objects.create(
            user=user,
            session_id=session_id,
            match_date=match_date,
            home_team=home_team_obj,
            away_team=away_team_obj,
            home_score=home_score,
            away_score=away_score,
            age_group=age_group,
            pitch_size=pitch_size,
            final_score=final_score_str,
            start_time=start_time,
            video_url=video_url_for_db,
            status="waiting_for_data",
            match_start_time=match_start_time,
            first_half_end_time=first_half_end_time,
            second_half_start_time=second_half_start_time,
            match_end_time=match_end_time,
            basic_game_stats=basic_game_stats,
            game=canonical_game,
            language_metadata=language_metadata_content,
        )

        # Create GameUserRole linking uploader to game
        GameUserRole.objects.get_or_create(game=canonical_game, user=user)

        # Trigger Excel processing task if Excel file is provided (runs before video download)
        # Check session.basic_game_stats after creation to ensure file was saved
        if session.basic_game_stats and process_excel_and_create_players_task:
            try:
                process_excel_and_create_players_task.delay(session.id)
                logger.info(f"Queued Excel processing task for session {session.id}")
            except Exception as e:
                logger.error(
                    f"Failed to queue Excel processing task for session {session.id}: {e}",
                    exc_info=True
                )

        # Trigger video download task
        from tracevision.tasks import download_video_and_save_to_azure_blob
        download_video_and_save_to_azure_blob.delay(session.id)


        return session


class CoachViewSpecificTeamPlayersSerializer(serializers.ModelSerializer):
    class Meta:
        model = TracePlayer
        fields = "__all__"


class HighlightDatePlayerSerializer(serializers.ModelSerializer):
    """Serializer for player info in highlight dates response"""

    player_id = serializers.IntegerField(source="id", read_only=True)
    player_name = serializers.SerializerMethodField()
    player_jersey_number = serializers.IntegerField(
        source="jersey_number", read_only=True
    )
    player_logo = serializers.SerializerMethodField()

    def get_player_name(self, obj):
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return get_localized_player_name(obj, user_language)

    def get_player_logo(self, obj):
        """Get player logo from user profile picture"""
        if obj.user and obj.user.picture:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.user.picture.url)
            return obj.user.picture.url
        return None

    player_position = serializers.CharField(source="position", read_only=True)
    side = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()

    class Meta:
        model = TracePlayer
        fields = [
            "player_id",
            "player_name",
            "player_jersey_number",
            "player_position",
            "player_logo",
            "side",
            "team",
        ]

    def get_side(self, obj):
        """Determine if player is on home or away team, transformed by viewer perspective"""
        from tracevision.utils import get_viewer_team, determine_viewer_perspective, transform_side_by_perspective
        
        # Get session from context (passed from view)
        session = self.context.get("session")
        if not session:
            # Fallback: get first session if available
            if obj.sessions.exists():
                session = obj.sessions.first()
            else:
                return None

        # Determine side based on team match
        side = None
        if session.home_team and obj.team and session.home_team.id == obj.team.id:
            side = "home"
        elif session.away_team and obj.team and session.away_team.id == obj.team.id:
            side = "away"
        
        if not side:
            return None

        # Transform side based on viewer perspective (so players see their team correctly)
        request = self.context.get("request")
        if request and request.user:
            viewer_team = get_viewer_team(request.user)
            if viewer_team:
                viewer_perspective = determine_viewer_perspective(viewer_team, session)
                if viewer_perspective:
                    side = transform_side_by_perspective(side, viewer_perspective)

        return side

    def get_team(self, obj):
        """Get team information for the player"""
        if not obj.team:
            return {"team_id": None, "team_name": None, "side": self.get_side(obj)}

        # Get user language preference
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )

        return {
            "team_id": obj.team.id,
            "team_name": get_localized_team_name(obj.team, user_language),
            "side": self.get_side(obj),
        }


class HighlightDateSessionSerializer(serializers.ModelSerializer):
    """Serializer for session info in highlight dates response"""

    id = serializers.IntegerField(read_only=True)
    session_id = serializers.CharField(read_only=True)
    match_date = serializers.DateField(format="%Y-%m-%d", read_only=True)
    home_team = serializers.SerializerMethodField()
    away_team = serializers.SerializerMethodField()
    match_logo = serializers.SerializerMethodField()
    match_status = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    stadium = serializers.SerializerMethodField()
    referees = serializers.SerializerMethodField()
    timeline = serializers.SerializerMethodField()

    class Meta:
        model = TraceSession
        fields = [
            "id",
            "session_id",
            "match_date",
            "final_score",
            "home_score",
            "away_score",
            "home_team",
            "away_team",
            "age_group",
            "match_start_time",
            "first_half_end_time",
            "second_half_start_time",
            "match_end_time",
            "video_url",
            "match_logo",
            "match_status",
            "score",
            "stadium",
            "referees",
            "timeline",
        ]

    def get_match_logo(self, obj):
        """Get match logo from home team (preferred) or away team"""
        # Prefer home team logo
        if obj.home_team and obj.home_team.logo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.home_team.logo.url)
            return obj.home_team.logo.url
        # Fallback to away team logo
        elif obj.away_team and obj.away_team.logo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.away_team.logo.url)
            return obj.away_team.logo.url
        return None

    def get_match_status(self, obj):
        """Determine match status: Scheduled, Live, or Ended with localized value"""
        from django.utils import timezone
        from datetime import datetime, date, time as dt_time
        
        # Get user language preference
        user_language = "en"
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        # Status translations
        status_translations = {
            "Scheduled": {
                "en": "Scheduled",
                "ar": "مجدول",
                "he": "מתוכנן",
                "es": "Programado",
                "fr": "Programmé",
                "de": "Geplant",
                "it": "Programmato",
                "pt": "Agendado",
            },
            "Live": {
                "en": "Live",
                "ar": "مباشر",
                "he": "חי",
                "es": "En vivo",
                "fr": "En direct",
                "de": "Live",
                "it": "In diretta",
                "pt": "Ao vivo",
            },
            "Ended": {
                "en": "Ended",
                "ar": "انتهى",
                "he": "הסתיים",
                "es": "Finalizado",
                "fr": "Terminé",
                "de": "Beendet",
                "it": "Terminato",
                "pt": "Finalizado",
            }
        }
        
        # Determine status
        status_key = "Scheduled"
        status_code = 1
        
        if not obj.match_date:
            status_key = "Scheduled"
            status_code = 1
        else:
            today = timezone.now().date()
            match_date = obj.match_date
            
            # If match date is in the future, it's Scheduled
            if match_date > today:
                status_key = "Scheduled"
                status_code = 1
            
            # If match date is today, check if it's live based on match_start_time and match_end_time
            elif match_date == today:
                if obj.match_start_time and obj.match_end_time:
                    try:
                        # Parse match times
                        start_time = datetime.strptime(obj.match_start_time, "%H:%M:%S").time()
                        end_time = datetime.strptime(obj.match_end_time, "%H:%M:%S").time()
                        current_time = timezone.now().time()
                        
                        # Check if current time is between start and end
                        if start_time <= current_time <= end_time:
                            status_key = "Live"
                            status_code = 2
                        else:
                            status_key = "Ended"
                            status_code = 3
                    except (ValueError, AttributeError):
                        # If status is processed, it's likely ended
                        if obj.status == "processed":
                            status_key = "Ended"
                            status_code = 3
                        else:
                            # Default to Live if today and no clear end time
                            status_key = "Live"
                            status_code = 2
                else:
                    # If status is processed, it's likely ended
                    if obj.status == "processed":
                        status_key = "Ended"
                        status_code = 3
                    else:
                        # Default to Live if today and no clear end time
                        status_key = "Live"
                        status_code = 2
            
            # If match date is in the past, it's Ended
            elif match_date < today:
                status_key = "Ended"
                status_code = 3
        
        # Get localized value, fallback to English if language not supported
        localized_value = status_translations[status_key].get(
            user_language, 
            status_translations[status_key]["en"]
        )
        
        return {
            "status": status_code,
            "value": localized_value
        }

    def get_score(self, obj):
        """Get match score when match is Ended"""
        match_status = self.get_match_status(obj)
        # Check if status is 3 (Ended)
        if match_status.get("status") == 3:
            return {
                "home": obj.home_score if obj.home_score is not None else 0,
                "away": obj.away_score if obj.away_score is not None else 0,
            }
        return None


    def get_stadium(self, obj):
        """Get stadium/venue from language_metadata"""
        user_language = "en"
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        if obj.language_metadata:
            match_summary = obj.language_metadata.get(user_language, {}).get("Match_summary", {})
            if match_summary:
                # Try match_location first, then match_venue
                stadium = match_summary.get("match_location") or match_summary.get("match_venue") or match_summary.get("Stadium") or match_summary.get("Venue")
                if stadium:
                    return stadium
        
        return None

    def _transform_lineups_to_list(self, lineups_dict, team_side, obj, team, players_lookup=None):
        """Transform starting_lineups from dict (keyed by jersey) to list format with player+jersey_number and profile info"""
        from tracevision.models import TracePlayer
        from django.core.exceptions import ObjectDoesNotExist
        
        if not lineups_dict or not isinstance(lineups_dict, dict):
            return []
        
        lineup_list = []
        request = self.context.get("request")
        
        # Optimize: Use provided players_lookup or fetch if not provided
        if players_lookup is None:
            players_lookup = {}
            if team:
                try:
                    # Get all players for this team with their users prefetched
                    team_players = TracePlayer.objects.filter(
                        team=team
                    ).select_related("user").only(
                        "id", "jersey_number", "user__picture"
                    )
                    
                    # Create lookup dictionary: jersey_number -> player
                    for player in team_players:
                        players_lookup[player.jersey_number] = player
                except Exception as e:
                    logger.warning(f"Error fetching players for team {team.id if team else 'None'}: {e}")
        
        for jersey_number, player_data in lineups_dict.items():
            if not isinstance(player_data, dict):
                continue
            
            # Ensure goals and video_goal are lists
            goals = player_data.get("goals", [])
            if not isinstance(goals, list):
                goals = [goals] if goals else []
            
            video_goal = player_data.get("video_goal", [])
            if not isinstance(video_goal, list):
                video_goal = [video_goal] if video_goal else []
            
            player_name = player_data.get("name", "")
            try:
                jersey_num = int(jersey_number) if str(jersey_number).isdigit() else jersey_number
            except (ValueError, TypeError):
                jersey_num = jersey_number
            
            # Look up player from prefetched data
            player_id = None
            player_logo = None
            
            if jersey_num in players_lookup:
                trace_player = players_lookup[jersey_num]
                player_id = trace_player.id
                
                # Get profile picture from user
                if trace_player.user and trace_player.user.picture:
                    try:
                        picture_url = trace_player.user.picture.url
                        if picture_url and not str(picture_url).endswith("null"):
                            if request:
                                player_logo = request.build_absolute_uri(picture_url)
                            else:
                                player_logo = picture_url
                    except (ValueError, AttributeError, ObjectDoesNotExist) as e:
                        logger.debug(f"Error getting picture URL for player {player_id}: {e}")
                        player_logo = None
            
            lineup_item = {
                "player": player_name,
                "player_id": player_id,
                "jersey_number": jersey_num,
                "role": player_data.get("role", ""),
                "cards": player_data.get("cards", 0),
                "goals": goals,
                "video_goal": video_goal,
                "sub_off_minute": player_data.get("sub_off_minute", 0),
                "logo": player_logo,
            }
            lineup_list.append(lineup_item)
        
        return lineup_list
    
    def _transform_replacements_to_list(self, replacements_dict, team_side, obj, team, players_lookup=None):
        """Transform replacements from dict (keyed by jersey) to list format with player+jersey_number and profile info"""
        from tracevision.models import TracePlayer
        from django.core.exceptions import ObjectDoesNotExist
        
        if not replacements_dict or not isinstance(replacements_dict, dict):
            return []
        
        replacement_list = []
        request = self.context.get("request")
        
        # Optimize: Use provided players_lookup or fetch if not provided
        if players_lookup is None:
            players_lookup = {}
            if team:
                try:
                    # Get all players for this team with their users prefetched
                    team_players = TracePlayer.objects.filter(
                        team=team
                    ).select_related("user").only(
                        "id", "jersey_number", "user__picture"
                    )
                    
                    # Create lookup dictionary: jersey_number -> player
                    for player in team_players:
                        players_lookup[player.jersey_number] = player
                except Exception as e:
                    logger.warning(f"Error fetching players for team {team.id if team else 'None'}: {e}")
        
        for jersey_number, player_data in replacements_dict.items():
            if not isinstance(player_data, dict):
                continue
            
            # Ensure goals and video_goal are lists
            goals = player_data.get("goals", [])
            if not isinstance(goals, list):
                goals = [goals] if goals else []
            
            video_goal = player_data.get("video_goal", [])
            if not isinstance(video_goal, list):
                video_goal = [video_goal] if video_goal else []
            
            player_name = player_data.get("name", "")
            try:
                jersey_num = int(jersey_number) if str(jersey_number).isdigit() else jersey_number
            except (ValueError, TypeError):
                jersey_num = jersey_number
            
            # Look up player from prefetched data
            player_id = None
            player_logo = None
            
            if jersey_num in players_lookup:
                trace_player = players_lookup[jersey_num]
                player_id = trace_player.id
                
                # Get profile picture from user
                if trace_player.user and trace_player.user.picture:
                    try:
                        picture_url = trace_player.user.picture.url
                        if picture_url and not str(picture_url).endswith("null"):
                            if request:
                                player_logo = request.build_absolute_uri(picture_url)
                            else:
                                player_logo = picture_url
                    except (ValueError, AttributeError, ObjectDoesNotExist) as e:
                        logger.debug(f"Error getting picture URL for player {player_id}: {e}")
                        player_logo = None
            
            replacement_item = {
                "player": player_name,
                "player_id": player_id,
                "jersey_number": jersey_num,
                "role": player_data.get("role", ""),
                "goals": goals,
                "video_goal": video_goal,
                "replacer_minute": player_data.get("replacer_minute", 0),
                "logo": player_logo,
            }
            replacement_list.append(replacement_item)
        
        return replacement_list
    
    def _get_team_goals_data(self, obj, team_side):
        """Get goal data for a specific team side (home or away)"""
        from tracevision.models import TraceVisionSessionStats, TraceHighlight
        
        # Get user language preference
        user_language = "en"
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        # Get goal highlights
        if hasattr(obj, "_prefetched_goal_highlights"):
            goal_highlights = obj._prefetched_goal_highlights
        else:
            goal_highlights = TraceHighlight.objects.filter(
                session=obj,
                event_type="goal"
            ).select_related("player", "player__team").order_by("half", "match_time")
        
        team_goals = []
        for highlight in goal_highlights:
            if not highlight.player:
                continue
            
            # Determine if this goal belongs to the requested team
            is_home_goal = highlight.player.team == obj.home_team
            is_away_goal = highlight.player.team == obj.away_team
            
            if team_side == "home" and not is_home_goal:
                continue
            if team_side == "away" and not is_away_goal:
                continue
            
            # Get player name in user's language
            player_name = get_localized_name(highlight.player, user_language, "name")
            if not player_name:
                player_name = highlight.player.name or f"Player {highlight.player.jersey_number}"
            
            # Get goal minute
            goal_minute = highlight.match_time or highlight.event_metadata.get("minute", "")
            
            # Determine half
            half = highlight.half or 1
            if highlight.match_time:
                try:
                    minute_str = highlight.match_time.split(":")[0] if ":" in highlight.match_time else highlight.match_time
                    minute = int(minute_str.replace("'", "").replace("min", "").strip())
                    half = 1 if minute <= 45 else 2
                except (ValueError, AttributeError):
                    pass
            
            goal_data = {
                "player_name": player_name,
                "jersey_number": highlight.player.jersey_number,
                "minute": goal_minute,
                "half": half,
            }
            team_goals.append(goal_data)
        
        # Get goal counts from session_stats
        first_half_count = 0
        second_half_count = 0
        total_count = len(team_goals)
        
        try:
            if hasattr(obj, "session_stats") and obj.session_stats.exists():
                session_stats = obj.session_stats.first()
            else:
                session_stats = TraceVisionSessionStats.objects.filter(session=obj).first()
            
            if session_stats:
                if team_side == "home":
                    home_stats = session_stats.home_team_stats or {}
                    if home_stats.get("first_half_goals") is not None:
                        first_half_count = home_stats.get("first_half_goals", 0)
                        second_half_count = home_stats.get("second_half_goals", 0)
                        total_count = first_half_count + second_half_count
                else:
                    away_stats = session_stats.away_team_stats or {}
                    if away_stats.get("first_half_goals") is not None:
                        first_half_count = away_stats.get("first_half_goals", 0)
                        second_half_count = away_stats.get("second_half_goals", 0)
                        total_count = first_half_count + second_half_count
        except Exception:
            pass
        
        return {
            "goals": team_goals,
            "goal_counts": {
                "first_half": first_half_count,
                "second_half": second_half_count,
                "total": total_count,
            }
        }
    
    def _get_team_coaches(self, obj, team, team_side, user_language):
        """Get coaches for a team from multiple sources with user_id and profile picture"""
        from accounts.models import WajoUser
        
        coaches_list = []
        request = self.context.get("request")
        
        # First, try to get from team.coach ManyToManyField (has user objects)
        if team and hasattr(team, "coach"):
            for coach_user in team.coach.all():
                # Get profile picture URL
                coach_logo = None
                if coach_user.picture:
                    try:
                        picture_url = coach_user.picture.url
                        if picture_url and not str(picture_url).endswith("null"):
                            if request:
                                coach_logo = request.build_absolute_uri(picture_url)
                            else:
                                coach_logo = picture_url
                        else:
                            coach_logo = None
                    except (ValueError, AttributeError):
                        coach_logo = None
                else:
                    # No profile picture
                    coach_logo = None
                
                coaches_list.append({
                    "user_id": str(coach_user.id),
                    "name": coach_user.name or "",
                    "role": coach_user.role or "Coach",
                    "logo": coach_logo,
                })
        
        # If no coaches from team relationship, try game_info and language_metadata
        # Try to match with user objects by name
        if not coaches_list:
            coaches_from_data = []
            
            # Try game_info first
            try:
                if obj.game and obj.game.game_info:
                    game_info = obj.game.game_info
                    if user_language in game_info:
                        lang_info = game_info[user_language]
                        team_info = lang_info.get(team_side, {})
                        coaches_from_info = team_info.get("coaches", [])
                        if isinstance(coaches_from_info, list):
                            coaches_from_data = coaches_from_info
            except Exception as e:
                logger.warning(f"Error getting coaches from game_info: {e}")
            
            # Fallback: try language_metadata
            if not coaches_from_data:
                try:
                    if obj.language_metadata:
                        lang_data = obj.language_metadata.get(user_language, {})
                        coaches_dict = lang_data.get("coaches", {})
                        if isinstance(coaches_dict, dict):
                            # Coaches are keyed by team name
                            team_name = get_localized_team_name(team, user_language) if team else None
                            if team_name and team_name in coaches_dict:
                                coaches_from_data = coaches_dict[team_name]
                            # Also try with English name as fallback
                            elif team:
                                team_name_en = get_localized_team_name(team, "en")
                                if team_name_en and team_name_en in coaches_dict:
                                    coaches_from_data = coaches_dict[team_name_en]
                except Exception as e:
                    logger.warning(f"Error getting coaches from language_metadata: {e}")
            
            # Optimize: Batch lookup coaches by name to avoid N+1 queries
            coach_names = []
            for coach_data in coaches_from_data:
                coach_name = coach_data.get("name", "") if isinstance(coach_data, dict) else str(coach_data)
                if coach_name:
                    coach_names.append(coach_name)
            
            # Fetch all matching coaches in a single query
            coaches_lookup = {}
            if coach_names:
                try:
                    matching_coaches = WajoUser.objects.filter(
                        name__in=coach_names,
                        role="Coach"
                    ).only("id", "name", "picture")
                    
                    for coach_user in matching_coaches:
                        coaches_lookup[coach_user.name] = coach_user
                except Exception as e:
                    logger.warning(f"Error batch fetching coaches: {e}")
            
            # Process coaches from data
            for coach_data in coaches_from_data:
                coach_name = coach_data.get("name", "") if isinstance(coach_data, dict) else str(coach_data)
                coach_role = coach_data.get("role", "Coach") if isinstance(coach_data, dict) else "Coach"
                
                # Look up coach from prefetched data
                coach_user = coaches_lookup.get(coach_name) if coach_name else None
                
                # Get profile picture
                coach_logo = None
                if coach_user and coach_user.picture:
                    try:
                        picture_url = coach_user.picture.url
                        if picture_url and not str(picture_url).endswith("null"):
                            if request:
                                coach_logo = request.build_absolute_uri(picture_url)
                            else:
                                coach_logo = picture_url
                    except (ValueError, AttributeError) as e:
                        logger.debug(f"Error getting picture URL for coach {coach_user.id}: {e}")
                        coach_logo = None
                
                coaches_list.append({
                    "user_id": str(coach_user.id) if coach_user else None,
                    "name": coach_name,
                    "role": coach_role,
                    "logo": coach_logo,
                })
        
        return coaches_list if coaches_list else []
    
    def _get_game_referees(self, obj, user_language):
        """Get referees for a game from multiple sources with user_id and profile picture"""
        from accounts.models import WajoUser
        
        referees_list = []
        request = self.context.get("request")
        
        # First, try to get from game.referees ManyToManyField (has user objects)
        if obj.game and hasattr(obj.game, "referees"):
            for referee_user in obj.game.referees.all():
                # Get profile picture URL
                referee_logo = None
                if referee_user.picture:
                    try:
                        picture_url = referee_user.picture.url
                        if picture_url and not str(picture_url).endswith("null"):
                            if request:
                                referee_logo = request.build_absolute_uri(picture_url)
                            else:
                                referee_logo = picture_url
                        else:
                            referee_logo = None
                    except (ValueError, AttributeError):
                        referee_logo = None
                else:
                    # No profile picture
                    referee_logo = None
                
                referees_list.append({
                    "user_id": str(referee_user.id),
                    "name": referee_user.name or "",
                    "position": referee_user.role or "Referee",
                    "logo": referee_logo,
                })
        
        # If no referees from game relationship, try game_info and language_metadata
        # Try to match with user objects by name
        if not referees_list:
            referees_from_data = []
            
            # Try game_info first
            try:
                if obj.game and obj.game.game_info:
                    game_info = obj.game.game_info
                    if user_language in game_info:
                        lang_info = game_info[user_language]
                        # Referees are shared, so get from either home or away
                        team_info = lang_info.get("home", {}) or lang_info.get("away", {})
                        referees_from_info = team_info.get("referees", [])
                        if isinstance(referees_from_info, list):
                            referees_from_data = referees_from_info
            except Exception as e:
                logger.warning(f"Error getting referees from game_info: {e}")
            
            # Fallback: try language_metadata
            if not referees_from_data:
                try:
                    if obj.language_metadata:
                        lang_data = obj.language_metadata.get(user_language, {})
                        referees_from_metadata = lang_data.get("referees", [])
                        if isinstance(referees_from_metadata, list):
                            referees_from_data = referees_from_metadata
                except Exception as e:
                    logger.warning(f"Error getting referees from language_metadata: {e}")
            
            # Optimize: Batch lookup referees by name to avoid N+1 queries
            referee_names = []
            for referee_data in referees_from_data:
                referee_name = referee_data.get("name", "") if isinstance(referee_data, dict) else str(referee_data)
                if referee_name:
                    referee_names.append(referee_name)
            
            # Fetch all matching referees in a single query
            referees_lookup = {}
            if referee_names:
                try:
                    matching_referees = WajoUser.objects.filter(
                        name__in=referee_names,
                        role="Referee"
                    ).only("id", "name", "picture")
                    
                    for referee_user in matching_referees:
                        referees_lookup[referee_user.name] = referee_user
                except Exception as e:
                    logger.warning(f"Error batch fetching referees: {e}")
            
            # Process referees from data
            for referee_data in referees_from_data:
                referee_name = referee_data.get("name", "") if isinstance(referee_data, dict) else str(referee_data)
                referee_position = referee_data.get("position", "Referee") if isinstance(referee_data, dict) else "Referee"
                
                # Look up referee from prefetched data
                referee_user = referees_lookup.get(referee_name) if referee_name else None
                
                # Get profile picture
                referee_logo = None
                if referee_user and referee_user.picture:
                    try:
                        picture_url = referee_user.picture.url
                        if picture_url and not str(picture_url).endswith("null"):
                            if request:
                                referee_logo = request.build_absolute_uri(picture_url)
                            else:
                                referee_logo = picture_url
                    except (ValueError, AttributeError) as e:
                        logger.debug(f"Error getting picture URL for referee {referee_user.id}: {e}")
                        referee_logo = None
                
                referees_list.append({
                    "user_id": str(referee_user.id) if referee_user else None,
                    "name": referee_name,
                    "position": referee_position,
                    "logo": referee_logo,
                })
        
        return referees_list if referees_list else []
    
    def _get_team_data(self, obj, team_side):
        """Get complete team data including goals, starting_lineups, replacements, coaches, and referees"""
        from tracevision.models import TraceVisionSessionStats
        
        # Get user language preference
        user_language = "en"
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        # Get team instance
        team = obj.home_team if team_side == "home" else obj.away_team
        if not team:
            return {
                "id": None,
                "name": None,
                "logo": None,
                "total_goals": 0,
                "first_half_goals": 0,
                "second_half_goals": 0,
                "goals": [],
                "goal_counts": {"first_half": 0, "second_half": 0, "total": 0},
                "starting_lineups": [],
                "replacements": [],
                "coaches": [],
            }
        
        # Get team basic info
        team_logo = None
        if team.logo:
            if request:
                team_logo = request.build_absolute_uri(team.logo.url)
            else:
                team_logo = team.logo.url
        
        # Get goals data
        goals_data = self._get_team_goals_data(obj, team_side)
        
        # Get starting_lineups and replacements from session_stats
        starting_lineups_dict = {}
        replacements_dict = {}
        total_goals = 0
        first_half_goals = 0
        second_half_goals = 0
        
        try:
            if hasattr(obj, "session_stats") and obj.session_stats.exists():
                session_stats = obj.session_stats.first()
            else:
                session_stats = TraceVisionSessionStats.objects.filter(session=obj).first()
            
            if session_stats:
                if team_side == "home":
                    team_stats = session_stats.home_team_stats or {}
                else:
                    team_stats = session_stats.away_team_stats or {}
                
                total_goals = team_stats.get("total_goals", 0)
                first_half_goals = team_stats.get("first_half_goals", 0)
                second_half_goals = team_stats.get("second_half_goals", 0)
                
                # Get starting_lineups and replacements
                starting_lineups_all = team_stats.get("starting_lineups", {})
                replacements_all = team_stats.get("replacements", {})
                
                starting_lineups_dict = starting_lineups_all.get(user_language, starting_lineups_all.get("en", {}))
                replacements_dict = replacements_all.get(user_language, replacements_all.get("en", {}))
        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"Error getting team data from session_stats: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error getting team data from session_stats: {e}", exc_info=True)
        
        # Fallback: try to get from game.game_info
        if not starting_lineups_dict and not replacements_dict:
            try:
                if obj.game and obj.game.game_info:
                    game_info = obj.game.game_info
                    if user_language in game_info:
                        lang_info = game_info[user_language]
                        team_info = lang_info.get(team_side, {})
                        starting_lineups_dict = team_info.get("starting_lineups", {})
                        replacements_dict = team_info.get("replacements", {})
                        total_goals = team_info.get("total_score", 0)
                        first_half_goals = team_info.get("first_half_score", 0)
                        second_half_goals = team_info.get("second_half_score", 0)
            except (AttributeError, KeyError, TypeError, ValueError) as e:
                logger.warning(f"Error getting team data from game_info: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error getting team data from game_info: {e}", exc_info=True)
        
        # Use goal counts from stats if available (more accurate), otherwise use counts from goals_data
        if total_goals == 0 and first_half_goals == 0 and second_half_goals == 0:
            # Stats don't have goal counts, use counts from goals_data
            first_half_goals = goals_data["goal_counts"]["first_half"]
            second_half_goals = goals_data["goal_counts"]["second_half"]
            total_goals = goals_data["goal_counts"]["total"]
        
        # Optimize: Prefetch all players for the team once to share between lineups and replacements
        from tracevision.models import TracePlayer
        players_lookup = {}
        if team:
            try:
                team_players = TracePlayer.objects.filter(
                    team=team
                ).select_related("user").only(
                    "id", "jersey_number", "user__picture"
                )
                for player in team_players:
                    players_lookup[player.jersey_number] = player
            except (AttributeError, ValueError, TypeError) as e:
                logger.warning(f"Error prefetching players for team {team.id if team else 'None'}: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error prefetching players for team {team.id if team else 'None'}: {e}", exc_info=True)
        
        # Transform lineups and replacements to list format with player profile info
        # Pass players_lookup to avoid duplicate queries
        starting_lineups_list = self._transform_lineups_to_list(
            starting_lineups_dict, team_side, obj, team, players_lookup
        )
        replacements_list = self._transform_replacements_to_list(
            replacements_dict, team_side, obj, team, players_lookup
        )
        
        # Get coaches (referees are at game level, not team level)
        coaches_list = self._get_team_coaches(obj, team, team_side, user_language)
        
        return {
            "id": team.id,
            "name": get_localized_team_name(team, user_language),
            "logo": team_logo,
            "total_goals": total_goals,
            "first_half_goals": first_half_goals,
            "second_half_goals": second_half_goals,
            "goals": goals_data["goals"],
            "goal_counts": {
                "first_half": first_half_goals,
                "second_half": second_half_goals,
                "total": total_goals,
            },
            "starting_lineups": starting_lineups_list,
            "replacements": replacements_list,
            "coaches": coaches_list,
        }
    
    def get_home_team(self, obj):
        """Get home team data with goals, starting_lineups, and replacements"""
        return self._get_team_data(obj, "home")
    
    def get_away_team(self, obj):
        """Get away team data with goals, starting_lineups, and replacements"""
        return self._get_team_data(obj, "away")
    
    def get_referees(self, obj):
        """Get referees for the game (at game level, not team level)"""
        # Get user language preference
        user_language = "en"
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        return self._get_game_referees(obj, user_language)
    
    def get_timeline(self, obj):
        """
        Get game timeline grouped by minute with separate home/away events.
        Returns timeline in format:
        [
            {
                "minute": 24,
                "home": [event1, event2],
                "away": [event3, event4]
            }
        ]
        """
        from tracevision.models import TracePlayer, TraceVisionSessionStats
        
        # Get user language preference
        user_language = "en"
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        timeline_events = []
        
        # First, try to get timeline from game_info
        try:
            if obj.game and obj.game.game_info:
                game_info = obj.game.game_info
                timeline_data = game_info.get("timeline", [])
                if timeline_data:
                    timeline_events = timeline_data
        except (AttributeError, KeyError, TypeError) as e:
            logger.warning(f"Error getting timeline from game_info: {e}")
        
        # Fallback: try to get from session_stats
        if not timeline_events:
            try:
                if hasattr(obj, "session_stats") and obj.session_stats.exists():
                    session_stats = obj.session_stats.first()
                else:
                    session_stats = TraceVisionSessionStats.objects.filter(session=obj).first()
                
                if session_stats and session_stats.tactical_analysis:
                    timeline_data = session_stats.tactical_analysis.get("game_timeline", [])
                    if timeline_data:
                        timeline_events = timeline_data
            except (AttributeError, KeyError, TypeError) as e:
                logger.warning(f"Error getting timeline from session_stats: {e}")
        
        if not timeline_events:
            return []
        
        # Prefetch all goal highlights for this session with clip reels
        from tracevision.models import TraceHighlight, TraceClipReel
        from django.db.models import Prefetch
        
        goal_highlights = {}
        try:
            highlights_queryset = (
                TraceHighlight.objects.filter(
                    session=obj,
                    event_type="goal"
                )
                .select_related("player__team", "session__home_team", "session__away_team")
                .prefetch_related(
                    Prefetch(
                        "clip_reels",
                        queryset=TraceClipReel.objects.select_related(
                            "primary_player", "primary_player__team"
                        ).order_by("-is_default", "ratio", "id"),
                    )
                )
            )
            
            # Build lookup: {(player_id, minute): highlight}
            for highlight in highlights_queryset:
                if highlight.player and highlight.match_time:
                    # Extract minute from match_time (format: "MM:00" or "MM:SS")
                    try:
                        minute_str = highlight.match_time.split(":")[0] if ":" in highlight.match_time else str(highlight.match_time)
                        minute = int(minute_str.replace("'", "").replace("min", "").strip())
                        key = (highlight.player.id, minute)
                        goal_highlights[key] = highlight
                    except (ValueError, AttributeError):
                        # If we can't parse minute, try to match by player only
                        key = (highlight.player.id, None)
                        if key not in goal_highlights:
                            goal_highlights[key] = highlight
        except Exception as e:
            logger.warning(f"Error prefetching goal highlights for timeline: {e}")
        
        # Build player lookup for both teams to enrich timeline with player IDs
        players_lookup = {}  # {(team_side, jersey_number): player_id}
        
        try:
            # Fetch all players for both teams
            for team_side, team in [("home", obj.home_team), ("away", obj.away_team)]:
                if team:
                    team_players = TracePlayer.objects.filter(
                        team=team
                    ).select_related("user").only("id", "jersey_number", "user__picture")
                    
                    for player in team_players:
                        players_lookup[(team_side, player.jersey_number)] = {
                            "player_id": player.id,
                            "player": player,
                        }
        except Exception as e:
            logger.warning(f"Error building player lookup for timeline: {e}")
        
        # Enrich timeline events with player IDs and profile pictures
        enriched_timeline = []
        for event in timeline_events:
            try:
                # Create a copy of the event to avoid modifying original
                enriched_event = event.copy()
                
                team_side = event.get("team_side", "home")
                jersey_number = event.get("player_jersey_number")
                
                # Helper function to get player logo
                def get_player_logo(player_info):
                    if not player_info:
                        return None
                    trace_player = player_info["player"]
                    if trace_player.user and trace_player.user.picture:
                        try:
                            picture_url = trace_player.user.picture.url
                            if picture_url and not str(picture_url).endswith("null"):
                                if request:
                                    return request.build_absolute_uri(picture_url)
                                else:
                                    return picture_url
                        except (ValueError, AttributeError):
                            pass
                    return None
                
                # Look up player ID and logo
                player_info = players_lookup.get((team_side, jersey_number))
                if player_info:
                    enriched_event["id"] = player_info["player_id"]
                    enriched_event["logo"] = get_player_logo(player_info)
                else:
                    # Player not found, set to None
                    enriched_event["id"] = None
                    enriched_event["logo"] = None
                
                # Use language-specific player name if available
                if "language" in event and user_language in event["language"]:
                    enriched_event["name"] = event["language"][user_language]
                elif player_info and player_info.get("player"):
                    # Fallback: get localized name from player object
                    player_name = get_localized_name(player_info["player"], user_language, "name")
                    if player_name:
                        enriched_event["name"] = player_name
                
                # Remove the language object from response to avoid confusion
                if "language" in enriched_event:
                    del enriched_event["language"]
                
                # Rename keys to remove "player_" prefix
                if "player_name" in enriched_event:
                    del enriched_event["player_name"]
                if "player_id" in enriched_event:
                    del enriched_event["player_id"]
                if "player_jersey_number" in enriched_event:
                    enriched_event["jersey_number"] = enriched_event.pop("player_jersey_number")
                if "player_team_name" in enriched_event:
                    enriched_event["team_name"] = enriched_event.pop("player_team_name")
                
                # Localize team_name
                team = obj.home_team if team_side == "home" else obj.away_team
                if team:
                    localized_team_name = get_localized_team_name(team, user_language)
                    if localized_team_name:
                        enriched_event["team_name"] = localized_team_name
                
                # For goal events, include TraceHighlight and TraceClipReel data as a nested object
                if event.get("event_type") == "goal" and player_info:
                    try:
                        event_minute = event.get("minute", 0)
                        player_id = player_info.get("player_id")
                        
                        # Try to find matching highlight by (player_id, minute)
                        highlight = goal_highlights.get((player_id, event_minute))
                        
                        # Fallback: try to match by player_id only if minute match fails
                        if not highlight:
                            highlight = goal_highlights.get((player_id, None))
                        
                        if highlight:
                            # Serialize the highlight using HighlightClipReelSerializer
                            highlight_serializer = HighlightClipReelSerializer(
                                highlight,
                                context={"request": request}
                            )
                            highlight_data = highlight_serializer.data
                            
                            # Add highlight data as a nested object instead of merging
                            enriched_event["highlight"] = highlight_data
                    except Exception as e:
                        logger.warning(f"Error adding highlight data to goal event: {e}")
                
                # Handle replaced_by and replaced_player references
                if "replaced_by" in event and enriched_event.get("replaced_by"):
                    replaced_jersey = event["replaced_by"].get("jersey_number")
                    replaced_info = players_lookup.get((team_side, replaced_jersey))
                    if replaced_info:
                        enriched_event["replaced_by"]["id"] = replaced_info["player_id"]
                        enriched_event["replaced_by"]["logo"] = get_player_logo(replaced_info)
                        # Localize player name in replaced_by
                        if replaced_info.get("player"):
                            localized_name = get_localized_name(replaced_info["player"], user_language, "name")
                            if localized_name:
                                enriched_event["replaced_by"]["name"] = localized_name
                    else:
                        enriched_event["replaced_by"]["id"] = None
                        enriched_event["replaced_by"]["logo"] = None
                    
                    # Remove player_id if exists
                    if "player_id" in enriched_event["replaced_by"]:
                        del enriched_event["replaced_by"]["player_id"]
                
                if "replaced_player" in event and enriched_event.get("replaced_player"):
                    replaced_jersey = event["replaced_player"].get("jersey_number")
                    replaced_info = players_lookup.get((team_side, replaced_jersey))
                    if replaced_info:
                        enriched_event["replaced_player"]["id"] = replaced_info["player_id"]
                        enriched_event["replaced_player"]["logo"] = get_player_logo(replaced_info)
                        # Localize player name in replaced_player
                        if replaced_info.get("player"):
                            localized_name = get_localized_name(replaced_info["player"], user_language, "name")
                            if localized_name:
                                enriched_event["replaced_player"]["name"] = localized_name
                    else:
                        enriched_event["replaced_player"]["id"] = None
                        enriched_event["replaced_player"]["logo"] = None
                    
                    # Remove player_id if exists
                    if "player_id" in enriched_event["replaced_player"]:
                        del enriched_event["replaced_player"]["player_id"]
                
                enriched_timeline.append(enriched_event)
            except Exception as e:
                logger.warning(f"Error enriching timeline event: {e}")
                # Keep original event if enrichment fails
                enriched_timeline.append(event)
        
        # Group events by minute with separate home/away arrays
        grouped_timeline = {}
        for event in enriched_timeline:
            minute = event.get("minute", 0)
            team_side = event.get("team_side", "home")
            
            # Initialize minute group if not exists
            if minute not in grouped_timeline:
                grouped_timeline[minute] = {
                    "minute": minute,
                    "home": [],
                    "away": []
                }
            
            # Add event to appropriate team array
            grouped_timeline[minute][team_side].append(event)
        
        # Convert to sorted list by minute
        timeline_list = sorted(grouped_timeline.values(), key=lambda x: x["minute"])
        
        return timeline_list



class PlayerDetailSerializer(serializers.ModelSerializer):
    """Serializer for player details in highlights"""

    id = serializers.CharField(read_only=True)
    name = serializers.SerializerMethodField()
    team_id = serializers.CharField(source="team.id", read_only=True)
    team_name = serializers.SerializerMethodField()

    def get_name(self, obj):
        """Get localized player name based on user language"""
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return get_localized_name(obj, user_language, field_name="name")

    def get_team_name(self, obj):
        """Get localized team name based on user language"""
        if not obj.team:
            return None
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return get_localized_team_name(obj.team, user_language)

    

    created_at = serializers.DateTimeField(
        format="%Y-%m-%dT%H:%M:%S.%fZ", read_only=True
    )
    updated_at = serializers.DateTimeField(
        format="%Y-%m-%dT%H:%M:%S.%fZ", read_only=True
    )

    class Meta:
        model = TracePlayer
        fields = [
            "id",
            "name",
            "jersey_number",
            "position",
            "object_id",
            "team_id",
            "team_name",
            "is_mapped",
            "created_at",
            "updated_at",
        ]


class MatchInfoSerializer(serializers.ModelSerializer):
    """Serializer for match information"""

    session_id = serializers.CharField(source="id", read_only=True)
    match_date = serializers.DateField(format="%Y-%m-%d", read_only=True)
    home_team = serializers.SerializerMethodField()
    away_team = serializers.SerializerMethodField()

    class Meta:
        model = TraceSession
        fields = [
            "session_id",
            "match_date",
            "final_score",
            "home_score",
            "away_score",
            "home_team",
            "away_team",
            "age_group",
            "match_start_time",
            "first_half_end_time",
            "second_half_start_time",
            "match_end_time",
        ]

    def get_home_team(self, obj):
        """Get home team, transformed to 'team' or 'opponent' based on viewer"""
        if obj.home_team:
            # Get user language preference
            user_language = "en"
            request = self.context.get("request")
            if request and request.user:
                user_language = getattr(request.user, "selected_language", "en") or "en"
                viewer_team = get_viewer_team(request.user)
                if viewer_team:
                    viewer_perspective = determine_viewer_perspective(viewer_team, obj)
                    team_data = {
                        "id": str(obj.home_team.id),
                        "name": get_localized_team_name(obj.home_team, user_language),
                    }
                    if viewer_perspective == "home":
                        team_data["label"] = "home"
                    elif viewer_perspective == "away":
                        team_data["label"] = "away"
                    return team_data

            team_data = {
                "id": str(obj.home_team.id),
                "name": get_localized_team_name(obj.home_team, user_language),
            }
            return team_data
        return None

    def get_away_team(self, obj):
        """Get away team, transformed to 'team' or 'opponent' based on viewer"""
        if obj.away_team:
            # Get user language preference
            user_language = "en"
            request = self.context.get("request")
            if request and request.user:
                user_language = getattr(request.user, "selected_language", "en") or "en"
                viewer_team = get_viewer_team(request.user)
                if viewer_team:
                    viewer_perspective = determine_viewer_perspective(viewer_team, obj)
                    team_data = {
                        "id": str(obj.away_team.id),
                        "name": get_localized_team_name(obj.away_team, user_language),
                    }
                    if viewer_perspective == "away":
                        team_data["label"] = "away"
                    elif viewer_perspective == "home":
                        team_data["label"] = "home"
                    return team_data

            team_data = {
                "id": str(obj.away_team.id),
                "name": get_localized_team_name(obj.away_team, user_language),
            }
            return team_data
        return None


class ClipReelVideoSerializer(serializers.ModelSerializer):
    """Serializer for clip reel video information in highlight response"""

    url = serializers.URLField(source="video_url", read_only=True, allow_null=True)
    ratio = serializers.CharField(read_only=True)
    tags = serializers.JSONField(read_only=True)
    status = serializers.CharField(source="generation_status", read_only=True)
    default = serializers.BooleanField(source="is_default", read_only=True)
    label = serializers.CharField(read_only=True, allow_blank=True)
    primary_player = PlayerDetailSerializer(read_only=True, allow_null=True)
    can_generate = serializers.SerializerMethodField()

    class Meta:
        model = TraceClipReel
        fields = [
            "id",
            "url",
            "ratio",
            "tags",
            "status",
            "default",
            "label",
            "primary_player",
            "can_generate",
        ]

    def get_can_generate(self, obj):
        """Return True if primary_player is set, False otherwise"""
        return obj.primary_player is not None


class HighlightClipReelSerializer(serializers.ModelSerializer):
    """Serializer for TraceHighlight with related clip reel videos"""

    # Basic highlight fields
    id = serializers.IntegerField(read_only=True)
    highlight_id = serializers.CharField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    event_name = serializers.SerializerMethodField()
    side = serializers.SerializerMethodField()
    start_ms = serializers.IntegerField(source="start_offset", read_only=True)
    duration_ms = serializers.IntegerField(source="duration", read_only=True)
    match_time = serializers.SerializerMethodField()
    half = serializers.IntegerField(read_only=True, allow_null=True)

    # Videos list from related clip reels
    videos = serializers.SerializerMethodField()

    # Session info (minimal)
    age_group = serializers.CharField(source="session.age_group", read_only=True)
    match_date = serializers.DateField(
        source="session.match_date", format="%Y-%m-%d", read_only=True
    )

    # Commented out fields not needed by frontend
    # start_clock = serializers.SerializerMethodField()
    # end_clock = serializers.SerializerMethodField()
    trace_player = PlayerDetailSerializer(
        source="player", read_only=True, allow_null=True
    )
    primary_player = serializers.SerializerMethodField()
    involved_players = serializers.SerializerMethodField()
    # session = serializers.CharField(source="session.id", read_only=True)
    match_start_time = serializers.CharField(
        source="session.match_start_time", read_only=True
    )
    first_half_end_time = serializers.CharField(
        source="session.first_half_end_time", read_only=True
    )
    second_half_start_time = serializers.CharField(
        source="session.second_half_start_time", read_only=True
    )
    match_end_time = serializers.CharField(
        source="session.match_end_time", read_only=True
    )
    # basic_game_stats = serializers.SerializerMethodField()
    # generation_started_at = serializers.DateTimeField(
    #     format="%Y-%m-%dT%H:%M:%S.%fZ", read_only=True, allow_null=True
    # )
    # generation_completed_at = serializers.DateTimeField(
    #     format="%Y-%m-%dT%H:%M:%S.%fZ", read_only=True, allow_null=True
    # )
    # created_at = serializers.DateTimeField(
    #     format="%Y-%m-%dT%H:%M:%S.%fZ", read_only=True, allow_null=True
    # )
    # updated_at = serializers.DateTimeField(
    #     format="%Y-%m-%dT%H:%M:%S.%fZ", read_only=True, allow_null=True
    # )
    # generation_errors = serializers.JSONField(default=list)
    # generation_metadata = serializers.JSONField(default=dict)
    # description = serializers.SerializerMethodField()
    # tags = serializers.SerializerMethodField()
    # video_type = serializers.CharField(read_only=True)
    # video_variant_name = serializers.CharField(read_only=True)
    # video_url = serializers.URLField(read_only=True)
    # video_thumbnail_url = serializers.URLField(read_only=True)
    # video_size_mb = serializers.FloatField(read_only=True)
    # video_duration_seconds = serializers.FloatField(read_only=True)
    # resolution = serializers.CharField(read_only=True)
    # frame_rate = serializers.IntegerField(read_only=True)
    # bitrate = serializers.IntegerField(read_only=True)
    label = serializers.SerializerMethodField()
    # video_stream = serializers.URLField(read_only=True)

    class Meta:
        model = TraceHighlight
        fields = [
            "id",
            "highlight_id",
            "event_type",
            "event_name",
            "side",
            "start_ms",
            "duration_ms",
            "match_time",
            "half",
            "age_group",
            "match_date",
            "label",
            "trace_player",
            "primary_player",
            "involved_players",
            "match_start_time",
            "first_half_end_time",
            "second_half_start_time",
            "match_end_time",
            "videos",
        ]

    def get_match_time(self, obj):
        """Get match time safely"""
        if hasattr(obj, "match_time"):
            return obj.match_time
        if hasattr(obj, "highlight") and hasattr(obj.highlight, "match_time"):
            return obj.highlight.match_time
        return None

    def get_event_name(self, obj):
        """Generate event name from event type and match time"""
        time_str = "Unknown time"
        if hasattr(obj, "match_time"):
            time_str = obj.match_time or "Unknown time"
        elif hasattr(obj, "highlight") and hasattr(obj.highlight, "match_time"):
            time_str = obj.highlight.match_time or "Unknown time"
            
        # Get event type - use get_event_type_display if available
        if hasattr(obj, 'get_event_type_display'):
            event_type = obj.get_event_type_display()
        else:
            event_type = getattr(obj, 'event_type', 'Event')
        return f"{event_type} at {time_str}"

    def get_side(self, obj):
        """Get side from highlight tags or player team"""
        # Try to get from tags first
        if obj.tags and isinstance(obj.tags, list):
            for tag in obj.tags:
                if tag in ["home", "away"]:
                    side = tag
                    # Apply perspective transformation
                    request = self.context.get("request")
                    if request and request.user:
                        viewer_team = get_viewer_team(request.user)
                        if viewer_team:
                            viewer_perspective = determine_viewer_perspective(
                                viewer_team, obj.session
                            )
                            if viewer_perspective:
                                side = transform_side_by_perspective(
                                    side, viewer_perspective
                                )
                    return side

        # Fallback to player's team
        # TraceHighlight has 'player', TraceClipReel has 'primary_player'
        player = getattr(obj, 'primary_player', None) or getattr(obj, 'player', None)
        if player and player.team:
            session = obj.session
            side = None
            if session.home_team and session.home_team.id == player.team.id:
                side = "home"
            elif session.away_team and session.away_team.id == player.team.id:
                side = "away"

            # Apply perspective transformation
            if side:
                request = self.context.get("request")
                if request and request.user:
                    viewer_team = get_viewer_team(request.user)
                    if viewer_team:
                        viewer_perspective = determine_viewer_perspective(
                            viewer_team, session
                        )
                        if viewer_perspective:
                            side = transform_side_by_perspective(
                                side, viewer_perspective
                            )
                return side

        return None

    def get_videos(self, obj):
        """Get related clip reels as videos"""
        # obj is a TraceHighlight, get its related clip reels
        if hasattr(obj, 'clip_reels'):
            clip_reels = obj.clip_reels.all()
            return ClipReelVideoSerializer(clip_reels, many=True, context=self.context).data
            
        # obj is a TraceClipReel (it has 'highlight' FK but no 'clip_reels' manager)
        # In this case, the object itself IS the video
        if hasattr(obj, 'highlight') and hasattr(obj, 'generation_status'):
             return ClipReelVideoSerializer([obj], many=True, context=self.context).data
             
        return []

    def get_label(self, obj):
        """Get label from clip reel or generate from event_name"""
        # Check if obj has a label attribute (TraceClipReel has it, TraceHighlight doesn't)
        if hasattr(obj, 'label') and obj.label:
            return obj.label

        # Fallback to event_name if no label
        return self.get_event_name(obj)

    def get_primary_player(self, obj):
        """Get primary player - handles both TraceHighlight and TraceClipReel"""
        # TraceClipReel has 'primary_player', TraceHighlight has 'player'
        player = getattr(obj, 'primary_player', None) or getattr(obj, 'player', None)
        if player:
            return PlayerDetailSerializer(player, context=self.context).data
        return None

    def get_involved_players(self, obj):
        """Get involved players - handles both TraceHighlight and TraceClipReel"""
        # TraceClipReel has 'involved_players' ManyToMany field
        if hasattr(obj, 'involved_players'):
            players = obj.involved_players.all()
            return PlayerDetailSerializer(players, many=True, context=self.context).data
        # TraceHighlight doesn't have involved_players
        return []

    # Commented out methods not needed by frontend
    # def get_start_clock(self, obj):
    #     """Convert start_ms to clock format"""
    #     from datetime import timedelta
    #     start_td = timedelta(milliseconds=obj.start_offset)
    #     return str(start_td)

    # def get_end_clock(self, obj):
    #     """Convert end_ms to clock format"""
    #     from datetime import timedelta
    #     end_td = timedelta(milliseconds=obj.start_offset + obj.duration)
    #     return str(end_td)

    # def get_basic_game_stats(self, obj):
    #     """Get basic game stats URL"""
    #     if obj.session and obj.session.basic_game_stats:
    #         return obj.session.basic_game_stats.url
    #     return None

    # def get_description(self, obj):
    #     """Get description or generate default"""
    #     return f"{obj.get_event_type_display()} event"

    # def get_tags(self, obj):
    #     """Get tags or generate default"""
    #     if obj.tags:
    #         return obj.tags
    #     side = self.get_side(obj)
    #     return [side, obj.event_type] if side and obj.event_type else []


class PossessionTeamMetricsSerializer(serializers.Serializer):
    """Serializer for team possession metrics"""

    team = serializers.SerializerMethodField()
    possession_time_ms = serializers.IntegerField()
    possession_count = serializers.IntegerField()
    avg_duration_ms = serializers.FloatField()
    avg_passes = serializers.FloatField()
    longest_possession_ms = serializers.IntegerField()
    turnovers = serializers.IntegerField()
    total_touches = serializers.IntegerField()
    total_passes = serializers.IntegerField()
    possession_percentage = serializers.FloatField()

    def get_team(self, obj):
        """Get team details with transformed side"""
        team_data = None
        if obj.get("team"):
            # Get user language preference
            user_language = "en"
            if self.context.get("request") and hasattr(self.context["request"], "user"):
                user_language = (
                    getattr(self.context["request"].user, "selected_language", "en")
                    or "en"
                )
            team_data = {
                "id": str(obj["team"].id),
                "name": get_localized_team_name(obj["team"], user_language),
            }

        # Add transformed side to team data
        side = obj.get("side")
        if side:
            # Get viewer perspective from context
            request = self.context.get("request")
            session = self.context.get("session")
            if request and request.user and session:
                viewer_team = get_viewer_team(request.user)
                if viewer_team:
                    viewer_perspective = determine_viewer_perspective(
                        viewer_team, session
                    )
                    if viewer_perspective:
                        side = transform_side_by_perspective(side, viewer_perspective)

            if team_data:
                team_data["side"] = side

        return team_data


class PossessionPlayerMetricsSerializer(serializers.Serializer):
    """Serializer for player possession metrics"""

    player = serializers.SerializerMethodField()
    involvement_count = serializers.IntegerField()
    total_duration_ms = serializers.IntegerField()
    total_touches = serializers.IntegerField()
    total_passes = serializers.IntegerField()
    possession_percentage = serializers.FloatField()

    def get_player(self, obj):
        """Get player details with team info, transformed by viewer perspective"""
        player = obj.get("player")
        if not player:
            return None

        team = player.team
        side = None

        # Get session from context if available
        session = self.context.get("session")
        if session and team:
            if session.home_team and team.id == session.home_team.id:
                side = "home"
            elif session.away_team and team.id == session.away_team.id:
                side = "away"

        # Transform side based on viewer perspective
        request = self.context.get("request")
        if request and request.user and session and side:
            viewer_team = get_viewer_team(request.user)
            if viewer_team:
                viewer_perspective = determine_viewer_perspective(viewer_team, session)
                if viewer_perspective:
                    side = transform_side_by_perspective(side, viewer_perspective)

        # Get user language preference
        user_language = "en"
        if request and request.user:
            user_language = getattr(request.user, "selected_language", "en") or "en"

        return {
            "id": str(player.id),
            "name": get_localized_player_name(player, user_language),
            "jersey_number": player.jersey_number,
            "position": player.position,
            "object_id": player.object_id,
            "team_id": str(team.id) if team else None,
            "team_name": team.name if team else None,
            "side": side,
        }


class GenerateHighlightClipReelSerializer(serializers.Serializer):
    """
    Serializer for highlight clip reel generation request.
    Validates input and ensures only expected fields are accepted.

    Accepts only clip_reel_id (single ID).
    """

    clip_reel_id = serializers.IntegerField(
        required=True,
        help_text="TraceClipReel ID to generate highlights for",
    )

    def validate(self, attrs):
        """Validate the entire data and reject any extra fields."""
        # Get the original data to check for extra fields
        if hasattr(self, "initial_data"):
            allowed_fields = {"clip_reel_id"}
            extra_fields = set(self.initial_data.keys()) - allowed_fields
            if extra_fields:
                raise serializers.ValidationError(
                    f"Unexpected fields: {', '.join(sorted(extra_fields))}. "
                    f"Allowed fields are: {', '.join(sorted(allowed_fields))}"
                )

        return attrs


class MapUserToPlayerSerializer(serializers.Serializer):
    """
    Serializer for mapping a WajoUser to a TracePlayer.
    Validates input and ensures only expected fields are accepted.
    """

    user_id = serializers.CharField(
        required=True,
        help_text="Phone number (primary key) of the WajoUser to map",
    )
    player_id = serializers.IntegerField(
        required=True,
        help_text="ID of the TracePlayer to map to",
    )

    def validate(self, attrs):
        """Validate the entire data and reject any extra fields."""
        if hasattr(self, "initial_data"):
            allowed_fields = {"user_id", "player_id"}
            extra_fields = set(self.initial_data.keys()) - allowed_fields
            if extra_fields:
                raise serializers.ValidationError(
                    f"Unexpected fields: {', '.join(sorted(extra_fields))}. "
                    f"Allowed fields are: {', '.join(sorted(allowed_fields))}"
                )
        return attrs


# ============================================================================
# TraceClipReel Comment System Serializers
# ============================================================================


class WajoUserBasicSerializer(serializers.Serializer):
    """
    Basic user information for nested serialization.
    Used in comments and notes to display author details.
    """

    id = serializers.UUIDField(read_only=True)
    name = serializers.SerializerMethodField()
    phone_no = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    picture = serializers.ImageField(read_only=True)
    jersey_number = serializers.IntegerField(read_only=True)

    def get_name(self, obj):
        """Get localized user name based on user language"""
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return get_localized_name(obj, user_language, field_name="name")


class GameUserSerializer(serializers.ModelSerializer):
    """
    Serializer for listing users associated with a game.
    Includes contact information and registration status.
    """
    
    name = serializers.SerializerMethodField()
    team_id = serializers.CharField(source="team.id", read_only=True, allow_null=True)
    team_name = serializers.SerializerMethodField()
    
    def get_name(self, obj):
        """Get localized user name"""
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return get_localized_name(obj, user_language, field_name="name")
    
    def get_team_name(self, obj):
        """Get localized team name"""
        if not obj.team:
            return None
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return get_localized_team_name(obj.team, user_language)
    
    class Meta:
        model = WajoUser
        fields = [
            "id",
            "name",
            "email",
            "phone_no",
            "role",
            "is_registered",
            "team_id",
            "team_name",
            "jersey_number",
        ]
        read_only_fields = fields


class TraceClipReelShareSerializer(serializers.ModelSerializer):
    """
    Serializer for sharing clip reels with other users.
    Enforces permission checks and prevents unauthorized access.
    """

    shared_by = WajoUserBasicSerializer(read_only=True)
    shared_with_user = WajoUserBasicSerializer(
        source="shared_with", read_only=True
    )

    # Write-only inputs
    clip_reel_id = serializers.IntegerField(write_only=True)
    highlight_id = serializers.IntegerField(write_only=True)
    shared_with_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = TraceClipReelShare
        fields = [
            "id",
            "clip_reel",
            "clip_reel_id",
            "highlight",
            "highlight_id",
            "shared_by",
            "shared_with",
            "shared_with_id",
            "shared_with_user",
            "can_comment",
            "shared_at",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "clip_reel",
            "highlight",
            "shared_by",
            "shared_with",
            "shared_at",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user

        # Resolve objects safely
        clip_reel = get_object_or_404(
            TraceClipReel, id=attrs["clip_reel_id"]
        )
        highlight = get_object_or_404(
            TraceHighlight, id=attrs["highlight_id"]
        )
        shared_with = get_object_or_404(
            WajoUser, id=attrs["shared_with_id"]
        )

        # ❌ Prevent self-sharing
        if shared_with == user:
            raise ValidationError("You cannot share a clip reel with yourself.")

        # ✅ Ownership / permission check
        is_owner = (
            clip_reel.primary_player
            and clip_reel.primary_player.user == user
        )

        if not is_owner:
            has_access = TraceClipReelShare.objects.filter(
                clip_reel=clip_reel,
                shared_with=user,
                is_active=True,
            ).exists()

            if not has_access:
                raise ValidationError(
                    "You don't have permission to share this clip reel."
                )

        # ✅ NEW: Validate that shared_with user belongs to the game
        # Get the session from highlight
        session = highlight.session
        
        # Check if user belongs to the game through multiple paths:
        # 1. Player on home or away team
        # 2. Coach of home or away team
        # 3. Has GameUserRole for the game (includes referees)
        
        belongs_to_game = False
        
        # Check if user is on home or away team
        if shared_with.team:
            if session.home_team and shared_with.team.id == session.home_team.id:
                belongs_to_game = True
            elif session.away_team and shared_with.team.id == session.away_team.id:
                belongs_to_game = True
        
        # Check if user is a coach of either team
        if not belongs_to_game and shared_with.role == "Coach":
            coached_teams = shared_with.teams_coached.values_list("id", flat=True)
            if session.home_team and session.home_team.id in coached_teams:
                belongs_to_game = True
            elif session.away_team and session.away_team.id in coached_teams:
                belongs_to_game = True
        
        # Check if user has a GameUserRole for this session's game
        if not belongs_to_game and session.game:
            from games.models import GameUserRole
            has_game_role = GameUserRole.objects.filter(
                game=session.game,
                user=shared_with
            ).exists()
            if has_game_role:
                belongs_to_game = True
        
        # Raise error if user doesn't belong to the game
        if not belongs_to_game:
            raise ValidationError(
                "This user is not associated with the game"
            )

        # Attach resolved objects
        attrs["clip_reel"] = clip_reel
        attrs["highlight"] = highlight
        attrs["shared_with"] = shared_with

        return attrs

    def create(self, validated_data):
        """
        Create or reactivate a reel share safely.
        """
        request = self.context["request"]

        validated_data.pop("clip_reel_id", None)
        validated_data.pop("highlight_id", None)
        validated_data.pop("shared_with_id", None)

        share, created = TraceClipReelShare.objects.update_or_create(
            clip_reel=validated_data["clip_reel"],
            shared_with=validated_data["shared_with"],
            defaults={
                "highlight": validated_data["highlight"],
                "shared_by": request.user,
                "can_comment": validated_data.get("can_comment", True),
                "is_active": True,
            },
        )

        return share


class TraceClipReelCommentSerializer(serializers.ModelSerializer):
    """
    Serializer for clip reel comments.
    Supports public/private visibility, mentions, and threaded replies.
    """

    author = WajoUserBasicSerializer(read_only=True)
    likes_count = serializers.IntegerField(read_only=True)
    replies_count = serializers.IntegerField(read_only=True)
    is_liked = serializers.SerializerMethodField()
    clip_reel_id = serializers.IntegerField(write_only=True, required=False)
    highlight_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = TraceClipReelComment
        fields = [
            "id",
            "clip_reel",
            "clip_reel_id",
            "highlight",
            "highlight_id",
            "author",
            "content",
            "visibility",
            "parent_comment",
            "mentions",
            "is_edited",
            "is_deleted",
            "likes_count",
            "replies_count",
            "is_liked",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "clip_reel",
            "highlight",
            "author",
            "is_edited",
            "is_deleted",
            "created_at",
            "updated_at",
        ]

    def get_is_liked(self, obj):
        """Check if current user has liked this comment"""
        user = self.context["request"].user
        return TraceClipReelCommentLike.objects.filter(
            comment=obj, user=user
        ).exists()

    def validate(self, attrs):
        """Validate comment access and mentions"""
        from tracevision.models import TraceClipReel, TraceHighlight
        from django.shortcuts import get_object_or_404
        
        user = self.context["request"].user
        
        # Resolve clip_reel_id and highlight_id to objects
        clip_reel_id = attrs.get("clip_reel_id")
        highlight_id = attrs.get("highlight_id")
        
        if clip_reel_id:
            clip_reel = get_object_or_404(TraceClipReel, id=clip_reel_id)
            attrs["clip_reel"] = clip_reel
        else:
            clip_reel = attrs.get("clip_reel")
        
        if highlight_id:
            highlight = get_object_or_404(TraceHighlight, id=highlight_id)
            attrs["highlight"] = highlight

        # Check if user has access to clip reel
        if clip_reel:
            is_owner = (
                clip_reel.primary_player and clip_reel.primary_player.user == user
            )
            
            # Owner always has access
            if is_owner:
                pass  # Owner can always comment
            else:
                # Check if explicitly shared with user
                has_share = TraceClipReelShare.objects.filter(
                    clip_reel=clip_reel, shared_with=user, is_active=True
                ).exists()
                
                # Check coach-player relationships
                has_coach_relationship = False
                if user.role == "Coach" and clip_reel.primary_player:
                    player_user = clip_reel.primary_player.user
                    
                    # Check if coach is part of the player's team
                    if player_user.team:
                        team_coaches = player_user.team.coach.all()
                        if user in team_coaches:
                            has_coach_relationship = True
                    
                    # Check if coach is personally assigned to the player
                    if not has_coach_relationship and player_user.coach.filter(id=user.id).exists():
                        has_coach_relationship = True
                
                # User must have share OR coach relationship
                if not has_share and not has_coach_relationship:
                    raise ValidationError("You don't have access to this clip reel.")

                # If user has a share, check can_comment permission
                if has_share:
                    share = TraceClipReelShare.objects.filter(
                        clip_reel=clip_reel, shared_with=user, is_active=True
                    ).first()
                    if not share or not share.can_comment:
                        raise ValidationError(
                            "You don't have permission to comment on this clip reel."
                        )
                # Coach relationships automatically grant comment permission

        # Validate mentions if provided
        mentions = attrs.get("mentions", [])
        if mentions:
            from accounts.models import WajoUser

            for mention in mentions:
                user_id = mention.get("user_id")
                if user_id:
                    try:
                        WajoUser.objects.get(id=user_id)
                    except WajoUser.DoesNotExist:
                        raise ValidationError(
                            f"Mentioned user with id {user_id} does not exist."
                        )

        return attrs

    def create(self, validated_data):
        """Set author to current user"""
        # Remove write-only fields
        validated_data.pop("clip_reel_id", None)
        validated_data.pop("highlight_id", None)
        
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)


class TraceClipReelCommentEditSerializer(serializers.ModelSerializer):
    """
    Serializer for editing existing comments.
    Creates edit history and sets is_edited flag.
    """

    class Meta:
        model = TraceClipReelComment
        fields = ["content", "mentions"]

    def update(self, instance, validated_data):
        """Update comment and create edit history"""
        # Save previous content to edit history
        TraceClipReelCommentEditHistory.objects.create(
            comment=instance,
            previous_content=instance.content,
            edited_by=self.context["request"].user,
        )

        # Update comment
        instance.content = validated_data.get("content", instance.content)
        instance.mentions = validated_data.get("mentions", instance.mentions)
        instance.is_edited = True
        instance.save()

        return instance


class TraceClipReelCommentLikeSerializer(serializers.ModelSerializer):
    """
    Serializer for comment likes.
    Validates that user has access to the comment.
    """

    user = WajoUserBasicSerializer(read_only=True)

    class Meta:
        model = TraceClipReelCommentLike
        fields = ["id", "comment", "user", "created_at"]
        read_only_fields = ["id", "user", "created_at"]

    def validate(self, attrs):
        """Validate that user can view the comment"""
        user = self.context["request"].user
        comment = attrs.get("comment")

        if comment and not comment.can_view(user):
            raise ValidationError("You don't have access to this comment.")

        return attrs

    def create(self, validated_data):
        """Set user to current user"""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class TraceClipReelNoteSerializer(serializers.ModelSerializer):
    """
    Serializer for private notes on clip reels.
    Only for Players and Coaches.
    """

    author = WajoUserBasicSerializer(read_only=True)
    created_by = serializers.SerializerMethodField()
    is_shared = serializers.SerializerMethodField()
    shared_with_count = serializers.SerializerMethodField()
    clip_reel_id = serializers.IntegerField(write_only=True, required=False)
    highlight_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = TraceClipReelNote
        fields = [
            "id",
            "clip_reel",
            "clip_reel_id",
            "highlight",
            "highlight_id",
            "author",
            "created_by",
            "content",
            "is_deleted",
            "is_shared",
            "shared_with_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "clip_reel", "highlight", "author", "is_deleted", "created_at", "updated_at"]
    
    def get_created_by(self, obj):
        """Return the role of the note creator (Player or Coach)"""
        return obj.author.role if obj.author else None

    def get_is_shared(self, obj):
        """Check if note has any active shares"""
        return obj.shares.filter(is_active=True).exists()

    def get_shared_with_count(self, obj):
        """Count how many users/groups note is shared with"""
        return obj.shares.filter(is_active=True).count()

    def validate(self, attrs):
        """Validate that author is Player or Coach and resolve clip_reel_id/highlight_id"""
        from django.shortcuts import get_object_or_404
        
        user = self.context["request"].user

        if user.role not in ["Player", "Coach"]:
            raise ValidationError("Only Players and Coaches can create notes.")

        # Resolve clip_reel_id and highlight_id to objects
        clip_reel_id = attrs.get("clip_reel_id")
        highlight_id = attrs.get("highlight_id")
        
        if clip_reel_id:
            clip_reel = get_object_or_404(TraceClipReel, id=clip_reel_id)
            attrs["clip_reel"] = clip_reel
        
        if highlight_id:
            highlight = get_object_or_404(TraceHighlight, id=highlight_id)
            attrs["highlight"] = highlight

        return attrs

    def create(self, validated_data):
        """Set author to current user and remove write-only fields"""
        # Remove write-only fields
        validated_data.pop("clip_reel_id", None)
        validated_data.pop("highlight_id", None)
        
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)


class TraceClipReelNoteShareSerializer(serializers.ModelSerializer):
    """
    Serializer for sharing notes with users or groups.
    Validates either user OR group is specified.
    """

    shared_by = WajoUserBasicSerializer(read_only=True)
    shared_with_user_details = WajoUserBasicSerializer(
        source="shared_with_user", read_only=True
    )
    shared_with_user_id = serializers.UUIDField(
        write_only=True, required=False, source="shared_with_user"
    )

    class Meta:
        model = TraceClipReelNoteShare
        fields = [
            "id",
            "note",
            "shared_by",
            "shared_with_user",
            "shared_with_user_id",
            "shared_with_user_details",
            "shared_with_group",
            "shared_at",
            "is_active",
        ]
        read_only_fields = ["id", "shared_by", "shared_at"]

    def validate(self, attrs):
        """Validate that either user OR group is specified"""
        shared_with_user = attrs.get("shared_with_user")
        shared_with_group = attrs.get("shared_with_group")

        if shared_with_user and shared_with_group:
            raise ValidationError(
                "Cannot share with both a user and a group. Choose one."
            )

        if not shared_with_user and not shared_with_group:
            raise ValidationError("Must specify either a user or a group to share with.")

        # Validate that user has permission to share (must be note author)
        note = attrs.get("note")
        user = self.context["request"].user
        if note and note.author != user:
            raise ValidationError("Only the note author can share it.")

        return attrs

    def create(self, validated_data):
        """Set shared_by to current user"""
        validated_data["shared_by"] = self.context["request"].user
        return super().create(validated_data)


class TraceClipReelCaptionSerializer(serializers.ModelSerializer):
    """
    Serializer for updating clip reel caption.
    Only owner can update caption.
    """

    class Meta:
        model = TraceClipReel
        fields = ["caption"]

    def validate(self, attrs):
        """Validate that user is the owner"""
        user = self.context["request"].user
        clip_reel = self.instance

        if clip_reel:
            is_owner = (
                clip_reel.primary_player and clip_reel.primary_player.user == user
            )
            if not is_owner:
                raise ValidationError("Only the owner can update the caption.")

        return attrs


class BulkHighlightShareSerializer(serializers.Serializer):
    
    """
    Serializer for sharing a clip reel with multiple users in a single request.
    Supports both players and coaches sharing clip reels.
    """
    
    clip_id = serializers.IntegerField(required=True)
    user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=True,
        allow_empty=False,
        help_text="List of user IDs to share the clip reel with"
    )
    can_comment = serializers.BooleanField(default=True, required=False)
    
    def validate_clip_id(self, value):
        """Validate that clip reel exists"""
        try:
            clip_reel = TraceClipReel.objects.select_related('highlight__session').get(id=value)
            return value
        except TraceClipReel.DoesNotExist:
            raise ValidationError(f"Clip reel with ID {value} does not exist")
    
    def validate_user_ids(self, value):
        """Validate that all user IDs exist and are unique"""
        if not value:
            raise ValidationError("At least one user ID must be provided")
        
        # Remove duplicates while preserving order
        unique_ids = list(dict.fromkeys(value))
        
        # Check all users exist
        existing_users = WajoUser.objects.filter(id__in=unique_ids)
        existing_ids = set(str(user.id) for user in existing_users)
        provided_ids = set(str(uid) for uid in unique_ids)
        
        missing_ids = provided_ids - existing_ids
        if missing_ids:
            raise ValidationError(
                f"The following user IDs do not exist: {', '.join(missing_ids)}"
            )
        
        return unique_ids
    
    def validate(self, attrs):
        from tracevision.models import Game
        """Validate access and prevent self-sharing"""
        request = self.context.get("request")
        user = request.user
        
        # Get clip reel and highlight
        clip_reel = get_object_or_404(TraceClipReel.objects.select_related('highlight__session'), id=attrs["clip_id"])
        highlight = clip_reel.highlight
        session = highlight.session
        
        # Check if user has access to the session
        user_games = Game.objects.filter(
            game_roles__user=user
        ).values_list("id", flat=True)
        
        has_access = (
            session.user == user
            or (session.game and session.game.id in user_games)
            or session.home_team == user.team
            or session.away_team == user.team
        )
        
        if not has_access:
            raise ValidationError(
                "You don't have permission to share this clip reel"
            )
        
        # Check user role
        if user.role not in ["Player", "Coach"]:
            raise ValidationError(
                "Only players and coaches can share clip reels"
            )
        
        # Prevent self-sharing
        user_id_str = str(user.id)
        if user_id_str in [str(uid) for uid in attrs["user_ids"]]:
            raise ValidationError("You cannot share a clip reel with yourself")
        
        # Attach objects for use in create
        attrs["clip_reel"] = clip_reel
        attrs["highlight"] = highlight
        attrs["session"] = session
        
        return attrs
    
    def create(self, validated_data):
        """Create shares for all users"""
        clip_reel = validated_data["clip_reel"]
        highlight = validated_data["highlight"]
        session = validated_data["session"]
        user_ids = validated_data["user_ids"]
        can_comment = validated_data.get("can_comment", True)
        request = self.context.get("request")
        shared_by = request.user
        
        results = []
        
        # For each recipient
        for user_id in user_ids:
            shared_with = WajoUser.objects.get(id=user_id)
            
            # Check if user belongs to the game
            belongs_to_game = False
            
            # Check if user is on home or away team
            if shared_with.team:
                if session.home_team and shared_with.team.id == session.home_team.id:
                    belongs_to_game = True
                elif session.away_team and shared_with.team.id == session.away_team.id:
                    belongs_to_game = True
            
            # Check if user is a coach of either team
            if not belongs_to_game and shared_with.role == "Coach":
                coached_teams = shared_with.teams_coached.values_list("id", flat=True)
                if session.home_team and session.home_team.id in coached_teams:
                    belongs_to_game = True
                elif session.away_team and session.away_team.id in coached_teams:
                    belongs_to_game = True
            
            # Check if user has a GameUserRole for this session's game
            if not belongs_to_game and session.game:
                from games.models import GameUserRole
                has_game_role = GameUserRole.objects.filter(
                    game=session.game,
                    user=shared_with
                ).exists()
                if has_game_role:
                    belongs_to_game = True
            
            user_result = {
                "user_id": str(user_id),
                "user_name": shared_with.name or shared_with.phone_no or shared_with.email,
                "shares_created": 0,
                "shares_updated": 0,
                "belongs_to_game": belongs_to_game
            }
            
            # Only create shares if user belongs to the game
            if belongs_to_game:
                # Create share for the specific clip reel
                share, created = TraceClipReelShare.objects.update_or_create(
                    clip_reel=clip_reel,
                    shared_with=shared_with,
                    defaults={
                        "highlight": highlight,
                        "shared_by": shared_by,
                        "can_comment": can_comment,
                        "is_active": True,
                    }
                )
                
                if created:
                    user_result["shares_created"] = 1
                else:
                    user_result["shares_updated"] = 1
                
                user_result["status"] = "success"
            else:
                user_result["status"] = "skipped"
                user_result["reason"] = "User is not associated with this game"
            
            results.append(user_result)
        
        return {
            "clip_id": clip_reel.id,
            "highlight_id": highlight.id,
            "recipients_count": len(user_ids),
            "shares": results
        }


class UserRegistrationStatusSerializer(serializers.Serializer):
    """
    Serializer for user registration status response.
    Returns user details with localized names and team information.
    """
    
    user_id = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    mobile_number = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    is_registered = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    
    def get_user_id(self, obj):
        """Get user ID"""
        user = obj.get('user')
        return str(user.id) if user else None
    
    def get_user_name(self, obj):
        """Get localized user name based on language preference"""
        user = obj.get('user')
        if not user:
            return None
        
        request = self.context.get('request')
        if not request:
            return user.name or user.phone_no
        
        # Get user's selected language
        selected_language = request.user.selected_language or 'en'
        
        # Try to get localized name from language_metadata
        if user.language_metadata:
            localized_name = user.language_metadata.get(selected_language, {}).get('name')
            if localized_name:
                return localized_name
        
        # Fallback to name or phone_no
        return user.name or user.phone_no
    
    def get_user_role(self, obj):
        """Get user role"""
        return obj.get('user_role')
    
    def get_is_registered(self, obj):
        """Get user registration status"""
        return obj.get('is_registered', False)
    
    def get_mobile_number(self, obj):
        """Get user mobile number"""
        user = obj.get('user')
        return user.phone_no if user else None
    
    def get_email(self, obj):
        """Get user email"""
        user = obj.get('user')
        return user.email if user else None
    
    def get_team(self, obj):
        """Get team information for the user"""
        user = obj.get('user')
        if not user:
            return None
        
        request = self.context.get('request')
        selected_language = 'en'
        if request:
            selected_language = request.user.selected_language or 'en'
        
        teams = []
        
        # For Players - get their team
        if user.role == "Player" and user.team:
            team_name = user.team.name
            
            # Get localized team name
            if user.team.language_metadata:
                localized_team_name = user.team.language_metadata.get(selected_language, {}).get('name')
                if localized_team_name:
                    team_name = localized_team_name
            
            teams.append({
                "id": str(user.team.id),
                "name": team_name,
                "relationship": "player"
            })
        
        # For Coaches - get all teams they coach
        elif user.role == "Coach":
            coached_teams = user.teams_coached.all()
            for team in coached_teams:
                team_name = team.name
                
                # Get localized team name
                if team.language_metadata:
                    localized_team_name = team.language_metadata.get(selected_language, {}).get('name')
                    if localized_team_name:
                        team_name = localized_team_name
                
                teams.append({
                    "id": str(team.id),
                    "name": team_name,
                    "relationship": "coach"
                })
        
        return teams if teams else None
