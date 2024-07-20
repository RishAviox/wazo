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
    coach = models.ForeignKey('self', related_name='players', null=True,
                                blank=True, on_delete=models.SET_NULL,
                                limit_choices_to={'role': 'Coach'}
                            )

    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Wajo User"
        verbose_name_plural = "Wajo Users"


    def clean(self):
        # Ensure that only players can have a coach
        if self.role == 'Coach' and self.coach is not None:
            raise ValidationError("A coach cannot have another coach assigned.")

    def save(self, *args, **kwargs):
        self.clean()  # Call the clean method to enforce the validation
        super().save(*args, **kwargs)

    def __str__(self):
        return self.phone_no
    
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
        return self.user.phone_no
    
    class Meta:
        unique_together = ('user', 'fcm_token')
        verbose_name = "Wajo User Device"
        verbose_name_plural = "Wajo User Devices"


# Map player id with the user
class PlayerIDMapping(models.Model):
    user = models.ForeignKey(WajoUser, on_delete=models.CASCADE, related_name="player_ids")
    player_id = models.CharField(max_length=255)
    
    created_on = models.DateTimeField(auto_now_add=True)
    updated_on = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.player_id
    
    class Meta:
        verbose_name = "Player ID Mapping"
        verbose_name_plural = "Player ID Mappings"