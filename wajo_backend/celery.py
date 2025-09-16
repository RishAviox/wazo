import os
from django.conf import settings
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', os.getenv('django-settings-module', 'wajo_backend.settings_dev'))

app = Celery(settings.PROJECT_NAME)

app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Optional: Configure timezone for scheduled tasks
app.conf.timezone = 'UTC'

# Periodic schedules
app.conf.beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {
    # 'tracevision-aggregate-reconcile-every-15m': {
    #     'task': 'tracevision.reconcile_aggregates_for_processed_sessions',
    #     'schedule': 15 * 60,  # seconds
    # },
    # Process TraceVision sessions every 2 hours, starting immediately
    'tracevision-process-sessions-every-2h': {
        'task': 'tracevision.tasks.process_trace_sessions_task',
        # 'schedule': 2 * 60 * 60,  # 2 hours in seconds
        'schedule': 60,  # every minute
    },
})