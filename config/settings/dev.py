"""Dev settings — relaxed CORS, console email, debug tooling."""
from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Console email until Phase 4 wiring lands.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Looser CORS in dev so the Vite dev server (5173/5174) works without ceremony.
CORS_ALLOW_ALL_ORIGINS = True

# CSRF requires explicit trusted origins for cross-port POSTs (Vite → Django).
# Django won't accept wildcards here — list the concrete dev URLs.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:8000",
]
