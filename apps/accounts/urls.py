"""Account API URLs — mounted under /api/."""
from __future__ import annotations

from django.urls import path

from .views import LoginView, LogoutView, MeView

app_name = "accounts"

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
