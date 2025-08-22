from django.db import models

from accounts.models import WajoUser


class TraceSession(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE)
    session_id = models.CharField(max_length=250)
    match_date = models.DateField()
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    home_score = models.PositiveSmallIntegerField()
    away_score = models.PositiveSmallIntegerField()
    home_team_jersey_color = models.CharField(
        max_length=7, 
        help_text="Hex color code for home team jersey (e.g., #FF0000)"
    )
    away_team_jersey_color = models.CharField(
        max_length=7, 
        help_text="Hex color code for away team jersey (e.g., #0000FF)"
    )
    final_score = models.CharField(
        max_length=10,
        help_text="Final score in format 'home_score-away_score' (e.g., '2-1')"
    )
    start_time = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Start time of the video, if known"
    )
    video_url = models.URLField()
    result = models.JSONField(default=dict)

    status = models.CharField(
        max_length=20,
        default="waiting_for_data",
        help_text="Status of the session processing"
    )
    
    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True, help_text="When the session was created")
    updated_at = models.DateTimeField(auto_now=True, help_text="When the session was last updated")

    class Meta:
        ordering = ['-updated_at', '-created_at']  # Latest updated first, then latest created

    def __str__(self):
        return f"{self.id} | {self.match_date} | {self.home_team} vs {self.away_team} | Status: {self.status}"


class TracePlayer(models.Model):
    name = models.CharField(max_length=100)
    jersey_number = models.PositiveIntegerField()
    team = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    session = models.ForeignKey(to=TraceSession, on_delete=models.CASCADE)
    # user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='trace_players', help_text="User who owns this player data")


class TraceHighlight(models.Model):
    """
    Model to store highlight data from the TraceVision API
    """
    highlight_id = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the highlight")
    video_id = models.PositiveIntegerField(help_text="Video ID associated with the highlight")
    start_offset = models.PositiveIntegerField(help_text="Start offset in milliseconds")
    duration = models.PositiveIntegerField(help_text="Duration of the highlight in milliseconds")
    tags = models.JSONField(default=list, help_text="Tags associated with the highlight")
    video_stream = models.URLField(help_text="URL to the video stream")
    
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='highlights')
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='trace_highlights', help_text="User who owns this highlight")
    
    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['highlight_id']),
            models.Index(fields=['session', 'start_offset']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Highlight {self.highlight_id} - {self.duration}ms"


class TraceObject(models.Model):
    """
    Model to store object data from the TraceVision API
    """
    object_id = models.CharField(max_length=120, help_text="Unique identifier for the object")
    type = models.CharField(max_length=100, help_text="Type of the object")
    side = models.CharField(max_length=100, help_text="Side/team the object belongs to")
    appearance_fv = models.JSONField(null=True, blank=True, help_text="Appearance feature vector")
    color_fv = models.JSONField(null=True, blank=True, help_text="Color feature vector")
    tracking_url = models.URLField(help_text="URL to fetch tracking data")
    role = models.CharField(max_length=50, null=True, blank=True, help_text="Role of the object")
    
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='trace_objects')
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='user_trace_objects', help_text="User who owns this object")
    
    # For storing parsed tracking data instead of making separate requests
    tracking_data = models.JSONField(default=list, help_text="Parsed tracking data points (time_off, x, y, w, h)")
    
    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['object_id']
        indexes = [
            models.Index(fields=['object_id']),
            models.Index(fields=['session', 'type']),
            models.Index(fields=['session', 'side']),
            models.Index(fields=['user', 'type']),
        ]
        unique_together = ['object_id', 'session']

    def __str__(self):
        return f"{self.object_id} ({self.type}) - {self.side}"


class TraceHighlightObject(models.Model):
    """
    Many-to-many relationship between highlights and objects
    """
    highlight = models.ForeignKey(TraceHighlight, on_delete=models.CASCADE, related_name='highlight_objects')
    trace_object = models.ForeignKey(TraceObject, on_delete=models.CASCADE, related_name='object_highlights')
    
    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['highlight', 'trace_object']
        indexes = [
            models.Index(fields=['highlight']),
            models.Index(fields=['trace_object']),
        ]

    def __str__(self):
        return f"{self.highlight.highlight_id} - {self.trace_object.object_id}"


class TrackingData(models.Model):
    """
    Alternative model for storing individual tracking data points
    Use this if you prefer separate records instead of JSON field in TraceObject
    """
    trace_object = models.ForeignKey(TraceObject, on_delete=models.CASCADE, related_name='tracking_points')
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='tracking_data', help_text="User who owns this tracking data")
    time_off = models.FloatField(help_text="Time offset in seconds")
    x = models.FloatField(help_text="X coordinate")
    y = models.FloatField(help_text="Y coordinate")
    w = models.FloatField(help_text="Width")
    h = models.FloatField(help_text="Height")
    
    # Timestamp fields
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['time_off']
        indexes = [
            models.Index(fields=['trace_object', 'time_off']),
            models.Index(fields=['user', 'time_off']),
        ]
        unique_together = ['trace_object', 'time_off']

    def __str__(self):
        return f"{self.trace_object.object_id} at {self.time_off}s"


class TraceVisionPlayerStats(models.Model):
    """
    Calculated performance statistics for individual players in a session
    Generated from tracking data and highlights analysis
    """
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='player_stats')
    object_id = models.CharField(max_length=50, help_text="TraceVision object ID (e.g., home_1, away_15)")
    side = models.CharField(max_length=10, help_text="home or away team")
    
    # Movement and physical stats
    total_distance_meters = models.FloatField(default=0.0, help_text="Total distance covered in meters")
    avg_speed_mps = models.FloatField(default=0.0, help_text="Average speed in meters per second")
    max_speed_mps = models.FloatField(default=0.0, help_text="Maximum speed reached")
    total_time_seconds = models.FloatField(default=0.0, help_text="Total time tracked in seconds")
    
    # Sprint analysis
    sprint_count = models.PositiveIntegerField(default=0, help_text="Number of sprints detected")
    sprint_distance_meters = models.FloatField(default=0.0, help_text="Total distance covered in sprints")
    sprint_time_seconds = models.FloatField(default=0.0, help_text="Total time spent sprinting")
    
    # Position and tactical stats
    avg_position_x = models.FloatField(default=0.0, help_text="Average X position (0-1000 scale)")
    avg_position_y = models.FloatField(default=0.0, help_text="Average Y position (0-1000 scale)")
    position_variance = models.FloatField(default=0.0, help_text="Position variance (movement range)")
    
    # Heatmap data (stored as JSON for flexibility)
    heatmap_data = models.JSONField(default=dict, help_text="Heatmap grid data for visualization")
    
    # Performance metrics
    performance_score = models.FloatField(default=0.0, help_text="Overall performance score 0-100")
    stamina_rating = models.FloatField(default=0.0, help_text="Stamina rating based on movement patterns")
    work_rate = models.FloatField(default=0.0, help_text="Work rate based on distance and speed")
    
    # Calculation metadata
    calculation_method = models.CharField(max_length=100, default="standard", help_text="Method used for calculations")
    calculation_version = models.CharField(max_length=20, default="1.0", help_text="Calculation algorithm version")
    last_calculated = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['session', 'object_id']
        indexes = [
            models.Index(fields=['session', 'object_id']),
            models.Index(fields=['side', 'performance_score']),
            models.Index(fields=['performance_score', 'last_calculated']),
        ]
        verbose_name = "TraceVision Player Stats"
        verbose_name_plural = "TraceVision Player Stats"

    def __str__(self):
        return f"{self.object_id} - {self.session.session_id} - Score: {self.performance_score}"

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
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='session_stats')
    
    # Team performance metrics
    home_team_stats = models.JSONField(default=dict, help_text="Home team aggregated stats")
    away_team_stats = models.JSONField(default=dict, help_text="Away team aggregated stats")
    
    # Match analysis
    possession_data = models.JSONField(default=dict, help_text="Possession percentages and patterns")
    tactical_analysis = models.JSONField(default=dict, help_text="Formation and tactical insights")
    
    # Data quality metrics
    total_tracking_points = models.PositiveIntegerField(default=0, help_text="Total tracking data points")
    data_coverage_percentage = models.FloatField(default=0.0, help_text="Percentage of video with tracking data")
    quality_score = models.FloatField(default=0.0, help_text="Overall data quality score")
    
    # Processing metadata
    processing_status = models.CharField(max_length=20, default="pending", help_text="Stats processing status")
    processing_errors = models.JSONField(default=list, help_text="Any errors during processing")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['session']
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['processing_status', 'created_at']),
        ]
        verbose_name = "TraceVision Session Stats"
        verbose_name_plural = "TraceVision Session Stats"

    def __str__(self):
        return f"Session Stats - {self.session.session_id} - Quality: {self.quality_score}%"


class TraceCoachReportTeam(models.Model):
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='coach_report_team')
    side = models.CharField(max_length=10)
    goals = models.IntegerField(default=0)
    shots = models.IntegerField(default=0)
    passes = models.IntegerField(default=0)
    possession_time_s = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['session', 'side']
        indexes = [
            models.Index(fields=['session', 'side']),
        ]
        verbose_name = 'Coach Report Team'
        verbose_name_plural = 'Coach Report Team'


class TraceTouchLeaderboard(models.Model):
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='touch_leaderboard')
    object_id = models.CharField(max_length=50)
    object_side = models.CharField(max_length=10)
    touches = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['session', 'object_id']
        indexes = [
            models.Index(fields=['session']),
            models.Index(fields=['object_side', 'touches']),
        ]
        verbose_name = 'Touch Leaderboard Entry'
        verbose_name_plural = 'Touch Leaderboard Entries'


class TracePossessionSegment(models.Model):
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='possession_segments')
    side = models.CharField(max_length=10)
    start_ms = models.IntegerField()
    end_ms = models.IntegerField()
    count = models.IntegerField(default=0)
    start_clock = models.CharField(max_length=20, blank=True)
    end_clock = models.CharField(max_length=20, blank=True)
    duration_s = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['session', 'side']),
            models.Index(fields=['session', 'start_ms']),
        ]
        verbose_name = 'Possession Segment'
        verbose_name_plural = 'Possession Segments'


class TraceClipReel(models.Model):
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='clip_reels')
    event_id = models.CharField(max_length=100)
    video_id = models.IntegerField()
    event_type = models.CharField(max_length=50)
    side = models.CharField(max_length=10)
    start_ms = models.IntegerField()
    duration_ms = models.IntegerField()
    start_clock = models.CharField(max_length=20, blank=True)
    end_clock = models.CharField(max_length=20, blank=True)
    object_id = models.CharField(max_length=50, blank=True, null=True)
    label = models.CharField(max_length=100, blank=True)
    tags = models.JSONField(default=list)
    video_stream = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['session', 'side']),
            models.Index(fields=['session', 'event_id']),
            models.Index(fields=['session', 'object_id']),
        ]
        unique_together = ['session', 'event_id', 'object_id']
        verbose_name = 'Clip Reel Item'
        verbose_name_plural = 'Clip Reel Items'


class TracePass(models.Model):
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='passes')
    side = models.CharField(max_length=10)
    from_object_id = models.CharField(max_length=50)
    to_object_id = models.CharField(max_length=50)
    start_ms = models.IntegerField()
    duration_ms = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['session', 'side']),
            models.Index(fields=['session', 'from_object_id', 'to_object_id']),
        ]
        verbose_name = 'Pass'
        verbose_name_plural = 'Passes'


class TracePassingNetwork(models.Model):
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='passing_network')
    side = models.CharField(max_length=10)
    from_object_id = models.CharField(max_length=50)
    to_object_id = models.CharField(max_length=50)
    passes_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['session', 'side', 'from_object_id', 'to_object_id']
        indexes = [
            models.Index(fields=['session', 'side']),
            models.Index(fields=['passes_count']),
        ]
        verbose_name = 'Passing Network Edge'
        verbose_name_plural = 'Passing Network Edges'