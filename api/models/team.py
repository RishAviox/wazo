from django.db import models
from django.core.exceptions import ValidationError
from .user import WajoUser

# Team Stats, store all metrics into single JSON
class TeamStats(models.Model):
    team_id = models.CharField(max_length=10, primary_key=True)
    metrics = models.JSONField(default=dict)
     
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Team Stats"
        verbose_name_plural = "Team Stats"

    def __str__(self):
        return f"Stats for Team with ID: {self.team_id}"


class CoachTeamMapping(models.Model):
    coach = models.OneToOneField( # Ensure each coach is assigned to only one team
        WajoUser, 
        on_delete=models.CASCADE,
        related_name="coach_team_mappings",
        limit_choices_to={'role': 'Coach'},
    )
    team_stats = models.ForeignKey(
        TeamStats, 
        on_delete=models.CASCADE, 
        related_name='coach_mappings'  # Rename related_name to avoid ambiguity
    )
    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def clean(self):
        # Check if the coach is already assigned to another team
        if CoachTeamMapping.objects.filter(coach=self.coach).exclude(id=self.id).exists():
            raise ValidationError(f"Coach {self.coach} is already assigned to another team.")

    def __str__(self) -> str:
        # Use team_stats.team_id for the team ID
        return f"Team ID: {self.team_stats.team_id} - Coach: {self.coach}"

    class Meta:
        verbose_name = "Coach Team Mapping"
        verbose_name_plural = "Coach Team Mappings"