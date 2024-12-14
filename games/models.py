from django.db import models
import os
from django.core.exceptions import ValidationError
import pandas as pd

from teams.models import Team
from core.soft_delete import WajoModel


class Game(WajoModel):
    GAME_TYPE_CHOICES = [
        ('match', 'Match'),
        ('training', 'Training'),
    ]

    id = models.CharField(max_length=10, primary_key=True, unique=True)  # User-defined unique ID
    type = models.CharField(max_length=10, choices=GAME_TYPE_CHOICES)
    name = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    teams = models.ManyToManyField(Team, related_name="games", blank=True)  # Teams that played in the game

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Game"
        verbose_name_plural = "Games"

    def __str__(self):
        return f"Game-{self.id} ({self.type})"

# Game GPS Data File
def validate_file_extension(value):
    ext = os.path.splitext(value.name)[1]  # [0] returns path + filename
    valid_extensions = ['.xlsx']
    if not ext.lower() in valid_extensions:
        raise ValidationError('Unsupported file extension. Allowed extensions: .xlsx')

def game_gps_data_file_path(instnace, filename):
    # MEDIA_ROOT / uploads/game_gps_data_files/<filename>
    return 'uploads/game_gps_data_files/{0}'.format(filename)

class GameGPSData(WajoModel):
    GAME_TYPE_CHOICES = [
        ('match', 'Match'),
        ('training', 'Training'),
    ]
    game_type = models.CharField(max_length=10, choices=GAME_TYPE_CHOICES)
    data_file = models.FileField(
                upload_to=game_gps_data_file_path, 
                validators=[validate_file_extension]
            )
    notes = models.TextField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    game = models.ForeignKey(
        Game,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="gps_data"
    )

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    # process file with signal

    class Meta:
        verbose_name = "Game GPS Data"
        verbose_name_plural = "Game GPS Data"

    def __str__(self):
        return self.data_file.name
    

# Game Video Data
def game_video_data_file_path(instnace, filename):
    # MEDIA_ROOT / uploads/game_video_data_files/<filename>
    return 'uploads/game_video_data_files/{0}'.format(filename)

class GameVideoData(WajoModel):
    GAME_TYPE_CHOICES = [
        ('match', 'Match'),
        ('training', 'Training'),
    ]
    PROVIDER_CHOICES = [
        ('BEPRO', 'BEPRO'),
    ]
    provider = models.CharField(max_length=16, choices=PROVIDER_CHOICES)
    game_type = models.CharField(max_length=10, choices=GAME_TYPE_CHOICES)
    data_file = models.FileField(
                upload_to=game_video_data_file_path, 
                validators=[validate_file_extension]
            )
    notes = models.TextField(null=True, blank=True)
    is_processed = models.BooleanField(default=False)
    game = models.ForeignKey(
        Game,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="video_data"
    )
    first_half_url = models.TextField()
    first_half_padding = models.IntegerField(default=0)
    
    second_half_url = models.TextField()
    second_half_padding = models.IntegerField(default=0)
    
    highlight_url = models.TextField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    # process file with signal

    class Meta:
        verbose_name = "Game Video Data"
        verbose_name_plural = "Game Video Data"

    def __str__(self):
        return self.data_file.name
    
# game video data json, process with signal on GameVideoData save
class GameMetaData(WajoModel):
    game = models.ForeignKey(
        Game,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="game_meta_data"
    )
    data = models.JSONField()

    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Game Meta Data JSON"
        verbose_name_plural = "Game Meta Data JSON"

    def __str__(self):
        return self.game.name