from django.db import models
from teams.models import Team
from accounts.models import WajoUser
from games.models import Game


def get_default_pitch_size():
    """Return default SENIOR pitch size"""
    return {"length": 105, "width": 68}


class TraceSession(models.Model):
    # Age group choices with corresponding pitch sizes
    AGE_GROUP_CHOICES = [
        ("U11_U12", "U11-U12 (9v9)"),
        ("U13_U14", "U13-U14 (11v11)"),
        ("U15_U16", "U15-U16 (11v11)"),
        ("U17_U18", "U17-U18 (11v11)"),
        ("SENIOR", "Senior (18+)"),
    ]

    # Default pitch sizes for each age group
    DEFAULT_PITCH_SIZES = {
        "U11_U12": {"length": 73, "width": 46},
        "U13_U14": {"length": 82, "width": 50},
        "U15_U16": {"length": 91, "width": 55},
        "U17_U18": {"length": 100, "width": 64},
        "SENIOR": {"length": 105, "width": 68},  # Standard FIFA pitch size
    }

    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=250)
    match_date = models.DateField()

    # Canonical game relationship - One TraceSession per Game
    game = models.OneToOneField(
        Game,
        on_delete=models.CASCADE,
        related_name="trace_session",
        null=True,
        blank=True,
        help_text="Canonical game this session belongs to (OneToOne: one game = one session)",
    )

    home_score = models.PositiveSmallIntegerField()
    away_score = models.PositiveSmallIntegerField()

    home_team = models.ForeignKey(
        Team,
        on_delete=models.DO_NOTHING,
        related_name="home_team",
        blank=True,
        null=True,
    )
    away_team = models.ForeignKey(
        Team,
        on_delete=models.DO_NOTHING,
        related_name="away_team",
        blank=True,
        null=True,
    )

    # Age group field
    age_group = models.CharField(
        max_length=10,
        choices=AGE_GROUP_CHOICES,
        default="SENIOR",
        blank=True,
        null=True,
        help_text="Age group of the players in this session",
    )

    # Pitch size field (JSON to store length and width)
    pitch_size = models.JSONField(
        default=get_default_pitch_size,  # Default to SENIOR pitch size
        blank=True,
        null=True,
        help_text="Football field dimensions in meters: {'length': 105, 'width': 68}",
    )

    final_score = models.CharField(
        max_length=10,
        help_text="Final score in format 'home_score-away_score' (e.g., '2-1')",
    )
    start_time = models.DateTimeField(
        null=True, blank=True, help_text="Start time of the video, if known"
    )
    video_url = models.URLField()
    blob_video_url = models.URLField(
        blank=True, null=True, help_text="Azure blob URL for downloaded video file"
    )
    result = models.JSONField(default=dict)
    result_blob_url = models.URLField(
        blank=True, null=True, help_text="Azure blob URL for session result data JSON"
    )

    status = models.CharField(
        max_length=20,
        default="waiting_for_data",
        help_text="Status of the session processing",
    )

    match_start_time = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Match start time in format 'HH:MM:SS'",
    )
    first_half_end_time = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="First half end time in format 'HH:MM:SS'",
    )
    second_half_start_time = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Second half start time in format 'HH:MM:SS'",
    )
    match_end_time = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Match end time in format 'HH:MM:SS'",
    )
    basic_game_stats = models.FileField(
        upload_to="basic_game_stats/",
        null=True,
        blank=True,
        help_text="Basic game stats file",
    )

    # Timestamp fields
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the session was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="When the session was last updated"
    )

    class Meta:
        # Latest updated first, then latest created
        ordering = ["-updated_at", "-created_at"]
        # Unique constraints for canonical game enforcement
        constraints = [
            models.UniqueConstraint(
                fields=["video_url"],
                name="unique_video_url",
                condition=models.Q(video_url__isnull=False),
            ),
            models.UniqueConstraint(
                fields=["home_team", "away_team", "match_date"],
                name="unique_game_match",
            ),
        ]
        indexes = [
            models.Index(fields=["video_url"]),
            models.Index(fields=["home_team", "away_team", "match_date"]),
            models.Index(fields=["game"]),
        ]

    def save(self, *args, **kwargs):
        """Override save to set default SENIOR values for age_group and pitch_size if not provided"""
        # Set default age_group to SENIOR if not provided
        if not self.age_group:
            self.age_group = "SENIOR"

        # Set default pitch_size based on age_group if not provided
        if not self.pitch_size:
            self.pitch_size = self.DEFAULT_PITCH_SIZES.get(
                self.age_group, self.DEFAULT_PITCH_SIZES["SENIOR"]
            )

        super().save(*args, **kwargs)

    def get_pitch_dimensions(self):
        """Get pitch dimensions as a formatted string"""
        if self.pitch_size:
            length = self.pitch_size.get("length", 0)
            width = self.pitch_size.get("width", 0)
            return f"{length} × {width} m"
        else:
            # Return default SENIOR pitch size if pitch_size is None
            senior_size = self.DEFAULT_PITCH_SIZES["SENIOR"]
            return f"{senior_size['length']} × {senior_size['width']} m"

    def __str__(self):
        return f"{self.id} | {self.match_date} | {self.home_team} vs {self.away_team} | Status: {self.status}"


class TracePlayer(models.Model):
    id = models.AutoField(primary_key=True)
    object_id = models.CharField(
        max_length=100, help_text="Unique identifier from TraceVision API", null=True
    )
    name = models.CharField(max_length=100, help_text="Player's name")
    jersey_number = models.PositiveIntegerField(help_text="Player's jersey number")
    position = models.CharField(
        max_length=100, help_text="Player's position on the field"
    )

    # Relationships
    session = models.ForeignKey(
        to=TraceSession,
        on_delete=models.CASCADE,
        related_name="trace_players",
        help_text="TraceVision session this player belongs to",
    )
    user = models.ForeignKey(
        WajoUser,
        on_delete=models.DO_NOTHING,
        related_name="trace_players",
        null=True,
        blank=True,
        help_text="User who owns this player data (optional for unmapped players)",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="trace_players",
        help_text="Team this player belongs to",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        verbose_name = "Trace Player"
        verbose_name_plural = "Trace Players"
        # Unique constraint: object_id + user (when user is present)
        constraints = [
            models.UniqueConstraint(
                fields=["object_id", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_object_id_per_user",
            ),
            # Ensure object_id is unique per session
            models.UniqueConstraint(
                fields=["object_id", "session"], name="unique_object_id_per_session"
            ),
        ]
        indexes = [
            models.Index(fields=["object_id"]),
            models.Index(fields=["user"]),
            models.Index(fields=["team"]),
            models.Index(fields=["session"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.jersey_number}) - {self.team.name if self.team else 'No Team'}"

    @property
    def is_mapped(self):
        """Check if this player is mapped to a user"""
        return self.user is not None

    @property
    def team_name(self):
        """Get team name for display"""
        return self.team.name if self.team else "Unknown Team"


class TraceHighlight(models.Model):
    # Event type choices for different match events
    EVENT_TYPE_CHOICES = [
        ("touch", "Touch"),
        ("touch-chain", "Touch Chain"),
        ("goal", "Goal"),
        ("yellow_card", "Yellow Card"),
        ("red_card", "Red Card"),
        ("substitution", "Substitution"),
        ("save", "Save"),
        ("shot", "Shot"),
        ("pass", "Pass"),
        ("tackle", "Tackle"),
        ("foul", "Foul"),
        ("offside", "Offside"),
        ("corner", "Corner"),
        ("free_kick", "Free Kick"),
        ("penalty", "Penalty"),
        ("other", "Other"),
    ]

    # Source choices for highlight origin
    SOURCE_CHOICES = [
        ("tracevision", "TraceVision API"),
        ("excel_import", "Excel Import"),
        ("manual", "Manual Entry"),
        ("ai_detection", "AI Detection"),
    ]

    id = models.AutoField(primary_key=True)
    highlight_id = models.CharField(
        max_length=100, unique=True, help_text="Unique identifier for the highlight"
    )
    video_id = models.PositiveIntegerField(
        help_text="Video ID associated with the highlight"
    )
    start_offset = models.PositiveIntegerField(help_text="Start offset in milliseconds")
    duration = models.PositiveIntegerField(
        help_text="Duration of the highlight in milliseconds"
    )
    tags = models.JSONField(
        default=list, help_text="Tags associated with the highlight"
    )
    video_stream = models.URLField(help_text="URL to the video stream")

    # New fields for enhanced event tracking
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default="touch",
        help_text="Type of event this highlight represents",
    )
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default="tracevision",
        help_text="Source of this highlight data",
    )
    match_time = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        help_text="Match time when event occurred in MM:SS format (e.g., '16:30', '77:15')",
    )
    half = models.PositiveIntegerField(
        null=True, blank=True, help_text="Match half (1 or 2) when event occurred"
    )

    # Event-specific metadata
    event_metadata = models.JSONField(
        default=dict,
        help_text="Additional event-specific data (scorer, card type, etc.)",
    )

    # Player performance impact
    performance_impact = models.FloatField(
        default=0.0, help_text="Impact score on player performance (0-100)"
    )
    team_impact = models.FloatField(
        default=0.0, help_text="Impact score on team performance (0-100)"
    )

    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="highlights"
    )
    player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="highlights",
        blank=True,
        null=True,
        help_text="Player involved in this highlight (optional)",
    )

    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["highlight_id"]),
            models.Index(fields=["session", "start_offset"]),
            models.Index(fields=["player", "-created_at"]),
            models.Index(fields=["event_type", "session"]),
            models.Index(fields=["source", "session"]),
            models.Index(fields=["match_time", "session"]),
            models.Index(fields=["performance_impact", "session"]),
        ]

    def __str__(self):
        return f"Highlight {self.highlight_id} - {self.event_type} - {self.duration}ms"

    @property
    def is_goal(self):
        """Check if this highlight represents a goal"""
        return self.event_type == "goal"

    @property
    def is_card(self):
        """Check if this highlight represents a card event"""
        return self.event_type in ["yellow_card", "red_card"]

    @property
    def is_positive_event(self):
        """Check if this is a positive event for the player's team"""
        return self.event_type in ["goal", "save", "tackle", "pass"]

    @property
    def is_negative_event(self):
        """Check if this is a negative event for the player's team"""
        return self.event_type in ["red_card", "yellow_card", "foul", "offside"]

    def get_event_description(self):
        """Get a human-readable description of the event"""
        time_str = self.match_time or "Unknown time"
        if self.event_type == "goal":
            scorer = self.event_metadata.get("scorer", "Unknown")
            return f"Goal by {scorer} at {time_str}"
        elif self.event_type in ["yellow_card", "red_card"]:
            player = self.event_metadata.get("player", "Unknown")
            card_type = "Yellow" if self.event_type == "yellow_card" else "Red"
            return f"{card_type} card for {player} at {time_str}"
        else:
            return f"{self.get_event_type_display()} at {time_str}"

    @property
    def minute(self):
        """Get minute from match_time (for backward compatibility)"""
        if self.match_time:
            try:
                return int(self.match_time.split(":")[0])
            except (ValueError, IndexError):
                return None
        return None

    @property
    def second(self):
        """Get second from match_time (for backward compatibility)"""
        if self.match_time:
            try:
                return int(self.match_time.split(":")[1])
            except (ValueError, IndexError):
                return None
        return None

    def set_match_time(self, minute, second=0):
        """Set match_time from minute and second values"""
        if minute is not None:
            self.match_time = f"{minute:02d}:{second:02d}"
        else:
            self.match_time = None

    def get_total_seconds(self):
        """Get total seconds from start of match"""
        if self.match_time:
            try:
                parts = self.match_time.split(":")
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
            except (ValueError, IndexError):
                return None
        return None

    def calculate_performance_impact(self):
        """Calculate performance impact based on event type and metadata"""
        base_impact = 0.0

        if self.event_type == "goal":
            base_impact = 25.0  # High positive impact
        elif self.event_type == "red_card":
            base_impact = -20.0  # High negative impact
        elif self.event_type == "yellow_card":
            base_impact = -5.0  # Low negative impact
        elif self.event_type == "save":
            base_impact = 15.0  # High positive impact for goalkeeper
        elif self.event_type == "tackle":
            base_impact = 8.0  # Positive impact for defensive action
        elif self.event_type == "pass":
            base_impact = 3.0  # Low positive impact

        # Adjust based on match context (minute, half, etc.)
        minute = self.minute
        if minute:
            if minute <= 15:  # Early in half
                base_impact *= 0.8
            elif minute >= 75:  # Late in half
                base_impact *= 1.2

        return max(-50.0, min(50.0, base_impact))  # Clamp between -50 and 50


class TraceObject(models.Model):
    """
    Model to store object data from the TraceVision API
    """

    id = models.AutoField(primary_key=True)
    object_id = models.CharField(
        max_length=120, help_text="Unique identifier for the object"
    )
    type = models.CharField(max_length=100, help_text="Type of the object")
    side = models.CharField(max_length=100, help_text="Side/team the object belongs to")
    appearance_fv = models.JSONField(
        null=True, blank=True, help_text="Appearance feature vector"
    )
    color_fv = models.JSONField(null=True, blank=True, help_text="Color feature vector")
    tracking_url = models.URLField(
        max_length=500, help_text="URL to fetch tracking data"
    )
    tracking_blob_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Azure blob URL for downloaded tracking data",
    )
    role = models.CharField(
        max_length=50, null=True, blank=True, help_text="Role of the object"
    )

    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="trace_objects"
    )
    player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="trace_objects",
        blank=True,
        null=True,
        help_text="Player this object belongs to (optional)",
    )

    # Status tracking for downloads
    tracking_processed = models.BooleanField(
        default=False, help_text="Whether tracking data has been processed"
    )

    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["object_id"]
        indexes = [
            models.Index(fields=["object_id"]),
            models.Index(fields=["session", "type"]),
            models.Index(fields=["session", "side"]),
            models.Index(fields=["player", "type"]),
        ]
        unique_together = ["object_id", "session"]

    def __str__(self):
        return f"{self.object_id} ({self.type}) - {self.side}"


class TraceHighlightObject(models.Model):
    """
    Many-to-many relationship between highlights and objects
    """

    id = models.AutoField(primary_key=True)
    highlight = models.ForeignKey(
        TraceHighlight, on_delete=models.CASCADE, related_name="highlight_objects"
    )
    trace_object = models.ForeignKey(
        TraceObject, on_delete=models.CASCADE, related_name="object_highlights"
    )
    player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="highlight_objects",
        blank=True,
        null=True,
        help_text="Player involved in this highlight-object relationship (optional)",
    )

    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["highlight", "trace_object"]
        indexes = [
            models.Index(fields=["highlight"]),
            models.Index(fields=["trace_object"]),
            models.Index(fields=["player"]),
        ]

    def __str__(self):
        return f"{self.highlight.highlight_id} - {self.trace_object.object_id}"


class TraceVisionPlayerStats(models.Model):
    """
    Calculated performance statistics for individual players in a session
    Generated from tracking data and highlights analysis
    """

    id = models.AutoField(primary_key=True)

    session = models.ForeignKey(
        TraceSession,
        on_delete=models.CASCADE,
        related_name="session_player_stats",
        null=True,
        blank=True,
    )
    player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="player_stats",
        help_text="Player this statistics belong to",
        null=True,
        blank=True,
    )

    side = models.CharField(max_length=10, help_text="home or away team")

    # Movement and physical stats
    total_distance_meters = models.FloatField(
        default=0.0, help_text="Total distance covered in meters"
    )
    avg_speed_mps = models.FloatField(
        default=0.0, help_text="Average speed in meters per second"
    )
    max_speed_mps = models.FloatField(default=0.0, help_text="Maximum speed reached")
    total_time_seconds = models.FloatField(
        default=0.0, help_text="Total time tracked in seconds"
    )

    # Sprint analysis
    sprint_count = models.PositiveIntegerField(
        default=0, help_text="Number of sprints detected"
    )
    sprint_distance_meters = models.FloatField(
        default=0.0, help_text="Total distance covered in sprints"
    )
    sprint_time_seconds = models.FloatField(
        default=0.0, help_text="Total time spent sprinting"
    )

    # Position and tactical stats
    avg_position_x = models.FloatField(
        default=0.0, help_text="Average X position (0-1000 scale)"
    )
    avg_position_y = models.FloatField(
        default=0.0, help_text="Average Y position (0-1000 scale)"
    )
    position_variance = models.FloatField(
        default=0.0, help_text="Position variance (movement range)"
    )

    # Heatmap data (stored as JSON for flexibility)
    heatmap_data = models.JSONField(
        default=dict, help_text="Heatmap grid data for visualization"
    )

    # Performance metrics
    performance_score = models.FloatField(
        default=0.0, help_text="Overall performance score 0-100"
    )
    stamina_rating = models.FloatField(
        default=0.0, help_text="Stamina rating based on movement patterns"
    )
    work_rate = models.FloatField(
        default=0.0, help_text="Work rate based on distance and speed"
    )

    # Calculation metadata
    calculation_method = models.CharField(
        max_length=100, default="standard", help_text="Method used for calculations"
    )
    calculation_version = models.CharField(
        max_length=20, default="1.0", help_text="Calculation algorithm version"
    )
    last_calculated = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # unique_together = ['session', 'player']
        indexes = [
            models.Index(fields=["session", "player"]),
            models.Index(fields=["side", "performance_score"]),
            models.Index(fields=["performance_score", "last_calculated"]),
        ]
        verbose_name = "TraceVision Player Stats"
        verbose_name_plural = "TraceVision Player Stats"

    def __str__(self):
        return f"{self.player.name} - {self.session.session_id} - Score: {self.performance_score}"

    @property
    def distance_per_minute(self):
        """Calculate distance covered per minute"""
        if self.total_time_seconds > 0:
            return (self.total_distance_meters / self.total_time_seconds) * 60
        return 0.0

    @property
    def sprint_percentage(self):
        """Calculate percentage of time spent sprinting"""
        if self.total_time_seconds > 0:
            return (self.sprint_time_seconds / self.total_time_seconds) * 100
        return 0.0


class TraceVisionSessionStats(models.Model):
    """
    Aggregated statistics for entire session (team-level insights)
    """

    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="session_stats"
    )

    # Team performance metrics
    home_team_stats = models.JSONField(
        default=dict, help_text="Home team aggregated stats"
    )
    away_team_stats = models.JSONField(
        default=dict, help_text="Away team aggregated stats"
    )

    # Match analysis
    possession_data = models.JSONField(
        default=dict, help_text="Possession percentages and patterns"
    )
    tactical_analysis = models.JSONField(
        default=dict, help_text="Formation and tactical insights"
    )

    # Data quality metrics
    total_tracking_points = models.PositiveIntegerField(
        default=0, help_text="Total tracking data points"
    )
    data_coverage_percentage = models.FloatField(
        default=0.0, help_text="Percentage of video with tracking data"
    )
    quality_score = models.FloatField(
        default=0.0, help_text="Overall data quality score"
    )

    # Processing metadata
    processing_status = models.CharField(
        max_length=20, default="pending", help_text="Stats processing status"
    )
    processing_errors = models.JSONField(
        default=list, help_text="Any errors during processing"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["session"]
        indexes = [
            models.Index(fields=["session"]),
            models.Index(fields=["processing_status", "created_at"]),
        ]
        verbose_name = "TraceVision Session Stats"
        verbose_name_plural = "TraceVision Session Stats"

    def __str__(self):
        return f"Session Stats - {self.session.session_id} - Quality: {self.quality_score}%"


class TraceCoachReportTeam(models.Model):
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="coach_report_team"
    )
    side = models.CharField(max_length=10)
    goals = models.IntegerField(default=0)
    shots = models.IntegerField(default=0)
    passes = models.IntegerField(default=0)
    possession_time_s = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["session", "side"]
        indexes = [
            models.Index(fields=["session", "side"]),
        ]
        verbose_name = "Coach Report Team"
        verbose_name_plural = "Coach Report Team"


class TraceTouchLeaderboard(models.Model):
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="touch_leaderboard"
    )
    player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="touch_leaderboard",
        help_text="Player this touch count belongs to",
        blank=True,
        null=True,
    )
    object_side = models.CharField(max_length=10)
    touches = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["session"]),
            models.Index(fields=["object_side", "touches"]),
        ]
        verbose_name = "Touch Leaderboard Entry"
        verbose_name_plural = "Touch Leaderboard Entries"


class TracePossessionSegment(models.Model):
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="possession_segments"
    )
    side = models.CharField(max_length=10)
    start_ms = models.IntegerField()
    end_ms = models.IntegerField()
    count = models.IntegerField(default=0)
    start_clock = models.CharField(max_length=20, blank=True)
    end_clock = models.CharField(max_length=20, blank=True)
    duration_s = models.FloatField(default=0.0)

    # NEW FIELDS FOR POSSESSION SEGMENTS
    highlight = models.ForeignKey(
        TraceHighlight,
        on_delete=models.CASCADE,
        related_name="possession_segments",
        null=True,
        blank=True,
    )

    # Team metrics for this segment (cumulative up to this point)
    team_metrics = models.JSONField(
        default=dict,
        help_text="Cumulative team possession metrics up to this highlight",
    )

    # Player metrics for this segment
    player_metrics = models.JSONField(
        default=dict, help_text="Player involvement metrics for this highlight"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["session", "side"]),
            models.Index(fields=["session", "start_ms"]),
            models.Index(fields=["highlight"]),
        ]
        verbose_name = "Possession Segment"
        verbose_name_plural = "Possession Segments"


class TraceClipReel(models.Model):
    """
    Model to store clip reel information for TraceVision highlights.
    Each highlight can generate multiple video variations (with/without overlay, zoomed, etc.)
    """

    # Video variation types
    VIDEO_TYPE_CHOICES = [
        ("original", "Original (No Overlay)"),
        ("with_overlay", "With Overlay"),
        ("zoomed_player", "Zoomed on Player"),
        ("zoomed_team", "Zoomed on Team"),
        ("tactical_view", "Tactical View"),
        ("slow_motion", "Slow Motion"),
        ("multi_angle", "Multi-Angle"),
    ]

    # Generation status choices
    GENERATION_STATUS_CHOICES = [
        ("pending", "Pending Generation"),
        ("generating", "Currently Generating"),
        ("completed", "Generation Completed"),
        ("failed", "Generation Failed"),
        ("skipped", "Skipped"),
    ]

    id = models.AutoField(primary_key=True)

    # Core highlight information
    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="clip_reels"
    )

    highlight = models.ForeignKey(
        "TraceHighlight",
        on_delete=models.CASCADE,
        related_name="clip_reels",
        help_text="The highlight this clip reel is based on",
    )

    event_id = models.CharField(max_length=100, help_text="Unique event identifier")

    # Video variation details
    video_type = models.CharField(
        max_length=20,
        choices=VIDEO_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text="Type of video variation (deprecated - use tags and ratio instead)",
    )
    video_variant_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom name for this video variant (e.g., 'Player Focus', 'Team View')",
    )

    # Highlight metadata
    event_type = models.CharField(
        max_length=50, help_text="Type of event (touch, pass, etc.)"
    )
    side = models.CharField(max_length=10, help_text="Team side (home/away)")
    start_ms = models.IntegerField(help_text="Start time in milliseconds")
    duration_ms = models.IntegerField(help_text="Duration in milliseconds")
    start_clock = models.CharField(
        max_length=20, blank=True, help_text="Start time in clock format"
    )
    end_clock = models.CharField(
        max_length=20, blank=True, help_text="End time in clock format"
    )

    # Player and team information
    primary_player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="primary_clip_reels",
        blank=True,
        null=True,
        help_text="Primary player involved in this clip",
    )
    involved_players = models.ManyToManyField(
        TracePlayer,
        related_name="involved_clip_reels",
        blank=True,
        help_text="All players involved in this highlight",
    )

    # Video generation and storage
    generation_status = models.CharField(
        max_length=20,
        choices=GENERATION_STATUS_CHOICES,
        default="pending",
        help_text="Status of video generation",
    )
    video_url = models.URLField(
        blank=True, help_text="Azure blob URL for the generated video"
    )
    video_thumbnail_url = models.URLField(
        blank=True, help_text="Azure blob URL for video thumbnail"
    )
    video_size_mb = models.FloatField(default=0.0, help_text="Video file size in MB")
    video_duration_seconds = models.FloatField(
        default=0.0, help_text="Actual video duration in seconds"
    )

    # Generation metadata
    generation_started_at = models.DateTimeField(
        null=True, blank=True, help_text="When video generation started"
    )
    generation_completed_at = models.DateTimeField(
        null=True, blank=True, help_text="When video generation completed"
    )
    generation_errors = models.JSONField(
        default=list, null=True, blank=True, help_text="Any errors during generation"
    )
    generation_metadata = models.JSONField(
        default=dict, null=True, blank=True, help_text="Additional generation parameters and settings"
    )

    # Video quality and settings
    resolution = models.CharField(
        max_length=20, default="1080p", help_text="Video resolution"
    )
    frame_rate = models.IntegerField(default=30, help_text="Video frame rate (FPS)")
    bitrate = models.IntegerField(default=0, help_text="Video bitrate (kbps)")

    # Video aspect ratio
    RATIO_CHOICES = [
        ("original", "Original (Horizontal)"),
        ("9:16", "Vertical (9:16)"),
    ]
    ratio = models.CharField(
        max_length=20,
        choices=RATIO_CHOICES,
        default="original",
        help_text="Video aspect ratio (original/horizontal or 9:16/vertical)",
    )

    # Content and tags
    label = models.CharField(
        max_length=100, blank=True, help_text="Display label for the clip"
    )
    description = models.TextField(
        blank=True, help_text="Detailed description of the clip"
    )
    tags = models.JSONField(
        default=list,
        help_text="Tags for overlay options: with_player_title, without_player_title, with_circle, without_circle",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default video variation for the highlight",
    )

    # Legacy field for backward compatibility
    video_stream = models.URLField(blank=True, help_text="Legacy video stream URL")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["session", "side"]),
            models.Index(fields=["session", "event_id"]),
            models.Index(fields=["session", "primary_player"]),
            models.Index(fields=["highlight", "video_type"]),
            models.Index(fields=["generation_status", "created_at"]),
            models.Index(fields=["video_type", "generation_status"]),
        ]
        # Allow multiple clip reels per highlight with different video types
        # unique_together = ['highlight', 'video_type']
        verbose_name = "Clip Reel Item"
        verbose_name_plural = "Clip Reel Items"

    def __str__(self):
        return f"{self.highlight.highlight_id} - {self.get_video_type_display()} ({self.generation_status})"

    @property
    def is_generated(self):
        """Check if video has been successfully generated"""
        return self.generation_status == "completed" and bool(self.video_url)

    @property
    def generation_duration(self):
        """Calculate how long generation took"""
        if self.generation_started_at and self.generation_completed_at:
            return self.generation_completed_at - self.generation_started_at
        return None

    def mark_generation_started(self):
        """Mark video generation as started"""
        from django.utils import timezone

        self.generation_status = "generating"
        self.generation_started_at = timezone.now()
        self.save(update_fields=["generation_status", "generation_started_at"])

    def mark_generation_completed(
        self, video_url, video_size_mb=0.0, video_duration_seconds=0.0, thumbnail_url=""
    ):
        """Mark video generation as completed"""
        from django.utils import timezone

        self.generation_status = "completed"
        self.generation_completed_at = timezone.now()
        self.video_url = video_url
        self.video_size_mb = video_size_mb
        self.video_duration_seconds = video_duration_seconds
        if thumbnail_url:
            self.video_thumbnail_url = thumbnail_url
        self.save(
            update_fields=[
                "generation_status",
                "generation_completed_at",
                "video_url",
                "video_size_mb",
                "video_duration_seconds",
                "video_thumbnail_url",
            ]
        )

    def mark_generation_failed(self, error_message):
        """Mark video generation as failed"""
        from django.utils import timezone

        self.generation_status = "failed"
        self.generation_completed_at = timezone.now()
        if not self.generation_errors:
            self.generation_errors = []
        self.generation_errors.append(
            {"timestamp": timezone.now().isoformat(), "error": error_message}
        )
        self.save(
            update_fields=[
                "generation_status",
                "generation_completed_at",
                "generation_errors",
            ]
        )

    def get_tracking_data_for_players(self):
        """
        Get tracking data for all involved players in this clip reel.

        Returns:
            dict: Dictionary mapping object_id to tracking data from TraceObject.tracking_blob_url
        """
        tracking_data = {}

        for player in self.involved_players.all():
            # Get TraceObject for this player in this session
            trace_object = TraceObject.objects.filter(
                session=self.session, player=player
            ).first()

            if trace_object and trace_object.tracking_blob_url:
                tracking_data[player.object_id] = {
                    "trace_object": trace_object,
                    "tracking_blob_url": trace_object.tracking_blob_url,
                    "player": player,
                }

        return tracking_data

    def get_video_file_url(self):
        """
        Get the video file URL for this clip reel's session.
        Prefers blob_video_url (downloaded) over video_url (original).

        Returns:
            str: Video file URL or None if not available
        """
        session = self.session
        return session.blob_video_url or session.video_url

    def can_generate_overlay(self):
        """
        Check if this clip reel can generate an overlay video.

        Returns:
            bool: True if all required data is available
        """
        # Check if video file is available
        if not self.get_video_file_url():
            return False

        # Check if we have involved players with tracking data
        tracking_data = self.get_tracking_data_for_players()
        if not tracking_data:
            return False

        # Check if generation status allows processing
        if self.generation_status not in ["pending", "failed"]:
            return False

        return True

    def get_generation_summary(self):
        """
        Get a summary of the generation status and metadata.

        Returns:
            dict: Summary information about the clip reel generation
        """
        return {
            "clip_reel_id": str(self.id),
            "highlight_id": self.highlight.highlight_id,
            "video_type": self.video_type,
            "video_variant_name": self.video_variant_name,
            "generation_status": self.generation_status,
            "is_generated": self.is_generated,
            "video_url": self.video_url,
            "video_size_mb": self.video_size_mb,
            "video_duration_seconds": self.video_duration_seconds,
            "generation_duration": self.generation_duration,
            "involved_players_count": self.involved_players.count(),
            "can_generate_overlay": self.can_generate_overlay(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class TracePass(models.Model):
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="passes"
    )
    side = models.CharField(max_length=10)
    from_player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="passes_made",
        help_text="Player who made the pass",
        blank=True,
        null=True,
    )
    to_player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="passes_received",
        help_text="Player who received the pass",
        blank=True,
        null=True,
    )
    start_ms = models.IntegerField()
    duration_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["session", "side"]),
            models.Index(fields=["session", "from_player", "to_player"]),
        ]
        verbose_name = "Pass"
        verbose_name_plural = "Passes"


class TracePassingNetwork(models.Model):
    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="passing_network"
    )
    side = models.CharField(max_length=10)
    from_player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="passing_network_from",
        help_text="Player who made the passes",
        blank=True,
        null=True,
    )
    to_player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="passing_network_to",
        help_text="Player who received the passes",
        blank=True,
        null=True,
    )
    passes_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["session", "side"]),
            models.Index(fields=["passes_count"]),
        ]
        verbose_name = "Passing Network Edge"
        verbose_name_plural = "Passing Network Edges"


class TracePossessionStats(models.Model):
    """
    Unified model to store possession statistics for both teams and players.
    Uses 'type' field to distinguish between team and player stats.
    All metrics are stored in a single JSON field for maximum flexibility.
    For a game: 1 row per team + 1 row per player = multiple rows per session.
    """

    POSSESSION_TYPE_CHOICES = [
        ("team", "Team"),
        ("player", "Player"),
    ]

    id = models.AutoField(primary_key=True)
    session = models.ForeignKey(
        TraceSession, on_delete=models.CASCADE, related_name="possession_stats"
    )
    possession_type = models.CharField(max_length=10, choices=POSSESSION_TYPE_CHOICES)

    # For team stats
    team = models.ForeignKey(
        "teams.Team",
        on_delete=models.CASCADE,
        related_name="possession_stats",
        null=True,
        blank=True,
    )
    side = models.CharField(
        max_length=10,
        choices=[("home", "Home"), ("away", "Away")],
        null=True,
        blank=True,
    )

    # For player stats
    player = models.ForeignKey(
        TracePlayer,
        on_delete=models.CASCADE,
        related_name="possession_stats",
        null=True,
        blank=True,
    )

    # Single JSON field for all metrics - maximum flexibility
    metrics = models.JSONField(
        default=dict,
        help_text="All possession metrics stored in JSON format. Structure varies by type: team metrics include possession_percentage, total_possessions, etc. Player metrics include touches_in_possession, involvement_percentage, etc.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "possession_type", "team", "side"],
                condition=models.Q(possession_type="team"),
                name="unique_team_possession_stats",
            ),
            models.UniqueConstraint(
                fields=["session", "possession_type", "player"],
                condition=models.Q(possession_type="player"),
                name="unique_player_possession_stats",
            ),
        ]
        indexes = [
            models.Index(fields=["session", "possession_type"]),
            models.Index(fields=["session", "possession_type", "team"]),
            models.Index(fields=["session", "possession_type", "player"]),
        ]
        verbose_name = "Possession Stats"
        verbose_name_plural = "Possession Stats"

    def __str__(self):
        if self.possession_type == "team":
            possession_pct = self.metrics.get("possession_percentage", 0.0)
            return f"{self.team.name} ({self.side}) - {possession_pct:.1f}% possession"
        else:
            involvement_pct = self.metrics.get("involvement_percentage", 0.0)
            return f"{self.player.name} - {involvement_pct:.1f}% involvement"

    # Helper methods for easy access to common metrics
    def get_possession_percentage(self):
        """Get possession percentage for team stats"""
        return self.metrics.get("possession_percentage", 0.0)

    def get_total_possessions(self):
        """Get total possessions for team stats"""
        return self.metrics.get("total_possessions", 0)

    def get_involvement_percentage(self):
        """Get involvement percentage for player stats"""
        return self.metrics.get("involvement_percentage", 0.0)

    def get_possessions_involved(self):
        """Get possessions involved for player stats"""
        return self.metrics.get("possessions_involved", 0)
