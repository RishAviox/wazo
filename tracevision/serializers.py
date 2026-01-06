import uuid
import logging
from django.db.models import Q
from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError


from tracevision.models import TraceSession, TraceClipReel, TracePlayer, TraceHighlight
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

        # session_payload = {
        #     "query": """
        #         mutation ($token: CustomerToken!, $sessionData: SessionCreateInput!) {
        #             createSession(token: $token, sessionData: $sessionData) {
        #                 session { session_id }
        #                 success
        #                 error
        #             }
        #         }
        #     """,
        #     "variables": {
        #         "token": {"customer_id": customer_id, "token": api_key},
        #         "sessionData": {
        #             "type": "soccer_game",
        #             "game_info": {
        #                 "home_team": {
        #                     "name": home_team_name,
        #                     "score": home_score,
        #                     "color": home_color,
        #                 },
        #                 "away_team": {
        #                     "name": away_team_name,
        #                     "score": away_score,
        #                     "color": away_color,
        #                 },
        #             },
        #             "capabilities": ["tracking", "highlights"],
        #         },
        #     },
        # }

        # session_response = requests.post(
        #     graphql_url,
        #     headers={"Content-Type": "application/json"},
        #     json=session_payload,
        # )
        # session_json = session_response.json()

        # if session_response.status_code != 200 or not session_json.get("data", {}).get(
        #     "createSession", {}
        # ).get("success"):
        #     raise ValidationError(
        #         {
        #             "error": "TraceVision session creation failed",
        #             "details": session_json,
        #         }
        #     )

        # session_id = session_json["data"]["createSession"]["session"]["session_id"]
        session_id = "1234567890"

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
        # if video_link:
        #     video_url_for_db = TraceVisionService.import_game_video(
        #         session_id=session_id, video_link=video_link, start_time=start_time
        #     )
        # else:
        #     # Video file upload is not supported - this should be caught by validation
        #     # but adding safety check here as well
        #     raise ValidationError(
        #         {
        #             "error": "Video file upload not supported",
        #             "message": "Video file upload is currently not supported. Please use video_link instead to provide a URL to your video.",
        #         }
        #     )
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
        # from tracevision.tasks import download_video_and_save_to_azure_blob
        # download_video_and_save_to_azure_blob.delay(session.id)


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


class HighlightDateTeamSerializer(serializers.Serializer):
    """Serializer for team info in highlight dates response"""

    id = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)
    logo = serializers.SerializerMethodField()

    def get_logo(self, instance):
        """Get team logo URL"""
        if instance is None:
            return None
        if instance.logo:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(instance.logo.url)
            return instance.logo.url
        return None

    def to_representation(self, instance):
        """Handle None team instances"""
        if instance is None:
            return {"id": None, "name": None, "logo": None}
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return {
            "id": instance.id,
            "name": get_localized_team_name(instance, user_language),
            "logo": self.get_logo(instance),
        }


class HighlightDateSessionSerializer(serializers.ModelSerializer):
    """Serializer for session info in highlight dates response"""

    id = serializers.IntegerField(read_only=True)
    session_id = serializers.CharField(read_only=True)
    match_date = serializers.DateField(format="%Y-%m-%d", read_only=True)
    home_team = HighlightDateTeamSerializer(read_only=True)
    away_team = HighlightDateTeamSerializer(read_only=True)
    players = serializers.SerializerMethodField()
    match_logo = serializers.SerializerMethodField()
    match_status = serializers.SerializerMethodField()
    score = serializers.SerializerMethodField()
    goal_scorers = serializers.SerializerMethodField()
    stadium = serializers.SerializerMethodField()
    team_wise_game_info = serializers.SerializerMethodField()
    team_wise_replacements = serializers.SerializerMethodField()

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
            "players",
            "video_url",
            "match_logo",
            "match_status",
            "score",
            "goal_scorers",
            "stadium",
            "team_wise_game_info",
            "team_wise_replacements",
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
        """Determine match status: Scheduled, Live, or Ended"""
        from django.utils import timezone
        from datetime import datetime, date, time as dt_time
        
        if not obj.match_date:
            return "Scheduled"
        
        today = timezone.now().date()
        match_date = obj.match_date
        
        # If match date is in the future, it's Scheduled
        if match_date > today:
            return "Scheduled"
        
        # If match date is today, check if it's live based on match_start_time and match_end_time
        if match_date == today:
            if obj.match_start_time and obj.match_end_time:
                try:
                    # Parse match times
                    start_time = datetime.strptime(obj.match_start_time, "%H:%M:%S").time()
                    end_time = datetime.strptime(obj.match_end_time, "%H:%M:%S").time()
                    current_time = timezone.now().time()
                    
                    # Check if current time is between start and end
                    if start_time <= current_time <= end_time:
                        return "Live"
                except (ValueError, AttributeError):
                    pass
            
            # If status is processed, it's likely ended
            if obj.status == "processed":
                return "Ended"
            
            # Default to Live if today and no clear end time
            return "Live"
        
        # If match date is in the past, it's Ended
        if match_date < today:
            return "Ended"
        
        # Default to Scheduled
        return "Scheduled"

    def get_score(self, obj):
        """Get match score when match is Ended"""
        match_status = self.get_match_status(obj)
        if match_status == "Ended":
            return {
                "home": obj.home_score if obj.home_score is not None else 0,
                "away": obj.away_score if obj.away_score is not None else 0,
            }
        return None

    def get_goal_scorers(self, obj):
        """Get goal scorers grouped by team with half information"""
        from tracevision.models import TraceVisionSessionStats
        
        # Get user language preference
        user_language = "en"
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        # Use prefetched highlights if available, otherwise query
        if hasattr(obj, "_prefetched_goal_highlights"):
            goal_highlights = obj._prefetched_goal_highlights
        else:
            # Get all goal highlights for this session
            goal_highlights = TraceHighlight.objects.filter(
                session=obj,
                event_type="goal"
            ).select_related("player", "player__team").order_by("half", "match_time")
        
        # Structure: {team_side: [goals], goal_counts: {home: {first_half: X, second_half: Y}, away: {...}}}
        home_goals = []
        away_goals = []
        home_first_half_count = 0
        home_second_half_count = 0
        away_first_half_count = 0
        away_second_half_count = 0
        
        for highlight in goal_highlights:
            if not highlight.player:
                continue
            
            # Get player name in user's language
            player_name = get_localized_name(highlight.player, user_language, "name")
            if not player_name:
                player_name = highlight.player.name or f"Player {highlight.player.jersey_number}"
            
            # Get goal minute
            goal_minute = highlight.match_time or highlight.event_metadata.get("minute", "")
            
            # Determine team side
            team_side = None
            if highlight.player.team == obj.home_team:
                team_side = "home"
            elif highlight.player.team == obj.away_team:
                team_side = "away"
            else:
                # Try to get from tags or event_metadata
                if "home" in (highlight.tags or []):
                    team_side = "home"
                elif "away" in (highlight.tags or []):
                    team_side = "away"
                elif highlight.event_metadata:
                    team_side = highlight.event_metadata.get("team", "").lower()
            
            if not team_side:
                continue
            
            # Determine half
            half = highlight.half or 1
            if highlight.match_time:
                try:
                    # Parse match_time (format: "MM:SS" or "MM")
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
            
            if team_side == "home":
                home_goals.append(goal_data)
                if half == 1:
                    home_first_half_count += 1
                else:
                    home_second_half_count += 1
            else:
                away_goals.append(goal_data)
                if half == 1:
                    away_first_half_count += 1
                else:
                    away_second_half_count += 1
        
        # Also check TraceVisionSessionStats for goal counts (more accurate)
        # Use prefetched session_stats if available
        try:
            if hasattr(obj, "session_stats") and obj.session_stats.exists():
                session_stats = obj.session_stats.first()
            else:
                from tracevision.models import TraceVisionSessionStats
                session_stats = TraceVisionSessionStats.objects.filter(session=obj).first()
            
            if session_stats:
                home_stats = session_stats.home_team_stats or {}
                away_stats = session_stats.away_team_stats or {}
                
                if home_stats.get("first_half_goals") is not None:
                    home_first_half_count = home_stats.get("first_half_goals", 0)
                    home_second_half_count = home_stats.get("second_half_goals", 0)
                
                if away_stats.get("first_half_goals") is not None:
                    away_first_half_count = away_stats.get("first_half_goals", 0)
                    away_second_half_count = away_stats.get("second_half_goals", 0)
        except Exception:
            pass
        
        return {
            "home": home_goals,
            "away": away_goals,
            "goal_counts": {
                "home": {
                    "first_half": home_first_half_count,
                    "second_half": home_second_half_count,
                    "total": home_first_half_count + home_second_half_count,
                },
                "away": {
                    "first_half": away_first_half_count,
                    "second_half": away_second_half_count,
                    "total": away_first_half_count + away_second_half_count,
                },
            },
        }

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

    def get_players(self, obj):
        """Get players from teams (home_team and away_team) - not filtered by session"""
        players_list = []

        # Use prefetched players if available (from view optimization)
        if hasattr(obj, "_prefetched_players"):
            players = obj._prefetched_players
        else:
            # Fallback: get all players from teams (not filtered by session)
            from tracevision.models import TracePlayer

            team_ids = []
            if obj.home_team:
                team_ids.append(obj.home_team.id)
            if obj.away_team:
                team_ids.append(obj.away_team.id)

            if team_ids:
                # Get all TracePlayers for these teams, regardless of session
                # Select related user to get profile picture for player_logo
                players = TracePlayer.objects.filter(
                    team_id__in=team_ids
                ).select_related("team", "user")
            else:
                players = TracePlayer.objects.none()

        # Serialize all players (filtered by team, not by session)
        for player in players:
            # Pass context to serializer so it can access request and user language preference
            # Also pass session so side can be determined correctly
            context = dict(self.context)
            context["session"] = obj
            serializer = HighlightDatePlayerSerializer(player, context=context)
            players_list.append(serializer.data)

        return players_list

    def get_team_wise_game_info(self, obj):
        """Get team-wise game information (goals, first half goals, etc.)"""
        from tracevision.models import TraceVisionSessionStats
        
        # Get user language preference
        user_language = "en"
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        # Try to get from session_stats first (most accurate)
        try:
            if hasattr(obj, "session_stats") and obj.session_stats.exists():
                session_stats = obj.session_stats.first()
            else:
                session_stats = TraceVisionSessionStats.objects.filter(session=obj).first()
            
            if session_stats:
                home_stats = session_stats.home_team_stats or {}
                away_stats = session_stats.away_team_stats or {}
                
                # Get starting_lineups and replacements from stats
                home_starting_lineups = home_stats.get("starting_lineups", {})
                away_starting_lineups = away_stats.get("starting_lineups", {})
                home_replacements = home_stats.get("replacements", {})
                away_replacements = away_stats.get("replacements", {})
                
                return {
                    "home": {
                        "total_goals": home_stats.get("total_goals", 0),
                        "first_half_goals": home_stats.get("first_half_goals", 0),
                        "second_half_goals": home_stats.get("second_half_goals", 0),
                        "starting_lineups": home_starting_lineups.get(user_language, home_starting_lineups.get("en", {})),
                    },
                    "away": {
                        "total_goals": away_stats.get("total_goals", 0),
                        "first_half_goals": away_stats.get("first_half_goals", 0),
                        "second_half_goals": away_stats.get("second_half_goals", 0),
                        "starting_lineups": away_starting_lineups.get(user_language, away_starting_lineups.get("en", {})),
                    }
                }
        except Exception as e:
            logger.warning(f"Error getting team_wise_game_info from session_stats: {e}")
        
        # Fallback: try to get from game.game_info
        try:
            if obj.game and obj.game.game_info:
                game_info = obj.game.game_info
                if user_language in game_info:
                    lang_info = game_info[user_language]
                    return {
                        "home": {
                            "total_goals": lang_info.get("home", {}).get("total_score", 0),
                            "first_half_goals": lang_info.get("home", {}).get("first_half_score", 0),
                            "second_half_goals": lang_info.get("home", {}).get("second_half_score", 0),
                            "starting_lineups": lang_info.get("home", {}).get("starting_lineups", {}),
                        },
                        "away": {
                            "total_goals": lang_info.get("away", {}).get("total_score", 0),
                            "first_half_goals": lang_info.get("away", {}).get("first_half_score", 0),
                            "second_half_goals": lang_info.get("away", {}).get("second_half_score", 0),
                            "starting_lineups": lang_info.get("away", {}).get("starting_lineups", {}),
                        }
                    }
        except Exception as e:
            logger.warning(f"Error getting team_wise_game_info from game_info: {e}")
        
        # Default fallback
        return {
            "home": {
                "total_goals": obj.home_score or 0,
                "first_half_goals": 0,
                "second_half_goals": 0,
                "starting_lineups": {},
            },
            "away": {
                "total_goals": obj.away_score or 0,
                "first_half_goals": 0,
                "second_half_goals": 0,
                "starting_lineups": {},
            }
        }

    def get_team_wise_replacements(self, obj):
        """Get team-wise replacements"""
        from tracevision.models import TraceVisionSessionStats
        
        # Get user language preference
        user_language = "en"
        request = self.context.get("request")
        if request and hasattr(request, "user"):
            user_language = getattr(request.user, "selected_language", "en") or "en"
        
        # Try to get from session_stats first
        try:
            if hasattr(obj, "session_stats") and obj.session_stats.exists():
                session_stats = obj.session_stats.first()
            else:
                session_stats = TraceVisionSessionStats.objects.filter(session=obj).first()
            
            if session_stats:
                home_stats = session_stats.home_team_stats or {}
                away_stats = session_stats.away_team_stats or {}
                
                home_replacements = home_stats.get("replacements", {})
                away_replacements = away_stats.get("replacements", {})
                
                return {
                    "home": home_replacements.get(user_language, home_replacements.get("en", {})),
                    "away": away_replacements.get(user_language, away_replacements.get("en", {})),
                }
        except Exception as e:
            logger.warning(f"Error getting team_wise_replacements from session_stats: {e}")
        
        # Fallback: try to get from game.game_info
        try:
            if obj.game and obj.game.game_info:
                game_info = obj.game.game_info
                if user_language in game_info:
                    lang_info = game_info[user_language]
                    return {
                        "home": lang_info.get("home", {}).get("replacements", {}),
                        "away": lang_info.get("away", {}).get("replacements", {}),
                    }
        except Exception as e:
            logger.warning(f"Error getting team_wise_replacements from game_info: {e}")
        
        # Default fallback
        return {
            "home": {},
            "away": {},
        }


class PlayerDetailSerializer(serializers.ModelSerializer):
    """Serializer for player details in highlights"""

    id = serializers.CharField(read_only=True)
    team_id = serializers.CharField(source="team.id", read_only=True)
    team_name = serializers.SerializerMethodField()

    def get_team_name(self, obj):
        user_language = "en"
        if self.context.get("request") and hasattr(self.context["request"], "user"):
            user_language = (
                getattr(self.context["request"].user, "selected_language", "en") or "en"
            )
        return get_localized_team_name(obj.team, user_language) if obj.team else None

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
    match_time = serializers.CharField(read_only=True, allow_null=True)
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
    primary_player = PlayerDetailSerializer(read_only=True)
    involved_players = PlayerDetailSerializer(many=True, read_only=True)
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

    def get_event_name(self, obj):
        """Generate event name from event type and match time"""
        time_str = obj.match_time or "Unknown time"
        return f"{obj.get_event_type_display()} at {time_str}"

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
        if obj.player and obj.player.team:
            session = obj.session
            side = None
            if session.home_team and session.home_team.id == obj.player.team.id:
                side = "home"
            elif session.away_team and session.away_team.id == obj.player.team.id:
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
        """Get all related clip reels as videos list"""
        # Order: default videos first (is_default=True), then by ratio, then by id
        clip_reels = obj.clip_reels.all().order_by("-is_default", "ratio", "id")
        return ClipReelVideoSerializer(clip_reels, many=True).data

    def get_label(self, obj):
        """Get label from default clip reel or generate from event_name"""
        # Try to get label from default clip reel first
        default_clip_reel = obj.clip_reels.filter(is_default=True).first()
        if default_clip_reel and default_clip_reel.label:
            return default_clip_reel.label

        # Fallback to event_name if no label in clip reel
        return self.get_event_name(obj)

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
