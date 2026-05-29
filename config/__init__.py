# Make the Celery app available at Django startup so @shared_task picks it up.
# Without this import, tasks in apps/*/tasks.py won't register and dispatch
# will silently fail with "Received unregistered task".
from .celery import app as celery_app

__all__ = ("celery_app",)
