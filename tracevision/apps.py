import threading
from django.apps import AppConfig

class TracevisionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tracevision"

    def ready(self):
        from .scheduler import start_scheduler
        threading.Thread(target=start_scheduler, daemon=True).start()