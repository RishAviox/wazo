from django.db import models
from django.core.exceptions import ValidationError
from .user import WajoUser

class CoachTeamMapping(models.Model):
    coach = models.ManyToManyField(
        WajoUser, 
        related_name="coach_team_mappings",
        limit_choices_to={'role': 'Coach'}  # Limit choices to users with the role 'Coach'
    )
    team_id = models.CharField(max_length=10, unique=True)
    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def clean(self):
        for coach in self.coach.all():
            if coach.coach_team_mappings.exclude(id=self.id).exists():
                raise ValidationError(f"Coach {coach} is already assigned to another team")

    def __str__(self) -> str:
        return self.team_id
    
    class Meta:
        verbose_name = "Coach Team Mappings"
        verbose_name_plural = "Coach Team Mappings"


# Team Stats, store all metrics into single JSON
class TeamStats(models.Model):
    team_mapping = models.OneToOneField(CoachTeamMapping, on_delete=models.CASCADE, related_name='team_stats')
    metrics = models.JSONField(default=dict)
     
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Team Stats"
        verbose_name_plural = "Team Stats"

    def __str__(self):
        return f"Stats for Team with ID: {self.team_mapping.team_id}"
