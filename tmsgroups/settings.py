"""
Django settings for tmsgroups project - FINAL PRODUCTION READY
"""
import os
from pathlib import Path
from decouple import config, Csv
from logging import Filter, LogRecord

BASE_DIR = Path(__file__).resolve().parent.parent

# # SAFE .env FORCE LOAD
# env_path = BASE_DIR / '.env'

# if env_path.exists():
#     from decouple import Config, RepositoryEnv
#     os.environ.update(RepositoryEnv(str(env_path)).data)
# else:
#     raise FileNotFoundError(f".env file not found at {env_path}")

# SECURITY
SECRET_KEY = config('SECRET_KEY','django-insecure-j^6hn5x4)n2jg45r!l0h&q)5^q*01g+e)g9o=x*tcxd9rcf=lk')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'django.contrib.sitemaps',
    'storages',
    'celery',
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

# Database
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

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'tms/static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

LOGIN_REDIRECT_URL = '/login-redirect/'
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# ============ S3 CONFIGURATION - CONDITIONAL (DJANGO 4.2+ COMPATIBLE) ============
USE_S3 = config('USE_S3', default=False, cast=bool)

if USE_S3:
    # AWS Settings
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='ap-south-2')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_SIGNATURE_VERSION = 's3v4'

    # New Django 4.2+ STORAGES config
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "region_name": AWS_S3_REGION_NAME,
                "access_key": AWS_ACCESS_KEY_ID,
                "secret_key": AWS_SECRET_ACCESS_KEY,
                "custom_domain": AWS_S3_CUSTOM_DOMAIN,
                "file_overwrite": AWS_S3_FILE_OVERWRITE,
                "default_acl": AWS_DEFAULT_ACL,
                "querystring_auth": AWS_QUERYSTRING_AUTH,
                "signature_version": AWS_S3_SIGNATURE_VERSION,
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'
else:
    # Local fallback
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'



# ============ Redis & Celery ============
USE_REDIS = config('USE_REDIS', default=False, cast=bool)

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
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"

CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Kolkata'

# ============ Logging ============
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

class SafeExtrasFilter(Filter):
    def filter(self, record: LogRecord) -> bool:
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
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{',},
        'simple': {'format': '{levelname} {asctime} {message}', 'style': '{',},
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
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple', 'filters': ['safe_extras'],},
        'superadmin_file': {'class': 'logging.handlers.RotatingFileHandler', 'filename': LOGS_DIR / 'superadmin.log', 'maxBytes': 10485760, 'backupCount': 10, 'formatter': 'verbose', 'filters': ['safe_extras'], 'encoding': 'utf-8',},
        'storeadmin_file': {'class': 'logging.handlers.RotatingFileHandler', 'filename': LOGS_DIR / 'storeadmin.log', 'maxBytes': 10485760, 'backupCount': 10, 'formatter': 'verbose', 'filters': ['safe_extras'], 'encoding': 'utf-8',},
        'public_file': {'class': 'logging.handlers.RotatingFileHandler', 'filename': LOGS_DIR / 'public.log', 'maxBytes': 10485760, 'backupCount': 10, 'formatter': 'public_detailed', 'filters': ['safe_extras'], 'encoding': 'utf-8',},
        'error_file': {'class': 'logging.handlers.RotatingFileHandler', 'filename': LOGS_DIR / 'errors.log', 'maxBytes': 10485760, 'backupCount': 10, 'formatter': 'verbose', 'level': 'ERROR', 'encoding': 'utf-8',},
    },
    'loggers': {
        'superadmin': {'handlers': ['superadmin_file', 'console'], 'level': 'INFO', 'propagate': False,},
        'storeadmin': {'handlers': ['storeadmin_file', 'console'], 'level': 'INFO', 'propagate': False,},
        'public': {'handlers': ['public_file', 'console'], 'level': 'INFO', 'propagate': False,},
        'django': {'handlers': ['error_file', 'console'], 'level': 'ERROR', 'propagate': False,},
    },
}