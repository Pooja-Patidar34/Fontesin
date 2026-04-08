
from pathlib import Path
from decouple import config
from datetime import timedelta
import os


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")


DEBUG = config("DEBUG", default="True").lower() == "true"
print(f"DEBUG mode is {'ON' if DEBUG else 'OFF'}")


if DEBUG:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1","52.53.204.127"]
else:
    ALLOWED_HOSTS = config(
        "ALLOWED_HOSTS",
        cast=lambda v: [s.strip() for s in v.split(",")],
    )


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    'accounts',
    'accounts_api',
    'billing',
    "drf_spectacular",
]

AUTH_USER_MODEL = "accounts.User"
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "FontEsin.middleware.correlation_id.CorrelationIDMiddleware",
    "FontEsin.middleware.request_logging.RequestLoggingMiddleware",
    "FontEsin.middleware.error_logging.ErrorLoggingMiddleware",
]

ROOT_URLCONF = 'FontEsin.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], 
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                "accounts.context_processors.admin_context",
            ],
        },
    },
]


WSGI_APPLICATION = 'FontEsin.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT"),
        'OPTIONS': {
            'connect_timeout': 5,
        },
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),

    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",

    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),

    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "120/min",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "FontEsin API",
    "DESCRIPTION": "API documentation for FontEsin backend",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,

    # Auth (JWT example)
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"bearerAuth": []}],
    "SECURITY_SCHEMES": {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    },
}

PRIVATE_KEY = (BASE_DIR / "keys/private.pem").read_text()
PUBLIC_KEY = (BASE_DIR / "keys/public.pem").read_text()

SIMPLE_JWT = {
    "ALGORITHM": "RS256",

    "SIGNING_KEY": PRIVATE_KEY,
    "VERIFYING_KEY": PUBLIC_KEY,

    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    
    
    # --- ROTATION ---
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,


    "AUTH_HEADER_TYPES": ("Bearer",),

    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

#Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/


STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = "/admin/login/"
LOGIN_REDIRECT_URL = "/admin/"
LOGOUT_REDIRECT_URL = "/admin/login/"


STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

LOGGING = {

    "version": 1,
    "disable_existing_loggers": False,

    "filters": {
        "correlation_id": {
            "()": "FontEsin.logging.correlation_filter.CorrelationIdFilter",
        }
    },

    "formatters": {
        "json": {
            "()": "FontEsin.logging.json_formatter.JSONFormatter",
        }
    },

    "handlers": {

        "technical_file": {
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "logs/technical.log"),
            "formatter": "json",
            "filters": ["correlation_id"],
        },

        "business_file": {
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "logs/business.log"),
            "formatter": "json",
            "filters": ["correlation_id"],
        },

        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "filters": ["correlation_id"],
        },
    },

    "loggers": {

        "technical": {
            "handlers": ["technical_file", "console"],
            "level": "INFO",
            "propagate": False,
        },

        "business": {
            "handlers": ["business_file", "console"],
            "level": "INFO",
            "propagate": False,
        },

    },
}

#varriff


# Email settings
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default="True").lower() == "true"
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@fontesin.com")

# MailerSend
MAILERSEND_API_KEY = config("MAILERSEND_API_KEY", default="")
MAILERSEND_FROM_EMAIL = config("MAILERSEND_FROM_EMAIL", default="noreply@fontesin.com")
MAILERSEND_FROM_NAME = config("MAILERSEND_FROM_NAME", default="FONTESIN")

VERIFF_API_KEY = config("VERIFF_API_KEY")
VERIFF_MASTER_SECRET = config("VERIFF_MASTER_SECRET")
VERIFF_BASE_URL = "https://stationapi.veriff.com"