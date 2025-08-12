from pathlib import Path
import os
from django.utils.timezone import timedelta


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("django-secret-key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ['.hiwajo.com']
CSRF_TRUSTED_ORIGINS = [
    'https://api.hiwajo.com', 
    'https://api2.hiwajo.com',
    'https://staging-api.hiwajo.com', 
]

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "calendar_entry",
    "rest_framework",
    "storages", # azure blob storage
    "core",
    "accounts",
    "onboarding",
    "cards",
    "chatbot_admin",
    "events",
    "questionnaire",
    "notifications",
    "games",
    "teams",
    "match_data",
    "chatbot_features",
    "tracevision",
    "django_apscheduler"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middlewares.DatabaseLogMiddleware",
]

# REST Framework configuration for OAuth2
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'core.middlewares.JWTAuthentication',
        'chatbot_admin.middlewares.ChatbotAdminJWTAuthentication',
    )
}

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Default authentication
]

ROOT_URLCONF = "wajo_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "wajo_backend.wsgi.application"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": "redis://redis-server:6379/1",  # Redis DB 1
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        }
    }
}


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("wajo-db-name"),
        "HOST": os.environ.get("wajo-db-host"),
        "PORT": os.environ.get("wajo-db-port"),
        "USER": os.environ.get("wajo-db-user"),
        "PASSWORD": os.environ.get("wajo-db-password"),
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Jerusalem"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

WAJO_OTP_SERVICE_URL = os.environ.get('wajo-otp-service-url')
WAJO_GOOGLE_GEMINI_API_KEY = os.environ.get('wajo-google-gemini-api-key')
WAJO_NOTIFICATIONS_API_URL = os.environ.get('wajo-notifications-api-url')

JWT_ACCESS_TOKEN_EXPIRATION = timedelta(days=30)
JWT_REFRESH_TOKEN_EXPIRATION = timedelta(days=40)

OTP_EXPIRATION_TIME = 10 # 10 minutes

"""
?: (security.W004) You have not set a value for the SECURE_HSTS_SECONDS setting. 
If your entire site is served only over SSL, you may want to consider setting a value and enabling HTTP Strict Transport Security. 
Be sure to read the documentation first; enabling HSTS carelessly can cause serious, irreversible problems.
"""

"""
More on this, 
https://stackoverflow.com/questions/49166768/setting-secure-hsts-seconds-can-irreversibly-break-your-site
"""

CSRF_COOKIE_SECURE = True

AZURE_ACCOUNT_NAME = os.environ.get('wajo-azure-storage-account-name')
AZURE_ACCOUNT_KEY = os.environ.get('wajo-azure-storage-account-key')
# If using SAS token instead of key, use: AZURE_SAS_TOKEN = "<your_sas_token>"

AZURE_CUSTOM_DOMAIN = f"{AZURE_ACCOUNT_NAME}.blob.core.windows.net"

# Use the custom storages
STATICFILES_STORAGE = 'core.azure_storages.AzureStaticStorage'
DEFAULT_FILE_STORAGE = 'core.azure_storages.AzureMediaStorage'

# Set URLs to serve static and media files
STATIC_URL = f"https://{AZURE_CUSTOM_DOMAIN}/static/"
MEDIA_URL = f"https://{AZURE_CUSTOM_DOMAIN}/media/"

TRACEVISION_CUSTOMER_ID = os.environ.get("tracevision-customer-id")
TRACEVISION_API_KEY = os.environ.get("tracevision-api-key")
TRACEVISION_GRAPHQL_URL = os.environ.get("tracevision-graphql-url")
SCHEDULER_AUTOSTART = os.environ.get("scheduler-autostart", "False")

# TraceVision Cache Configuration
TRACEVISION_STATUS_CACHE_TIMEOUT = int(os.environ.get("tracevision-status-cache-timeout", "300"))  # 5 minutes
TRACEVISION_RESULT_CACHE_TIMEOUT = int(os.environ.get("tracevision-result-cache-timeout", "1800"))  # 30 minutes 