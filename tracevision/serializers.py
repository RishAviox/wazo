import requests
from datetime import datetime
from django.conf import settings
from django.db.models import Q
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
)
from teams.models import Team
from tracevision.models import TraceSession
from tracevision.services import TraceVisionService
from games.models import GameUserRole
from tracevision.tasks import download_video_and_save_to_azure_blob


class TraceClipReelSerializer(serializers.ModelSerializer):
    age_group = serializers.CharField(source="session.age_group", read_only=True)
    match_date = serializers.DateField(source="session.match_date", read_only=True)

    class Meta:
        model = TraceClipReel
        fields = "__all__"
        extra_fields = ["age_group", "match_date"]


class TraceVisionProcessesSerializer(serializers.ModelSerializer):
    home_team_name = serializers.CharField(source="home_team.name", read_only=True)
    away_team_name = serializers.CharField(source="away_team.name", read_only=True)
    home_team_jersey_color = serializers.CharField(
        source="home_team.jersey_color", read_only=True
    )
    away_team_jersey_color = serializers.CharField(
        source="away_team.jersey_color", read_only=True
    )

    class Meta:
        model = TraceSession
        fields = "__all__"
        read_only_fields = ["id", "user"]


class TraceSessionListSerializer(serializers.ModelSerializer):
    """
    Serializer for TraceSession list view with essential information and filtering
    """

    home_team_name = serializers.CharField(source="home_team.name", read_only=True)
    away_team_name = serializers.CharField(source="away_team.name", read_only=True)
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
        
        # Check if user belongs to a team
        request = self.context.get('request')
        if request and request.user:
            user = request.user
            has_team = False
            
            # For coaches, check teams_coached relationship
            if user.role == 'Coach':
                has_team = user.teams_coached.exists()
            else:
                # For players and other roles, check team ForeignKey
                has_team = user.team is not None
            
            if not has_team:
                raise serializers.ValidationError({
                    "error": "Team required",
                    "message": "Please select your team in your profile to continue."
                })

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
        """
        if not value:
            return value

        import pandas as pd

        try:
            # Read the Excel file
            excel_file = pd.ExcelFile(value)

            # Define required tabs and their columns
            required_tabs = {
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

            # Check if all required tabs exist
            available_tabs = excel_file.sheet_names
            missing_tabs = []

            for tab_name in required_tabs.keys():
                if tab_name not in available_tabs:
                    missing_tabs.append(tab_name)

            if missing_tabs:
                errors.append(f"Missing required tabs: {', '.join(missing_tabs)}")

            # Check columns for each existing tab
            for tab_name, required_columns in required_tabs.items():
                if tab_name in available_tabs:
                    try:
                        df = pd.read_excel(value, sheet_name=tab_name)
                        actual_columns = df.columns.tolist()

                        # Check if all required columns exist
                        missing_columns = []
                        for col in required_columns:
                            if col not in actual_columns:
                                missing_columns.append(col)

                        if missing_columns:
                            errors.append(
                                f"Tab '{tab_name}' is missing required columns: {', '.join(missing_columns)}"
                            )

                    except Exception as e:
                        errors.append(f"Error reading tab '{tab_name}': {str(e)}")

            # Check if file is empty or has no data
            if not available_tabs:
                errors.append("The Excel file appears to be empty or corrupted")

            # If there are any errors, raise validation error
            if errors:
                raise serializers.ValidationError(errors)

            return value

        except Exception as e:
            raise serializers.ValidationError([f"Error reading CSV file: {str(e)}"])

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
        game_date = validated_data["game_date"]  # Required field
        game_time = validated_data.get("game_time")  # Optional field
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

        # Set pitch size (custom or default based on age group)
        if pitch_length and pitch_width:
            pitch_size = {"length": pitch_length, "width": pitch_width}
        else:
            pitch_size = TraceSession.DEFAULT_PITCH_SIZES.get(
                age_group, TraceSession.DEFAULT_PITCH_SIZES["SENIOR"]
            )

        # Parse the final score
        home_score, away_score = map(int, final_score_str.split("-"))

        # Generate team IDs and get or create teams
        home_team_id = "".join(c for c in home_team_name.upper() if c.isalnum())[:10]
        away_team_id = "".join(c for c in away_team_name.upper() if c.isalnum())[:10]

        home_team_obj, _ = Team.objects.get_or_create(
            id=home_team_id,
            defaults={"name": home_team_name, "jersey_color": home_color},
        )

        away_team_obj, _ = Team.objects.get_or_create(
            id=away_team_id,
            defaults={"name": away_team_name, "jersey_color": away_color},
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

        # Create TraceVision session
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
                "token": {
                    "customer_id": customer_id,
                    "token": api_key
                },
                "sessionData": {
                    "type": "soccer_game",
                    "game_info": {
                        "home_team": {
                            "name": home_team_name,
                            "score": home_score,
                            "color": home_color
                        },
                        "away_team": {
                            "name": away_team_name,
                            "score": away_score,
                            "color": away_color
                        }
                    },
                    "capabilities": ["tracking", "highlights"]
                }
            }
        }

        session_response = requests.post(
            graphql_url,
            headers={"Content-Type": "application/json"},
            json=session_payload
        )
        session_json = session_response.json()

        if session_response.status_code != 200 or not session_json.get("data", {}).get("createSession", {}).get("success"):
            raise ValidationError({
                "error": "TraceVision session creation failed",
                "details": session_json
            })

        session_id = session_json["data"]["createSession"]["session"]["session_id"]
        # session_id = "1234567890"

        # Check for duplicate by video_url BEFORE processing video
        video_url_for_db = None
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
            # video_url_for_db = TraceVisionService.import_game_video(
            #     session_id=session_id,
            #     video_link=video_link,
            #     start_time=start_time
            # )
            pass
        # TODO: Implement video upload functionality later
        # else:
        #     # Get upload URL first, then check duplicate
        #     upload_url = TraceVisionService.upload_game_video(
        #         session_id=session_id,
        #         video_file=video_file
        #     )
        #     video_url_for_db = upload_url

        #     # Check for duplicate by upload URL
        #     duplicate_session = check_duplicate_game(video_url=video_url_for_db)
        #     if duplicate_session:
        #         existing_game = duplicate_session.game
        #         raise ValidationError({
        #             "error": "Video already processed",
        #             "message": "This video has already been uploaded and processed.",
        #             "existing_session": {
        #                 "id": duplicate_session.id,
        #                 "session_id": duplicate_session.session_id,
        #                 "match_date": duplicate_session.match_date.isoformat(),
        #                 "home_team": duplicate_session.home_team.name if duplicate_session.home_team else None,
        #                 "away_team": duplicate_session.away_team.name if duplicate_session.away_team else None,
        #                 "status": duplicate_session.status
        #             },
        #             "existing_game": {
        #                 "id": existing_game.id if existing_game else None,
        #                 "type": existing_game.type if existing_game else None,
        #                 "name": existing_game.name if existing_game else None,
        #                 "date": existing_game.date.isoformat() if existing_game and existing_game.date else None
        #             } if existing_game else None
        #         })

        # Get or create canonical game
        canonical_game = get_or_create_canonical_game(
            home_team=home_team_obj,
            away_team=away_team_obj,
            match_date=match_date,
            game_type="match",
        )

        # Create TraceSession
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
        )

        # Create GameUserRole linking uploader to game
        GameUserRole.objects.get_or_create(game=canonical_game, user=user)

        # Trigger video download task
        # download_video_and_save_to_azure_blob.delay(session.id)

        return session


class CoachViewSpecificTeamPlayersSerializer(serializers.ModelSerializer):
    class Meta:
        model = TracePlayer
        fields = "__all__"


class HighlightDatePlayerSerializer(serializers.ModelSerializer):
    """Serializer for player info in highlight dates response"""

    player_id = serializers.IntegerField(source="id", read_only=True)
    player_name = serializers.CharField(source="name", read_only=True)
    player_jersey_number = serializers.IntegerField(
        source="jersey_number", read_only=True
    )
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
            "side",
            "team",
        ]

    def get_side(self, obj):
        """Determine if player is on home or away team, transformed by viewer perspective"""
        session = obj.session
        side = None
        if session.home_team and obj.team and session.home_team.id == obj.team.id:
            side = "home"
        elif session.away_team and obj.team and session.away_team.id == obj.team.id:
            side = "away"

        # Transform side based on viewer perspective
        viewer_team = get_viewer_team(
            self.context.get("request").user if self.context.get("request") else None
        )
        if viewer_team and side:
            viewer_perspective = determine_viewer_perspective(viewer_team, session)
            if viewer_perspective:
                side = transform_side_by_perspective(side, viewer_perspective)

        return side

    def get_team(self, obj):
        """Get team information for the player"""
        if not obj.team:
            return {"team_id": None, "team_name": None, "side": self.get_side(obj)}

        return {
            "team_id": obj.team.id,
            "team_name": obj.team.name,
            "side": self.get_side(obj),
        }


class HighlightDateTeamSerializer(serializers.Serializer):
    """Serializer for team info in highlight dates response"""

    id = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)

    def to_representation(self, instance):
        """Handle None team instances"""
        if instance is None:
            return {"id": None, "name": None}
        return {"id": instance.id, "name": instance.name}


class HighlightDateSessionSerializer(serializers.ModelSerializer):
    """Serializer for session info in highlight dates response"""

    id = serializers.IntegerField(read_only=True)
    session_id = serializers.CharField(read_only=True)
    match_date = serializers.DateField(format="%Y-%m-%d", read_only=True)
    home_team = HighlightDateTeamSerializer(read_only=True)
    away_team = HighlightDateTeamSerializer(read_only=True)
    players = serializers.SerializerMethodField()

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
        ]

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
                players = TracePlayer.objects.filter(
                    team_id__in=team_ids
                ).select_related("team")
            else:
                players = TracePlayer.objects.none()

        # Serialize all players (filtered by team, not by session)
        for player in players:
            serializer = HighlightDatePlayerSerializer(player)
            players_list.append(serializer.data)

        return players_list


class PlayerDetailSerializer(serializers.ModelSerializer):
    """Serializer for player details in highlights"""

    id = serializers.CharField(read_only=True)
    team_id = serializers.CharField(source="team.id", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
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
            team_data = {"id": str(obj.home_team.id), "name": obj.home_team.name}

            # Transform label based on viewer perspective
            request = self.context.get("request")
            if request and request.user:
                viewer_team = get_viewer_team(request.user)
                if viewer_team:
                    viewer_perspective = determine_viewer_perspective(viewer_team, obj)
                    if viewer_perspective == "home":
                        team_data["label"] = "team"
                    elif viewer_perspective == "away":
                        team_data["label"] = "opponent"

            return team_data
        return None

    def get_away_team(self, obj):
        """Get away team, transformed to 'team' or 'opponent' based on viewer"""
        if obj.away_team:
            team_data = {"id": str(obj.away_team.id), "name": obj.away_team.name}

            # Transform label based on viewer perspective
            request = self.context.get("request")
            if request and request.user:
                viewer_team = get_viewer_team(request.user)
                if viewer_team:
                    viewer_perspective = determine_viewer_perspective(viewer_team, obj)
                    if viewer_perspective == "away":
                        team_data["label"] = "team"
                    elif viewer_perspective == "home":
                        team_data["label"] = "opponent"

            return team_data
        return None


class ClipReelVideoSerializer(serializers.ModelSerializer):
    """Serializer for clip reel video information in highlight response"""
    url = serializers.URLField(source="video_url", read_only=True, allow_null=True)
    ratio = serializers.CharField(read_only=True)
    tags = serializers.JSONField(read_only=True)
    status = serializers.CharField(source="generation_status", read_only=True)
    default = serializers.BooleanField(source="is_default", read_only=True)
    
    class Meta:
        model = TraceClipReel
        fields = ["id", "url", "ratio", "tags", "status", "default"]


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
    # primary_player = PlayerDetailSerializer(read_only=True)
    # involved_players = PlayerDetailSerializer(many=True, read_only=True)
    # session = serializers.CharField(source="session.id", read_only=True)
    # match_start_time = serializers.CharField(
    #     source="session.match_start_time", read_only=True
    # )
    # first_half_end_time = serializers.CharField(
    #     source="session.first_half_end_time", read_only=True
    # )
    # second_half_start_time = serializers.CharField(
    #     source="session.second_half_start_time", read_only=True
    # )
    # match_end_time = serializers.CharField(
    #     source="session.match_end_time", read_only=True
    # )
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
    # label = serializers.CharField(read_only=True)
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
            "videos",
            "age_group",
            "match_date",
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
                                side = transform_side_by_perspective(side, viewer_perspective)
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
                            side = transform_side_by_perspective(side, viewer_perspective)
                return side
        
        return None
    
    def get_videos(self, obj):
        """Get all related clip reels as videos list"""
        # Order: default videos first (is_default=True), then by ratio, then by id
        clip_reels = obj.clip_reels.all().order_by('-is_default', 'ratio', 'id')
        return ClipReelVideoSerializer(clip_reels, many=True).data

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
            team_data = {"id": str(obj["team"].id), "name": obj["team"].name}

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

        return {
            "id": str(player.id),
            "name": player.name,
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
    """

    highlight_id = serializers.IntegerField(
        required=True,
        help_text="ID of the TraceHighlight to generate clip reel for",
    )
    tags = serializers.ListField(
        child=serializers.ChoiceField(
            choices=[
                "with_player_title",
                "without_player_title",
                "with_circle",
                "without_circle",
            ]
        ),
        required=True,
        min_length=1,
        help_text="List of overlay tags (e.g., ['with_player_title', 'without_circle'])",
    )
    ratio = serializers.ChoiceField(
        choices=[("original", "Original (Horizontal)"), ("9:16", "Vertical (9:16)")],
        required=True,
        help_text="Video aspect ratio - 'original' or '9:16'",
    )
    is_default = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether this should be the default video variation",
    )

    def validate_tags(self, value):
        """Ensure tags list is not empty and contains valid values."""
        if not value:
            raise serializers.ValidationError("Tags list cannot be empty")
        
        # Check for duplicates
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Tags list contains duplicate values")
        
        return value

    def validate(self, attrs):
        """Validate the entire data and reject any extra fields."""
        # Get the original data to check for extra fields
        if hasattr(self, 'initial_data'):
            allowed_fields = {'highlight_id', 'tags', 'ratio', 'is_default'}
            extra_fields = set(self.initial_data.keys()) - allowed_fields
            if extra_fields:
                raise serializers.ValidationError(
                    f"Unexpected fields: {', '.join(sorted(extra_fields))}. "
                    f"Allowed fields are: {', '.join(sorted(allowed_fields))}"
                )
        return attrs