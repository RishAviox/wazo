from django.db import models
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

    def __str__(self) -> str:
        return self.team_id
    
    class Meta:
        verbose_name = "Coach Team Mappings"
        verbose_name_plural = "Coach Team Mappings"