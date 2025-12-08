import threading
from django.apps import AppConfig


class TracevisionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tracevision"

    def ready(self):
        import tracevision.signals  # noqa: F401 - Import signals to register them
        from .scheduler import start_scheduler

        threading.Thread(target=start_scheduler, daemon=True).start()
