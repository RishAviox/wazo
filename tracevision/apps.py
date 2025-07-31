import sys
from django.apps import AppConfig

class TracevisionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tracevision"

    def ready(self):
        if 'runserver' in sys.argv:
            from .scheduler import start_scheduler
            start_scheduler()