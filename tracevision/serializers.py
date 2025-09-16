from rest_framework import serializers
from tracevision.models import TraceSession, TraceClipReel, TracePlayer
from tracevision.utils import get_hex_from_color_name

class TraceClipReelSerializer(serializers.ModelSerializer):
    age_group = serializers.CharField(source="session.age_group", read_only=True)
    match_date = serializers.DateField(source="session.match_date", read_only=True)
    class Meta:
        model = TraceClipReel
        fields = '__all__'
        extra_fields = ['age_group', 'match_date']


class TraceVisionProcessesSerializer(serializers.ModelSerializer):
    home_team_name = serializers.CharField(source='home_team.name', read_only=True)
    away_team_name = serializers.CharField(source='away_team.name', read_only=True)
    home_team_jersey_color = serializers.CharField(source='home_team.jersey_color', read_only=True)
    away_team_jersey_color = serializers.CharField(source='away_team.jersey_color', read_only=True)
    
    class Meta:
        model = TraceSession
        fields = '__all__'
        read_only_fields = ['id', 'user']


class TraceSessionListSerializer(serializers.ModelSerializer):
    """
    Serializer for TraceSession list view with essential information
    """
    home_team_name = serializers.CharField(source='home_team.name', read_only=True)
    away_team_name = serializers.CharField(source='away_team.name', read_only=True)
    home_team_jersey_color = serializers.CharField(source='home_team.jersey_color', read_only=True)
    away_team_jersey_color = serializers.CharField(source='away_team.jersey_color', read_only=True)
    pitch_dimensions = serializers.CharField(source='get_pitch_dimensions', read_only=True)
    
    class Meta:
        model = TraceSession
        fields = [
            'id', 'session_id', 'status', 'user', 'match_date', 'home_team', 'away_team',
            'home_team_name', 'away_team_name', 'home_score', 'away_score', 
            'home_team_jersey_color', 'away_team_jersey_color', 'age_group', 'pitch_size', 'pitch_dimensions',
            'final_score', 'start_time', 'video_url', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'session_id', 'status', 'user', 'match_date', 'home_team', 'away_team',
            'home_team_name', 'away_team_name', 'home_score', 'away_score', 
            'home_team_jersey_color', 'away_team_jersey_color', 'age_group', 'pitch_size', 'pitch_dimensions',
            'final_score', 'start_time', 'video_url', 'created_at', 'updated_at'
        ]


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

class CoachViewSpecificTeamPlayersSerializer(serializers.ModelSerializer):
    class Meta:
        model = TracePlayer
        fields = '__all__'