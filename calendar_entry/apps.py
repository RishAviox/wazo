from django.apps import AppConfig


class CalendarMarkerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calendar_entry'

    def ready(self):
        import calendar_entry.signals