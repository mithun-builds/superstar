"""Tests for the platform-level org endpoints.

Coverage:
- Superusers can list + create + delete orgs.
- Regular org admins / owners get 403 (the platform endpoints are NOT
  the same surface as /api/admin/, where org admins ARE allowed).
- Anonymous users get 401/403.
- Create flow mirrors create_tenant exactly:
    * Slug uniqueness enforced
    * Owner provisioning: reuse existing user OR create new (password
      required for new users)
- An audit event is written when orgs are created / deleted.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.audit.models import AuditEvent
from apps.tenants.models import Org, OrgMembership

pytestmark = pytest.mark.django_db

User = get_user_model()
URL_ORGS = "/api/platform/orgs/"


# ---------------------------------------------------------------------------
# Permission gating — only superusers see these endpoints
# ---------------------------------------------------------------------------
def test_anonymous_cannot_list(anon_client) -> None:
    resp = anon_client.get(URL_ORGS)
    assert resp.status_code in (401, 403)


def test_org_admin_cannot_list_platform_orgs(client_factory, acme_admin) -> None:
    # Admin of acme — should NOT be able to peek at all the other orgs on
    # the platform. This is the contract.
    resp = client_factory(acme_admin).get(URL_ORGS)
    assert resp.status_code == 403


def test_org_owner_cannot_create_org(client_factory, acme_owner) -> None:
    resp = client_factory(acme_owner).post(
        URL_ORGS,
        {"slug": "new-co", "name": "New Co"},
        format="json",
    )
    assert resp.status_code == 403


def test_superuser_can_list(client_factory, superuser, acme_org, globex_org) -> None:
    resp = client_factory(superuser).get(URL_ORGS)
    assert resp.status_code == 200
    slugs = {o["slug"] for o in resp.json()}
    assert {"acme", "globex"} <= slugs


# ---------------------------------------------------------------------------
# Create path — mirrors create_tenant
# ---------------------------------------------------------------------------
def test_create_org_minimal(client_factory, superuser) -> None:
    resp = client_factory(superuser).post(
        URL_ORGS,
        {"slug": "newco", "name": "New Co"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["slug"] == "newco" and body["name"] == "New Co"
    assert body["member_count"] == 0
    assert Org.objects.filter(slug="newco").exists()


def test_create_org_with_new_owner(client_factory, superuser) -> None:
    """If owner_email isn't an existing user, owner_password creates one."""
    resp = client_factory(superuser).post(
        URL_ORGS,
        {
            "slug": "acme2",
            "name": "Acme 2",
            "owner_email": "founder@acme2.test",
            "owner_password": "supersecret123",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    org = Org.objects.get(slug="acme2")
    owner = User.objects.get(email="founder@acme2.test")
    assert OrgMembership.objects.filter(
        org=org, user=owner, role=OrgMembership.Role.OWNER,
    ).exists()
    assert resp.json()["member_count"] == 1
    # Password actually set (not the raw string).
    assert owner.check_password("supersecret123")


def test_create_org_reuses_existing_owner(client_factory, superuser, acme_admin) -> None:
    """Owner email matches an existing user → no new user created, just a
    fresh OrgMembership."""
    pre_users = User.objects.count()
    resp = client_factory(superuser).post(
        URL_ORGS,
        {
            "slug": "acme3",
            "name": "Acme 3",
            "owner_email": acme_admin.email,
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert User.objects.count() == pre_users  # no new user
    new_org = Org.objects.get(slug="acme3")
    assert OrgMembership.objects.filter(
        org=new_org, user=acme_admin, role=OrgMembership.Role.OWNER,
    ).exists()


def test_create_org_new_owner_requires_password(client_factory, superuser) -> None:
    resp = client_factory(superuser).post(
        URL_ORGS,
        {
            "slug": "x",
            "name": "X",
            "owner_email": "nobody@example.com",
            # owner_password intentionally missing
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "owner_password" in resp.json()
    # Org NOT created — POST is atomic.
    assert not Org.objects.filter(slug="x").exists()


def test_create_org_duplicate_slug_rejected(
    client_factory, superuser, acme_org,
) -> None:
    resp = client_factory(superuser).post(
        URL_ORGS,
        {"slug": "acme", "name": "Acme dup"},
        format="json",
    )
    assert resp.status_code == 400
    assert "slug" in resp.json()


def test_create_org_writes_audit_event(client_factory, superuser) -> None:
    """A `tenant_created` audit event lands on the new org so the action
    is traceable later."""
    client_factory(superuser).post(
        URL_ORGS,
        {"slug": "auditme", "name": "Audit Me"},
        format="json",
    )
    org = Org.objects.get(slug="auditme")
    assert AuditEvent.objects.filter(
        org=org, data__action="tenant_created",
    ).exists()


# ---------------------------------------------------------------------------
# Delete path
# ---------------------------------------------------------------------------
def test_superuser_can_delete_org(client_factory, superuser) -> None:
    org = Org.objects.create(slug="goner", name="Goner")
    resp = client_factory(superuser).delete(f"{URL_ORGS}{org.id}/")
    assert resp.status_code == 204
    assert not Org.objects.filter(pk=org.pk).exists()
    assert AuditEvent.objects.filter(data__action="tenant_deleted").exists()


def test_org_admin_cannot_delete_other_orgs_org(
    client_factory, acme_admin, globex_org,
) -> None:
    resp = client_factory(acme_admin).delete(f"{URL_ORGS}{globex_org.id}/")
    assert resp.status_code == 403
    assert Org.objects.filter(pk=globex_org.pk).exists()  # still there
