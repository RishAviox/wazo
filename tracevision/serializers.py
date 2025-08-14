from rest_framework import serializers
from tracevision.models import TraceSession
from tracevision.utils import get_hex_from_color_name


class TraceVisionProcessesSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraceSession
        fields = '__all__'
        read_only_fields = ['id', 'user']


class TraceSessionListSerializer(serializers.ModelSerializer):
    """
    Serializer for TraceSession list view with essential information
    """
    class Meta:
        model = TraceSession
        fields = ['id', 'session_id', 'status', 'user', 'created_at', 'updated_at']
        read_only_fields = ['id', 'session_id', 'status', 'user', 'created_at', 'updated_at']


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
    final_score = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="Final score of the match (optional)"
    )
    start_time = serializers.DateTimeField(
        required=False,
        help_text="Start time of the video, if known (optional)"
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

        return value

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

        return value

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
