from django.db.models import Q
from rest_framework import serializers


from tracevision.models import TraceSession, TraceClipReel, TracePlayer
from tracevision.utils import get_hex_from_color_name


class TraceClipReelSerializer(serializers.ModelSerializer):
    age_group = serializers.CharField(
        source="session.age_group", read_only=True)
    match_date = serializers.DateField(
        source="session.match_date", read_only=True)

    class Meta:
        model = TraceClipReel
        fields = '__all__'
        extra_fields = ['age_group', 'match_date']


class TraceVisionProcessesSerializer(serializers.ModelSerializer):
    home_team_name = serializers.CharField(
        source='home_team.name', read_only=True)
    away_team_name = serializers.CharField(
        source='away_team.name', read_only=True)
    home_team_jersey_color = serializers.CharField(
        source='home_team.jersey_color', read_only=True)
    away_team_jersey_color = serializers.CharField(
        source='away_team.jersey_color', read_only=True)

    class Meta:
        model = TraceSession
        fields = '__all__'
        read_only_fields = ['id', 'user']


class TraceSessionListSerializer(serializers.ModelSerializer):
    """
    Serializer for TraceSession list view with essential information and filtering
    """
    home_team_name = serializers.CharField(
        source='home_team.name', read_only=True)
    away_team_name = serializers.CharField(
        source='away_team.name', read_only=True)
    home_team_jersey_color = serializers.CharField(
        source='home_team.jersey_color', read_only=True)
    away_team_jersey_color = serializers.CharField(
        source='away_team.jersey_color', read_only=True)
    pitch_dimensions = serializers.CharField(
        source='get_pitch_dimensions', read_only=True)

    # Filter fields
    match_date = serializers.DateField(
        required=False, help_text="Filter by exact match date (YYYY-MM-DD)")
    created_at = serializers.DateTimeField(
        required=False, help_text="Filter by creation date (YYYY-MM-DD HH:MM:SS)")
    status = serializers.ChoiceField(
        choices=['waiting_for_data', 'processing',
                 'processed', 'process_error'],
        required=False,
        # write_only=True,
        help_text="Filter by session status"
    )
    age_group = serializers.ChoiceField(
        choices=['U11_U12', 'U13_U14', 'U15_U16', 'U17_U18', 'SENIOR'],
        required=False,
        # write_only=True,
        help_text="Filter by age group"
    )
    team_name = serializers.CharField(
        max_length=100,
        required=False,
        # write_only=True,
        help_text="Filter by team name (searches both home and away teams)"
    )

    class Meta:
        model = TraceSession
        fields = [
            'id', 'session_id', 'status', 'user', 'match_date',
            'home_team_name', 'away_team_name', 'home_score', 'away_score',
            'home_team_jersey_color', 'away_team_jersey_color', 'age_group', 'pitch_size', 'pitch_dimensions',
            'final_score', 'start_time', 'video_url', 'created_at', 'updated_at',
            # Filter fields
            'match_date', 'created_at', 'status', 'age_group', 'team_name'
        ]
        read_only_fields = [
            'id', 'session_id', 'status', 'user', 'match_date', 'home_team', 'away_team',
            'home_team_name', 'away_team_name', 'home_score', 'away_score',
            'home_team_jersey_color', 'away_team_jersey_color', 'age_group', 'pitch_size', 'pitch_dimensions',
            'final_score', 'start_time', 'video_url', 'created_at', 'updated_at'
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
        if validated_data.get('created_at'):
            queryset = queryset.filter(
                created_at__date=validated_data['created_at'].date())

        # Status filter
        if validated_data.get('status'):
            queryset = queryset.filter(status=validated_data['status'])

        # Match date filter
        if validated_data.get('match_date'):
            queryset = queryset.filter(match_date=validated_data['match_date'])

        # Age group filter
        if validated_data.get('age_group'):
            queryset = queryset.filter(age_group=validated_data['age_group'])

        # Team name filter (searches both home_team and away_team)
        if validated_data.get('team_name'):
            queryset = queryset.filter(
                Q(home_team__name__icontains=validated_data['team_name']) |
                Q(away_team__name__icontains=validated_data['team_name'])
            )

        return queryset.order_by('-updated_at', '-created_at')


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
        help_text="URL to the video file (alternative to video_file upload)"
    )
    video_file = serializers.FileField(
        required=False,
        allow_empty_file=False,
        help_text="Video file to upload (alternative to video_link)"
    )

    # Team information
    home_team_name = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Name of the home team"
    )
    away_team_name = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Name of the away team"
    )
    home_team_jersey_color = serializers.CharField(
        max_length=7,
        required=True,
        help_text="Hex color code for home team jersey (e.g., #FF0000)"
    )
    away_team_jersey_color = serializers.CharField(
        max_length=7,
        required=True,
        help_text="Hex color code for away team jersey (e.g., #0000FF)"
    )
    final_score = serializers.CharField(
        required=True,
        help_text="Final score of the match in format 'home_score-away_score' (e.g., '2-1', '0-0'). Use '0-0' for no score."
    )
    start_time = serializers.DateTimeField(
        required=False,
        help_text="Start time of the video, if known (optional)"
    )
    match_start_time = serializers.CharField(
        required=False,
        help_text="Match start time in format 'HH:MM:SS' (optional)"
    )
    first_half_end_time = serializers.CharField(
        required=False,
        help_text="First half end time in format 'HH:MM:SS' (optional)"
    )
    second_half_start_time = serializers.CharField(
        required=False,
        help_text="Second half start time in format 'HH:MM:SS' (optional)"
    )
    match_end_time = serializers.CharField(
        required=False,
        help_text="Match end time in format 'HH:MM:SS' (optional)"
    )
    basic_game_stats = serializers.FileField(
        required=False,
        help_text="Basic game stats file (optional)"
    )

    # Age group and pitch size fields
    age_group = serializers.ChoiceField(
        choices=[
            ('U11_U12', 'U11-U12 (9v9)'),
            ('U13_U14', 'U13-U14 (11v11)'),
            ('U15_U16', 'U15-U16 (11v11)'),
            ('U17_U18', 'U17-U18 (11v11)'),
            ('SENIOR', 'Senior (18+)'),
        ],
        required=False,
        default='SENIOR',
        allow_blank=True,
        allow_null=True,
        help_text="Age group of the players (defaults to SENIOR if not provided)"
    )

    # Optional custom pitch size (if user wants to override default)
    pitch_length = serializers.FloatField(
        required=False,
        min_value=50,
        max_value=130,
        help_text="Custom pitch length in meters (optional, will use age group default if not provided)"
    )
    pitch_width = serializers.FloatField(
        required=False,
        min_value=30,
        max_value=100,
        help_text="Custom pitch width in meters (optional, will use age group default if not provided)"
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

        # Ensure team names are different
        if data['home_team_name'].lower() == data['away_team_name'].lower():
            raise serializers.ValidationError(
                "Home team and away team names must be different")

        # Ensure either video_link OR video_file is provided, but not both
        video_link = data.get('video_link')
        video_file = data.get('video_file')

        # Check if video_link is empty string and treat as None
        if video_link == "":
            video_link = None

        if not video_link and not video_file:
            raise serializers.ValidationError(
                "Either video_link or video_file must be provided")

        if video_link and video_file:
            raise serializers.ValidationError(
                "Cannot provide both video_link and video_file. Choose one option.")
        return data

    def validate_home_team_jersey_color(self, value):
        """Validate hex color format."""

        hex_color = get_hex_from_color_name(value)
        if not hex_color:
            raise serializers.ValidationError(
                f"Invalid color name: {value}"
            )

        if not hex_color.startswith('#') or len(hex_color) != 7:
            raise serializers.ValidationError(
                "Home team jersey color must be a valid hex color (e.g., #FF0000)")

        # Check if the hex value is valid
        try:
            int(hex_color[1:], 16)
        except ValueError:
            raise serializers.ValidationError(
                "Home team jersey color must be a valid hex color")

        return hex_color

    def validate_away_team_jersey_color(self, value):
        """Validate hex color format."""
        hex_color = get_hex_from_color_name(value)
        if not hex_color:
            raise serializers.ValidationError(
                f"Invalid color name: {value}"
            )

        if not hex_color.startswith('#') or len(hex_color) != 7:
            raise serializers.ValidationError(
                "Away team jersey color must be a valid hex color (e.g., #0000FF)")

        # Check if the hex value is valid
        try:
            int(hex_color[1:], 16)
        except ValueError:
            raise serializers.ValidationError(
                "Away team jersey color must be a valid hex color")

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

        if value.count('-') != 1:
            raise serializers.ValidationError(
                "Final score must be in format 'home_score-away_score' (e.g., '2-1', '0-0')"
            )

        # Split and validate both parts
        try:
            home_score_str, away_score_str = value.split('-')

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
                'Match_Summary': [],  # No specific columns required
                'Starting_Lineups': ['Team', 'Number', 'Name', 'Role', 'Goals', 'SubOffMinute', 'Cards'],
                'Replacements': ['Team', 'Number', 'Name', 'Role', 'Goals', 'ReplacerMinute'],
                'Bench': ['Team', 'Number', 'Name'],
                'Coaches': ['Team', 'Coach Name', 'Role'],
                'Referees': ['Position', 'Name']
            }

            errors = []

            # Check if all required tabs exist
            available_tabs = excel_file.sheet_names
            missing_tabs = []

            for tab_name in required_tabs.keys():
                if tab_name not in available_tabs:
                    missing_tabs.append(tab_name)

            if missing_tabs:
                errors.append(
                    f"Missing required tabs: {', '.join(missing_tabs)}")

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
                                f"Tab '{tab_name}' is missing required columns: {', '.join(missing_columns)}")

                    except Exception as e:
                        errors.append(
                            f"Error reading tab '{tab_name}': {str(e)}")

            # Check if file is empty or has no data
            if not available_tabs:
                errors.append(
                    "The Excel file appears to be empty or corrupted")

            # If there are any errors, raise validation error
            if errors:
                raise serializers.ValidationError(errors)

            return value

        except Exception as e:
            raise serializers.ValidationError(
                [f"Error reading CSV file: {str(e)}"])


class CoachViewSpecificTeamPlayersSerializer(serializers.ModelSerializer):
    class Meta:
        model = TracePlayer
        fields = '__all__'


class HighlightDatePlayerSerializer(serializers.ModelSerializer):
    """Serializer for player info in highlight dates response"""
    player_id = serializers.IntegerField(source='id', read_only=True)
    player_name = serializers.CharField(source='name', read_only=True)
    player_jersey_number = serializers.IntegerField(
        source='jersey_number', read_only=True)
    player_position = serializers.CharField(source='position', read_only=True)
    side = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()

    class Meta:
        model = TracePlayer
        fields = ['player_id', 'player_name', 'player_jersey_number',
                  'player_position', 'side', 'team']

    def get_side(self, obj):
        """Determine if player is on home or away team"""
        session = obj.session
        if session.home_team and obj.team and session.home_team.id == obj.team.id:
            return 'home'
        elif session.away_team and obj.team and session.away_team.id == obj.team.id:
            return 'away'
        return None

    def get_team(self, obj):
        """Get team information for the player"""
        if not obj.team:
            return {
                "team_id": None,
                "team_name": None,
                "side": self.get_side(obj)
            }

        return {
            "team_id": obj.team.id,
            "team_name": obj.team.name,
            "side": self.get_side(obj)
        }


class HighlightDateTeamSerializer(serializers.Serializer):
    """Serializer for team info in highlight dates response"""
    id = serializers.CharField(allow_null=True)
    name = serializers.CharField(allow_null=True)

    def to_representation(self, instance):
        """Handle None team instances"""
        if instance is None:
            return {"id": None, "name": None}
        return {
            "id": instance.id,
            "name": instance.name
        }


class HighlightDateSessionSerializer(serializers.ModelSerializer):
    """Serializer for session info in highlight dates response"""
    id = serializers.IntegerField(source='id', read_only=True)
    session_id = serializers.CharField(read_only=True)
    match_date = serializers.DateField(format='%Y-%m-%d', read_only=True)
    home_team = HighlightDateTeamSerializer(read_only=True)
    away_team = HighlightDateTeamSerializer(read_only=True)
    players = serializers.SerializerMethodField()

    class Meta:
        model = TraceSession
        fields = [
            'id', 'session_id', 'match_date', 'final_score', 'home_score', 'away_score',
            'home_team', 'away_team', 'age_group', 'match_start_time',
            'first_half_end_time', 'second_half_start_time', 'match_end_time',
            'players'
        ]
    
    def get_players(self, obj):
        """Get players from teams (home_team and away_team) - not filtered by session"""
        players_list = []
        
        # Use prefetched players if available (from view optimization)
        if hasattr(obj, '_prefetched_players'):
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
                ).select_related('team')
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
    team_id = serializers.CharField(source='team.id', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%fZ', read_only=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%fZ', read_only=True)

    class Meta:
        model = TracePlayer
        fields = [
            'id', 'name', 'jersey_number', 'position', 'object_id',
            'team_id', 'team_name', 'is_mapped', 'created_at', 'updated_at'
        ]


class MatchInfoSerializer(serializers.ModelSerializer):
    """Serializer for match information"""
    session_id = serializers.CharField(source='id', read_only=True)
    match_date = serializers.DateField(format='%Y-%m-%d', read_only=True)
    home_team = serializers.SerializerMethodField()
    away_team = serializers.SerializerMethodField()

    class Meta:
        model = TraceSession
        fields = [
            'session_id', 'match_date', 'final_score', 'home_score', 'away_score',
            'home_team', 'away_team', 'age_group', 'match_start_time',
            'first_half_end_time', 'second_half_start_time', 'match_end_time'
        ]

    def get_home_team(self, obj):
        if obj.home_team:
            return {
                "id": str(obj.home_team.id),
                "name": obj.home_team.name
            }
        return None

    def get_away_team(self, obj):
        if obj.away_team:
            return {
                "id": str(obj.away_team.id),
                "name": obj.away_team.name
            }
        return None


class HighlightClipReelSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for TraceClipReel highlights"""
    id = serializers.CharField(read_only=True)
    age_group = serializers.CharField(source='session.age_group', read_only=True)
    match_date = serializers.DateField(source='session.match_date', format='%Y-%m-%d', read_only=True)
    event_name = serializers.SerializerMethodField()
    start_clock = serializers.SerializerMethodField()
    end_clock = serializers.SerializerMethodField()
    primary_player = PlayerDetailSerializer(read_only=True)
    involved_players = PlayerDetailSerializer(many=True, read_only=True)
    session = serializers.CharField(source='session.id', read_only=True)
    highlight = serializers.CharField(source='highlight.id', read_only=True, allow_null=True)
    match_start_time = serializers.CharField(source='session.match_start_time', read_only=True)
    first_half_end_time = serializers.CharField(source='session.first_half_end_time', read_only=True)
    second_half_start_time = serializers.CharField(source='session.second_half_start_time', read_only=True)
    match_end_time = serializers.CharField(source='session.match_end_time', read_only=True)
    basic_game_stats = serializers.SerializerMethodField()
    half = serializers.IntegerField(source='highlight.half', read_only=True, allow_null=True)
    match_time = serializers.CharField(source='highlight.match_time', read_only=True, allow_null=True)
    generation_started_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%fZ', read_only=True, allow_null=True)
    generation_completed_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%fZ', read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%fZ', read_only=True, allow_null=True)
    updated_at = serializers.DateTimeField(format='%Y-%m-%dT%H:%M:%S.%fZ', read_only=True, allow_null=True)
    generation_errors = serializers.JSONField(default=list)
    generation_metadata = serializers.JSONField(default=dict)
    description = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = TraceClipReel
        fields = [
            'id', 'age_group', 'match_date', 'event_id', 'video_type',
            'video_variant_name', 'event_type', 'event_name', 'side',
            'start_ms', 'duration_ms', 'start_clock', 'end_clock',
            'generation_status', 'video_url', 'video_thumbnail_url',
            'video_size_mb', 'video_duration_seconds', 'generation_started_at',
            'generation_completed_at', 'generation_errors', 'generation_metadata',
            'resolution', 'frame_rate', 'bitrate', 'label', 'description',
            'tags', 'video_stream', 'created_at', 'updated_at', 'session',
            'highlight', 'primary_player', 'involved_players',
            'match_start_time', 'first_half_end_time', 'second_half_start_time',
            'match_end_time', 'basic_game_stats', 'half', 'match_time'
        ]

    def get_event_name(self, obj):
        """Get event name from highlight"""
        if obj.highlight:
            return obj.highlight.get_event_description()
        return obj.event_type.capitalize() if obj.event_type else None

    def get_start_clock(self, obj):
        """Convert start_ms to clock format"""
        from datetime import timedelta
        start_td = timedelta(milliseconds=obj.start_ms)
        return str(start_td)

    def get_end_clock(self, obj):
        """Convert end_ms to clock format"""
        from datetime import timedelta
        end_td = timedelta(milliseconds=obj.start_ms + obj.duration_ms)
        return str(end_td)

    def get_basic_game_stats(self, obj):
        """Get basic game stats URL"""
        if obj.session and obj.session.basic_game_stats:
            return obj.session.basic_game_stats.url
        return None

    def get_description(self, obj):
        """Get description or generate default"""
        if obj.description:
            return obj.description
        return f"{obj.event_type.capitalize()} event for {obj.side} team"

    def get_tags(self, obj):
        """Get tags or generate default"""
        if obj.tags:
            return obj.tags
        return [obj.side, obj.event_type] if obj.side and obj.event_type else []


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
        """Get team details"""
        if obj.get('team'):
            return {
                "id": str(obj['team'].id),
                "name": obj['team'].name
            }
        return None


class PossessionPlayerMetricsSerializer(serializers.Serializer):
    """Serializer for player possession metrics"""
    player = serializers.SerializerMethodField()
    involvement_count = serializers.IntegerField()
    total_duration_ms = serializers.IntegerField()
    total_touches = serializers.IntegerField()
    total_passes = serializers.IntegerField()
    possession_percentage = serializers.FloatField()

    def get_player(self, obj):
        """Get player details with team info"""
        player = obj.get('player')
        if not player:
            return None
        
        team = player.team
        side = None
        
        # Get session from context if available
        session = self.context.get('session')
        if session and team:
            if session.home_team and team.id == session.home_team.id:
                side = 'home'
            elif session.away_team and team.id == session.away_team.id:
                side = 'away'
        
        return {
            "id": str(player.id),
            "name": player.name,
            "jersey_number": player.jersey_number,
            "position": player.position,
            "object_id": player.object_id,
            "team_id": str(team.id) if team else None,
            "team_name": team.name if team else None,
            "side": side
        }
