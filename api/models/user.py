from django.db import models
from django.core.exceptions import ValidationError


# On creating WajoUser, new OnboardingStep instance will be created using signals
# refer signals.py

def profile_picture_path(instnace, filename):
    # MEDIA_ROOT / uploads/user_phone_no/profile_picture/<filename>
    return 'uploads/user_{0}/profile_picture/{1}'.format(instnace.phone_no, filename)

class WajoUser(models.Model):
    phone_no = models.CharField(max_length=15, unique=True, primary_key=True)
    selected_language = models.CharField(max_length=15)
    # fcm_token = models.CharField(max_length=255)
    # we have WajoUserDevice to store FCM tokens

    # Onboarding Profile
    name = models.CharField(max_length=50, blank=True, null=True)
    nickname = models.CharField(max_length=50, blank=True, null=True)
    gender = models.CharField(max_length=15, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    primary_sport = models.CharField(max_length=50, blank=True, null=True)
    role = models.CharField(max_length=50, blank=True, null=True)
    wake_up_time = models.TimeField(blank=True, null=True)
    sleep_time = models.TimeField(blank=True, null=True)
    picture = models.ImageField(blank=True, null=True, upload_to=profile_picture_path)

    # Self-referential many-to-many relationship
    coach = models.ManyToManyField('self', related_name='players',
                                blank=True,
                                limit_choices_to={'role': 'Coach'},
                                symmetrical=False, 
                            )
    """
        symmetrical=False meaning
        if Player1 has Coach1 as a coach, 
        it doesn't mean that Coach1 automatically has Player1 as a coach. 
        The relationship is one-way: coaches are assigned to players,
        but not the other way around.
    """

    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wajo User"
        verbose_name_plural = "Wajo Users"


    def clean(self):
        # Ensure that only players can have a coach
        print(self.coach.exists())
        if self.role == 'Coach' and self.coach.exists():
            raise ValidationError("A coach cannot have another coach assigned.")

    def save(self, *args, **kwargs):
        self.clean()  # Call the clean method to enforce the validation
        super().save(*args, **kwargs)

    def __str__(self):
        return self.phone_no + " - " + self.name if self.name else self.phone_no
    
    @property
    def is_authenticated(self):
        """Always return True for compatibility with Django's authentication system."""
        return True
    



# Store FCM Tokens
class WajoUserDevice(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="devices")
    fcm_token = models.CharField(max_length=255)
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.user.phone_no) + "--->" + self.fcm_token
    
    class Meta:
        unique_together = ('user', 'fcm_token')
        verbose_name = "Wajo User Device"
        verbose_name_plural = "Wajo User Devices"


# Map player id with the user
POSITION_CHOICES = [
        ('GK', 'Goalkeeper'),
        ('CB', 'Center Back'),
        ('LB', 'Left Back'),
        ('RB', 'Right Back'),
        ('LWB', 'Left Wing Back'),
        ('RWB', 'Right Wing Back'),
        ('CDM', 'Central Defensive Midfielder'),
        ('CM', 'Central Midfielder'),
        ('CAM', 'Central Attacking Midfielder'),
        ('LM', 'Left Midfielder'),
        ('RM', 'Right Midfielder'),
        ('LW', 'Left Winger'),
        ('RW', 'Right Winger'),
        ('ST', 'Striker'),
        ('CF', 'Center Forward'),
    ]
class PlayerIDMapping(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="player_ids")
    player_id = models.CharField(max_length=10, unique=True)
    player_position = models.CharField(max_length=10, choices=POSITION_CHOICES, default='ST')
    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.player_id
    
    class Meta:
        verbose_name = "Player ID Mappings"
        verbose_name_plural = "Player ID Mappings"
        constraints = [
            models.UniqueConstraint(fields=['user'],  name='unique_user_player_id_mapping')
        ]


# Save notifications to DB in Notifications Service, serve via API
class Notification(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="notifications")
    device = models.ForeignKey(WajoUserDevice, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    body = models.CharField(max_length=255)
    postback = models.CharField(max_length=24)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.user.phone_no
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        