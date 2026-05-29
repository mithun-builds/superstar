"""Project-level pytest fixtures.

Two orgs (acme + globex) with the four membership roles, so any test that
needs to assert cross-org isolation or permission gating can compose
without duplication.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.tenants.models import Org, OrgMembership

User = get_user_model()


# ---------------------------------------------------------------------------
# Orgs
# ---------------------------------------------------------------------------
@pytest.fixture
def acme_org(db) -> Org:
    return Org.objects.create(slug="acme", name="Acme Inc")


@pytest.fixture
def globex_org(db) -> Org:
    return Org.objects.create(slug="globex", name="Globex Corp")


# ---------------------------------------------------------------------------
# Users + memberships (acme)
# ---------------------------------------------------------------------------
def _make_member(org: Org, email: str, role: str):
    user = User.objects.create_user(email=email, password="pw12345!")
    OrgMembership.objects.create(org=org, user=user, role=role)
    return user


@pytest.fixture
def acme_owner(acme_org: Org):
    return _make_member(acme_org, "owner@acme.test", OrgMembership.Role.OWNER)


@pytest.fixture
def acme_admin(acme_org: Org):
    return _make_member(acme_org, "admin@acme.test", OrgMembership.Role.ADMIN)


@pytest.fixture
def acme_approver(acme_org: Org):
    return _make_member(acme_org, "approver@acme.test", OrgMembership.Role.APPROVER)


@pytest.fixture
def acme_requester(acme_org: Org):
    return _make_member(acme_org, "requester@acme.test", OrgMembership.Role.REQUESTER)


# ---------------------------------------------------------------------------
# Users + memberships (globex)
# ---------------------------------------------------------------------------
@pytest.fixture
def globex_admin(globex_org: Org):
    return _make_member(globex_org, "admin@globex.test", OrgMembership.Role.ADMIN)


# ---------------------------------------------------------------------------
# Platform superuser (bypasses IsOrgAdmin)
# ---------------------------------------------------------------------------
@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(email="root@local.test", password="pw12345!")


# ---------------------------------------------------------------------------
# Authenticated API clients
# ---------------------------------------------------------------------------
@pytest.fixture
def client_factory():
    """Build an authenticated APIClient for a given user."""
    def _make(user) -> APIClient:
        c = APIClient()
        c.force_authenticate(user=user)
        return c
    return _make


@pytest.fixture
def anon_client() -> APIClient:
    return APIClient()
