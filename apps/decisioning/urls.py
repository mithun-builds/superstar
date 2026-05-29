"""Decisioning endpoints — mounted under /api/."""
from __future__ import annotations

from django.urls import path

from .views import DecisionByTaskView

app_name = "decisioning"

urlpatterns = [
    path("decisions/by-task/<uuid:task_id>/", DecisionByTaskView.as_view(), name="by-task"),
]
