"""SuperStar base Django settings.

Read by dev.py / prod.py and overridden where necessary. All env-driven values
land here so per-env files stay minimal.
"""
from __future__ import annotations

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    CORS_ALLOWED_ORIGINS=(list, []),
    DECISIONING_CONFIDENCE_THRESHOLD=(float, 0.85),
    DECISIONING_SHADOW_MODE=(bool, True),
    EMAIL_ENABLED=(bool, False),
)
# Load .env if present (no-op if not — env vars from the shell still win).
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-secret-do-not-use")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    # SuperStar apps
    "apps.accounts",
    "apps.tenants",
    "apps.tickets",
    "apps.kb",
    "apps.decisioning",
    "apps.audit",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # SuperStar — resolves current org from path / subdomain and stores on request.
    "superstar.middleware.tenant.TenantMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
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

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database (Postgres + pgvector)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        **env.db("DATABASE_URL"),
        "OPTIONS": {
            # Enables RLS-aware connection setup. Tenant context is set per request
            # via `SET LOCAL app.org_id = '...'` in TenantMiddleware.
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# i18n / tz
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("REDIS_URL")
CELERY_RESULT_BACKEND = env("REDIS_URL")
# Eager mode runs tasks inline (no worker required) — set CELERY_TASK_ALWAYS_EAGER=true
# for tests or for local dev when you don't want to start a worker. In prod
# leave it false so /decide/ actually returns 202 + offloads the LLM call.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = True  # tests want to see exceptions, not swallow them
CELERY_TIMEZONE = "UTC"

# ---------------------------------------------------------------------------
# SuperStar — LLM
# ---------------------------------------------------------------------------
LLM = {
    "PROVIDER": env("LLM_PROVIDER", default="ollama"),
    "BASE_URL": env("LLM_BASE_URL", default="http://localhost:11434"),
    "MODEL": env("LLM_MODEL", default="qwen2.5:7b-instruct-q4_K_M"),
    "API_KEY": env("LLM_API_KEY", default=""),
    "TIMEOUT": env.int("LLM_TIMEOUT_SECONDS", default=120),
}

# ---------------------------------------------------------------------------
# SuperStar — embeddings
# ---------------------------------------------------------------------------
EMBEDDINGS = {
    "MODEL": env("EMBEDDING_MODEL", default="BAAI/bge-m3"),
    "DEVICE": env("EMBEDDING_DEVICE", default="cpu"),
    "DIM": 1024,  # BGE-M3 native dim
}

# ---------------------------------------------------------------------------
# SuperStar — decisioning
# ---------------------------------------------------------------------------
DECISIONING = {
    "CONFIDENCE_THRESHOLD": env("DECISIONING_CONFIDENCE_THRESHOLD"),
    "SHADOW_MODE": env("DECISIONING_SHADOW_MODE"),
}

# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------
EMAIL_ENABLED = env("EMAIL_ENABLED")
# Phase 4 wiring lives here. Outbound SMTP first, then Postal inbound.

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "logging.Formatter",
            "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL", default="INFO"),
    },
}
