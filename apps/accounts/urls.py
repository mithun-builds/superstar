"""Account API URLs — mounted under /api/."""
from __future__ import annotations

from django.urls import path

from .views import MeView

app_name = "accounts"

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
]
