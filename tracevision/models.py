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
