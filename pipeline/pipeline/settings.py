"""
Django settings for pipeline project.

Generated by 'django-admin startproject' using Django 3.0.7.

For more information on this file, see
https://docs.djangoproject.com/en/3.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.0/ref/settings/
"""

import os
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration


# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    "SECRET_KEY", "o9b=*)+bd#oad=!%-yr9n@_u(y9m2@89jlr2&4ix555!ha5#&e"
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DEBUG", False) == "True"
ALLOWED_HOSTS = [os.environ.get("ALLOWED_HOST", "localhost"), '0.0.0.0']

# Application definition

INSTALLED_APPS = [
    "subtitles.apps.SubtitlesConfig",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "embed_video",
    "django_cleanup.apps.CleanupConfig",
    "core.apps.CoreConfig",
    "mooclink.apps.MooclinkConfig",
    "django_celery_results",
    "django_celery_beat",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.AuthenticationTenantMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pipeline.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates"), ],
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

WSGI_APPLICATION = "pipeline.wsgi.application"


# Database
# https://docs.djangoproject.com/en/3.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": os.environ.get("SQL_DATABASE", "pipeline"),
        "USER": os.environ.get("SQL_USER", "django_user"),
        "PASSWORD": os.environ.get("SQL_PASSWORD", "xmg99dzWEX8qUUi"),
        "HOST": os.environ.get("SQL_HOST", "localhost"),
        "PORT": os.environ.get("SQL_PORT", "5432"),
        "CONN_MAX_AGE": None,  # Use persistent database connections
    }
}

# Password validation
# https://docs.djangoproject.com/en/3.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator", },
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator", },
]


# Internationalization
# https://docs.djangoproject.com/en/3.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "CET"

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.0/howto/static-files/

STATIC_URL = "/static/"
# STATICFILES_DIRS = [
#     os.path.join(BASE_DIR, "static"),
# ]
STATIC_ROOT = os.environ.get(
    "STATIC_ROOT", os.path.join(BASE_DIR, "subtitles/static/"))

# Media files (*.vtt, etc.)
MEDIA_ROOT = os.environ.get(
    "MEDIA_ROOT", os.path.join(BASE_DIR, "subtitles/media/"))
MEDIA_URL = "media/"

# TODO: delete if no longer needed
# Redirect to localhost main page after login and logout (Default redirects to /accounts/profile/)
LOGIN_REDIRECT_URL = "/subtitles/list/"
LOGOUT_REDIRECT_URL = "/accounts/login/"
LOGIN_URL = "login"

# Use our own customized User-Model.
AUTH_USER_MODEL = 'core.TranspipeUser'

# Logs all emails sent to the console. You can copy the password reset link from the console
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", None)
EMAIL_HOST = os.environ.get("EMAIL_HOST", None)
EMAIL_PORT = os.environ.get("EMAIL_PORT", None)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", None)
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", None)

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", None)
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", None)

SECURE_SSL_REDIRECT = bool(os.environ.get("FORCE_SSL", False))
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = bool(os.environ.get("FORCE_SSL", False))
CSRF_COOKIE_SECURE = bool(os.environ.get("FORCE_SSL", False))

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN", None),
    integrations=[DjangoIntegration()],
    send_default_pii=True,
    release=os.environ.get("SENTRY_RELEASE", None),
)

# LOAD AWS MIE CREDENTIALS
DATAPLANE_BUCKET = os.environ.get("DATAPLANE_BUCKET")

_BOOLEAN_TRUE_EQUIVALENTS = {'true', '1', 't'}

XIKOLO_ASYNC_VIDEO_DETAIL_FETCH = (
        os.environ.get("XIKOLO_ASYNC_VIDEO_DETAIL_FETCH", "True").casefold() in _BOOLEAN_TRUE_EQUIVALENTS
)

PUBLIC_ADDRESS = os.environ.get("PUBLIC_ADDRESS", "https://transpipe.openhpi.de")

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'tbl_cache',
    }
}

CELERY_TIMEZONE = "Europe/Berlin"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_RESULT_BACKEND = 'django-db'
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', f"amqp://rabbit:rabbit@rabbitmq:5672/transpipevhost")
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_TASK_ACKS_LATE = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
