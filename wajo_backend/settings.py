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
CSRF_TRUSTED_ORIGINS = ['https://api.hiwajo.com', 'https://api2.hiwajo.com']

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
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


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "mssql",
        "NAME": os.environ.get("wajo-db-name"),
        "HOST": os.environ.get("wajo-db-host"),
        "PORT": os.environ.get("wajo-db-port"),
        "USER": os.environ.get("wajo-db-user"),
        "PASSWORD": os.environ.get("wajo-db-password"),
        'OPTIONS': {
            'driver': 'ODBC Driver 17 for SQL Server', 
            'MARS_Connection': 'True',
            "extra_params": "Encrypt=yes;TrustServerCertificate=no;"
        },

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

# Azure Blob Storage

AZURE_ACCOUNT_NAME = os.environ.get('wajo-azure-storage-account-name')
AZURE_ACCOUNT_KEY = os.environ.get('wajo-azure-storage-account-key')
AZURE_CONTAINER_STATIC = "static"  
AZURE_CONTAINER_MEDIA = "media" 


# Point STATICFILES_STORAGE to your custom static storage class
STATICFILES_STORAGE = "core.storages.AzureStaticStorage"

# Point DEFAULT_FILE_STORAGE to your custom media storage class
DEFAULT_FILE_STORAGE = "core.storages.AzureMediaStorage"

# Static files
STATIC_URL = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_STATIC}/"

# Media files
MEDIA_URL = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_MEDIA}/"

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

WAJO_OTP_SERVICE_URL = os.environ.get('wajo-otp-service-url')
WAJO_GOOGLE_GEMINI_API_KEY = os.environ.get('wajo-google-gemini-api-key')
WAJO_NOTIFICATIONS_API_URL = os.environ.get('wajo-notifications-api-url')

JWT_ACCESS_TOKEN_EXPIRATION = timedelta(hours=24)
JWT_REFRESH_TOKEN_EXPIRATION = timedelta(days=7)

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