from django.apps import AppConfig


class MatchDataConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'match_data'

    def ready(self):
        from match_data import signals
