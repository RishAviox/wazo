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
        return f"{self.match_date} | {self.home_team} vs {self.away_team} | Status: {self.status}"


class TracePlayer(models.Model):
    name = models.CharField(max_length=100)
    jersey_number = models.PositiveIntegerField()
    team = models.CharField(max_length=100)
    position = models.CharField(max_length=100)
    session = models.ForeignKey(to=TraceSession, on_delete=models.CASCADE)
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='trace_players', help_text="User who owns this player data")


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
    
    session = models.ForeignKey(TraceSession, on_delete=models.CASCADE, related_name='objects')
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name='trace_objects', help_text="User who owns this object")
    
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