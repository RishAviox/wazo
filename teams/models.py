from django.db import models
from accounts.models import WajoUser

from core.soft_delete import WajoModel

class Team(WajoModel):
    id = models.CharField(max_length=10, primary_key=True, unique=True)  # User-defined unique ID
    name = models.CharField(max_length=255, blank=True, null=True)
    logo = models.ImageField(upload_to="team_logos/", blank=True, null=True)
    jersey_color = models.CharField(max_length=7, blank=True, null=True)
    coach = models.ManyToManyField(
        WajoUser,
        related_name='teams_coached',
        blank=True,
        limit_choices_to={'role': 'Coach'}  # Restrict selection to users with the role "Coach"
    )

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name if self.name else f"Team {self.id}"

class TeamStats(WajoModel):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="team_stats")
    game = models.ForeignKey("games.Game", on_delete=models.CASCADE, related_name='game_team_stats')
    metrics = models.JSONField(default=dict)
     
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Team Stats"
        verbose_name_plural = "Team Stats"
        unique_together = ('team', 'game')

    def __str__(self):
        return f"Stats for Team: {self.team.name if self.team.name else self.team.id}"
