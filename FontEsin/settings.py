
from pathlib import Path
from decouple import config
from datetime import timedelta
import os

from django.utils.translation import gettext_lazy as _


BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("SECRET_KEY")


DEBUG = config("DEBUG", default="True").lower() == "true"
print(f"DEBUG mode is {'ON' if DEBUG else 'OFF'}")


ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
    cast=lambda v: [s.strip().strip('"').strip("'").strip("[").strip("]") for s in v.split(",") if s.strip()],
)
print(f"ALLOWED_HOSTS = {ALLOWED_HOSTS}")

# Origins that are allowed to make cross-origin POST/PUT/PATCH/DELETE
# requests over HTTPS. Required since Django 4.0 for any HTTPS form post
# behind a TLS-terminating proxy (Cloudflare → nginx). Driven from the
# environment so the same code runs in dev, staging, and prod without
# editing source.
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="",
    cast=lambda v: [s.strip() for s in v.split(",") if s.strip()],
)

# A failed CSRF check (stale form / rotated session) otherwise renders Django's
# bare "403 Forbidden" page, which reads as "Access Denied" and hides the real,
# recoverable cause. Route it through a friendly handler that bounces the user
# back with a "please try again" message. (handler403 only covers PermissionDenied,
# not CSRF failures — Django dispatches those to CSRF_FAILURE_VIEW.)
CSRF_FAILURE_VIEW = "accounts.view.error.csrf_failure"

# Cloudflare and nginx terminate TLS and proxy plain HTTP to gunicorn on
# 127.0.0.1. Without this header mapping, Django sees `http://` and
# `request.is_secure()` returns False — which breaks Secure cookies,
# CSRF on HTTPS POSTs, and redirects to the http:// scheme. nginx is
# configured to forward the X-Forwarded-Proto header (see runbook).
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")



# Application definition

INSTALLED_APPS = [
    'FontEsin',
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
    'listings'
]

AUTH_USER_MODEL = "accounts.User"
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'FontEsin.middleware.locale.UserLocaleMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "FontEsin.middleware.correlation_id.CorrelationIDMiddleware",
    "FontEsin.middleware.request_logging.RequestLoggingMiddleware",
    "FontEsin.middleware.error_logging.ErrorLoggingMiddleware",
    "FontEsin.middleware.no_emoji.NoEmojiMiddleware",
    "FontEsin.middleware.no_cache.NoCachePagesMiddleware",
    # Resolve the Business User's currently-selected company BEFORE the plan
    # gate — plans are company-scoped, so the plan resolver needs to know
    # which company the user is acting as.
    "FontEsin.middleware.active_company.ActiveCompanyMiddleware",
    # Identity verification gate runs BEFORE the plan gate: an unverified
    # account is forced onto /verify/ and can't reach plan selection until
    # Veriff approves it.
    "FontEsin.middleware.require_verification.RequireIdentityVerificationMiddleware",
    # Company gate: plans are company-scoped, so a verified Business User must
    # create their first company (the mandatory onboarding step) before using
    # the app. This replaced the old "pick a plan" gate — plan selection now
    # happens per-company AFTER certification, not at onboarding.
    "FontEsin.middleware.require_company.RequireCompanyForBusinessUserMiddleware",
    # Coordinator / franchise accounts can't reach the dashboard until a super
    # admin approves their application. Runs after the verification + plan
    # gates (Veriff first, then approval).
    "FontEsin.middleware.require_application_approval.RequireApplicationApprovalMiddleware",
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
                'django.template.context_processors.i18n',
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
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.Argon2PasswordHasher",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
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
        "anon": "100/min",
        "user": "200/min",
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

LANGUAGE_CODE = "en"

LANGUAGES = [
    ("en", _("English")),
    ("de", _("German")),
    ("es", _("Spanish")),
    ("fr", _("French")),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

TIME_ZONE = 'Asia/Kolkata'

USE_I18N = True

USE_TZ = True

#Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/


STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

# Allow up to ~11 GB uploads for the bulk company CSV importer. Files larger
# than FILE_UPLOAD_MAX_MEMORY_SIZE are streamed to a temp file on disk, so
# the gunicorn worker never holds the full payload in RAM. Nginx still
# needs client_max_body_size set to match (see deploy notes).
DATA_UPLOAD_MAX_MEMORY_SIZE = 11 * 1024 * 1024 * 1024   # 11 GB
FILE_UPLOAD_MAX_MEMORY_SIZE = 1 * 1024 * 1024            # 1 MB: anything bigger streams to disk
DATA_UPLOAD_MAX_NUMBER_FIELDS = None                     # unbounded form fields (form will only carry the file)
FILE_UPLOAD_HANDLERS = [
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]


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
MAILERSEND_API_URL = config("MAILERSEND_API_URL", default="https://api.mailersend.com/v1/email")
MAILERSEND_FROM_EMAIL = config("MAILERSEND_FROM_EMAIL", default="noreply@fontesin.com")
MAILERSEND_FROM_NAME = config("MAILERSEND_FROM_NAME", default="FONTESIN")

VERIFF_API_KEY = config("VERIFF_API_KEY")
VERIFF_MASTER_SECRET = config("VERIFF_MASTER_SECRET")
VERIFF_BASE_URL= config("VERIFF_BASE_URL")
VERIFF_WEBHOOK_SECRET = config("VERIFF_WEBHOOK_SECRET")
VERIFF_CALLBACK_URL = config("VERIFF_CALLBACK_URL", default="http://127.0.0.1:8000/membership/")

# LOCAL TESTING ONLY. When True, identity verification is bypassed: new
# registrations are auto-marked "approved" and the RequireIdentityVerification
# middleware lets everyone through, so you can register/test without a working
# Veriff webhook (which can't reach localhost). Defaults to False — never turn
# this on in production, or the Veriff gate is disabled platform-wide. Enable
# locally via VERIFF_BYPASS=True in your .env.
VERIFF_BYPASS = config("VERIFF_BYPASS", default="False").lower() == "true"