from django.db import models
from accounts.models import WajoUserDevice, WajoUser

from core.soft_delete import WajoModel

# Save notifications to DB in Notifications Service, serve via API
class Notification(WajoModel):
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
