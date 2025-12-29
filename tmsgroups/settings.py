"""
Django settings for tmsgroups project - FINAL PRODUCTION READY
Supports Development (Windows) + Production (Server) with S3 + Redis
"""
import os
from pathlib import Path
from decouple import config, Csv  # pip install python-decouple
from logging import Filter, LogRecord

from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production-please!')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'tms',
    'whitenoise.runserver_nostatic',
    'crispy_forms',
    'crispy_bootstrap5',
    'django.contrib.humanize',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tmsgroups.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'tms' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'tmsgroups.wsgi.application'

USE_TZ = True
TIME_ZONE = 'Asia/Kolkata'

# Database - from .env
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
    }
}

# Static & Media (Base)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'tms/static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'tms/media'  # Only used when USE_S3=False

LOGIN_REDIRECT_URL = '/login-redirect/'

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ==================== S3 + REDIS INTEGRATION (SAFE & SWITCHABLE) ====================

USE_S3 = config('USE_S3', default=False, cast=bool)
USE_REDIS = config('USE_REDIS', default=False, cast=bool)

# --- S3 for Media (Images, Banners, Logos) ---
if USE_S3:
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='ap-south-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_SIGNATURE_VERSION = 's3v4'

    # All uploaded files go to S3
    DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
else:
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# --- Redis Cache & Sessions (runs on same server) ---
if USE_REDIS:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": "redis://127.0.0.1:6379/1",
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "KEY_PREFIX": "tms"
        }
    }
    # Use Redis for sessions (faster login/logout)
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"

# Static files handling (Whitenoise for production)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'


# ==================== LOGGING (FINAL - DETAILED + SAFE) ====================
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

class SafeExtrasFilter(Filter):
    def filter(self, record: LogRecord) -> bool:
        # Safely set defaults for all expected extra fields
        record.client_ip = getattr(record, 'client_ip', 'unknown')
        record.user = getattr(record, 'user', 'anonymous')
        record.product = getattr(record, 'product', '-')
        record.store = getattr(record, 'store', '-')
        record.customer_name = getattr(record, 'customer_name', '-')
        record.phone = getattr(record, 'phone', '-')
        record.city = getattr(record, 'city', '-')
        record.product_id = getattr(record, 'product_id', '-')
        return True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'safe_extras': {
            '()': SafeExtrasFilter,
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
        'public_detailed': {
            'format': '{levelname} {asctime} [IP: {client_ip}] [User: {user}] {message} | Product: {product} (ID: {product_id}) | Store: {store} | Name: {customer_name} | Phone: {phone} | City: {city}',
            'style': '{',
        },
        'safe_console': {
            'format': '{levelname} {asctime} [IP: %(client_ip)s] [User: %(user)s] %(message)s',
            'style': '%',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['safe_extras'],
        },
        'superadmin_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'superadmin.log',
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'verbose',
            'filters': ['safe_extras'],
            'encoding': 'utf-8',
        },
        'storeadmin_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'storeadmin.log',
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'verbose',
            'filters': ['safe_extras'],
            'encoding': 'utf-8',
        },
        'public_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'public.log',
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'public_detailed',   # ← CORRECT
            'filters': ['safe_extras'],
            'encoding': 'utf-8',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOGS_DIR / 'errors.log',
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'verbose',
            'level': 'ERROR',
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'superadmin': {
            'handlers': ['superadmin_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'storeadmin': {
            'handlers': ['storeadmin_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'public': {
            'handlers': ['public_file', 'console'],
            'level': 'INFO',
            'propagate': False,
            # ← REMOVED formatter here — it's set in handler
        },
        'django': {
            'handlers': ['error_file', 'console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}