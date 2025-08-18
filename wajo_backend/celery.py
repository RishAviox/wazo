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