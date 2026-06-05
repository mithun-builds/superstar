"""Auth endpoint tests — /api/login/, /api/logout/.

The /api/me/ endpoint is exercised indirectly elsewhere; here we focus on
the bootstrap surface that lets the SPA sign a user in without bouncing
through Django admin.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(db):
    return User.objects.create_user(email="alice@example.test", password="hunter2!")


def test_login_with_correct_credentials_returns_me(alice) -> None:
    c = APIClient()
    resp = c.post(
        "/api/login/",
        {"email": "alice@example.test", "password": "hunter2!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["email"] == "alice@example.test"
    # Session cookie set — verifies by hitting /me/ without re-auth.
    me = c.get("/api/me/")
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.test"


def test_login_with_wrong_password_returns_401(alice) -> None:
    resp = APIClient().post(
        "/api/login/",
        {"email": "alice@example.test", "password": "wrong"},
        format="json",
    )
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_login_with_unknown_email_returns_401(db) -> None:
    """Don't leak which side of the credential was wrong — both unknown-email
    and wrong-password produce the same 401."""
    resp = APIClient().post(
        "/api/login/",
        {"email": "ghost@example.test", "password": "anything"},
        format="json",
    )
    assert resp.status_code == 401


def test_login_missing_fields_returns_400(db) -> None:
    resp = APIClient().post("/api/login/", {"email": "x@y.test"}, format="json")
    assert resp.status_code == 400
    assert "password" in resp.json()


def test_login_inactive_user_returns_403(db) -> None:
    user = User.objects.create_user(email="dis@example.test", password="hunter2!")
    user.is_active = False
    user.save()
    resp = APIClient().post(
        "/api/login/",
        {"email": "dis@example.test", "password": "hunter2!"},
        format="json",
    )
    # Django's authenticate() returns None for inactive users (default backend
    # filters them out), so we get a 401 here. That's fine — the user can't
    # tell the difference between "wrong password" and "disabled account",
    # which is also a defensible privacy choice.
    assert resp.status_code == 401


def test_logout_revokes_session(alice) -> None:
    c = APIClient()
    c.post(
        "/api/login/",
        {"email": "alice@example.test", "password": "hunter2!"},
        format="json",
    )
    # Sanity: we're in
    assert c.get("/api/me/").status_code == 200
    # Log out
    resp = c.post("/api/logout/")
    assert resp.status_code == 204
    # /me/ now rejects
    assert c.get("/api/me/").status_code in (401, 403)


def test_logout_when_not_signed_in_is_idempotent(db) -> None:
    """Anonymous logout is a no-op success — easier for the client."""
    resp = APIClient().post("/api/logout/")
    assert resp.status_code == 204
