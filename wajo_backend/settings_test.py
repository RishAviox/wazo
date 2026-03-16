"""
Test-specific Django settings.
Uses SQLite database for fast, isolated testing without Docker dependencies.
"""
from wajo_backend.settings_dev import *

# Override database to use SQLite for testing
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "test_db.sqlite3",
    }
}

# Use in-memory cache for faster tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Disable Celery for tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Disable external storage for tests
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
MEDIA_ROOT = BASE_DIR / 'test_media'
MEDIA_URL = '/media/'

# Simplify password hashing for faster tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable migrations for faster test database creation
# (already set in pytest.ini with --nomigrations)

# Set DEBUG to False to match production-like behavior
DEBUG = False

# Allow all hosts for testing
ALLOWED_HOSTS = ['*']

# Disable CSRF for API tests
CSRF_COOKIE_SECURE = False

print("=" * 80)
print("USING TEST SETTINGS WITH SQLITE DATABASE")
print(f"Database: {DATABASES['default']['ENGINE']}")
print(f"Database Name: {DATABASES['default']['NAME']}")
print("=" * 80)
