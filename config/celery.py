"""Celery app — discovered by `celery -A config worker`."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

app = Celery("superstar")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
