"""Dev settings — relaxed CORS, console email, debug tooling."""
from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Console email until Phase 4 wiring lands.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Looser CORS in dev so the Vite dev server (5173) works without ceremony.
CORS_ALLOW_ALL_ORIGINS = True
