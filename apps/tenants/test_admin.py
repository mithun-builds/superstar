"""Team + TeamMembership admin REST API tests.

Covers: permission gating (anon / requester / approver / admin / owner /
superuser / cross-org admin), slug validation + uniqueness, cross-org
boundary on the nested members endpoint, and the "user must already be
an org member" guard on adding a TeamMembership.
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.tenants.models import OrgMembership, Team, TeamMembership

User = get_user_model()
pytestmark = pytest.mark.django_db


HDRS = {"HTTP_X_ORG_SLUG": "acme"}


def _team_payload(**overrides) -> dict:
    return {"slug": "security", "name": "Security Review Team", "description": "", **overrides}


# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------
def test_anon_cannot_list(anon_client, acme_org) -> None:
    resp = anon_client.get("/api/admin/teams/", **HDRS)
    assert resp.status_code in (401, 403)


def test_requester_cannot_list(client_factory, acme_requester) -> None:
    resp = client_factory(acme_requester).get("/api/admin/teams/", **HDRS)
    assert resp.status_code == 403


def test_admin_can_create_team(client_factory, acme_admin) -> None:
    resp = client_factory(acme_admin).post(
        "/api/admin/teams/", _team_payload(), format="json", **HDRS
    )
    assert resp.status_code == 201, resp.content
    assert Team.objects.filter(slug="security").exists()


def test_owner_can_create_team(client_factory, acme_owner) -> None:
    resp = client_factory(acme_owner).post(
        "/api/admin/teams/", _team_payload(), format="json", **HDRS
    )
    assert resp.status_code == 201


def test_superuser_bypasses(client_factory, superuser, acme_org) -> None:
    resp = client_factory(superuser).post(
        "/api/admin/teams/", _team_payload(), format="json", **HDRS
    )
    assert resp.status_code == 201


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def test_invalid_slug_rejected(client_factory, acme_admin) -> None:
    c = client_factory(acme_admin)
    for bad in ["UPPER", "has space", "$", "x"]:  # too short, special chars, etc.
        resp = c.post(
            "/api/admin/teams/", _team_payload(slug=bad), format="json", **HDRS
        )
        assert resp.status_code == 400, f"{bad!r} should be rejected"
        assert "slug" in resp.json()


def test_duplicate_slug_within_org_rejected(client_factory, acme_admin) -> None:
    c = client_factory(acme_admin)
    r1 = c.post("/api/admin/teams/", _team_payload(), format="json", **HDRS)
    assert r1.status_code == 201
    r2 = c.post("/api/admin/teams/", _team_payload(), format="json", **HDRS)
    assert r2.status_code == 400
    assert "slug" in r2.json()


def test_same_slug_in_different_orgs_ok(
    client_factory, acme_admin, globex_admin
) -> None:
    """Slug uniqueness is per-org, not global."""
    r1 = client_factory(acme_admin).post(
        "/api/admin/teams/", _team_payload(), format="json", **HDRS
    )
    r2 = client_factory(globex_admin).post(
        "/api/admin/teams/",
        _team_payload(),
        format="json",
        **{"HTTP_X_ORG_SLUG": "globex"},
    )
    assert r1.status_code == 201
    assert r2.status_code == 201


# ---------------------------------------------------------------------------
# Cross-org isolation
# ---------------------------------------------------------------------------
def test_admin_sees_only_own_org_teams(
    client_factory, acme_admin, acme_org, globex_org
) -> None:
    Team.objects.create(org=acme_org, slug="acme-team", name="Acme")
    Team.objects.create(org=globex_org, slug="globex-team", name="Globex")
    resp = client_factory(acme_admin).get("/api/admin/teams/", **HDRS)
    data = resp.json()
    slugs = [t["slug"] for t in (data["results"] if isinstance(data, dict) else data)]
    assert "acme-team" in slugs
    assert "globex-team" not in slugs


def test_cannot_retrieve_other_org_team(
    client_factory, acme_admin, globex_org
) -> None:
    t = Team.objects.create(org=globex_org, slug="x", name="X")
    resp = client_factory(acme_admin).get(f"/api/admin/teams/{t.id}/", **HDRS)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------
@pytest.fixture
def acme_team(acme_org):
    return Team.objects.create(org=acme_org, slug="security", name="Security")


def test_add_member_by_email(client_factory, acme_admin, acme_team, acme_approver) -> None:
    """The approver fixture is already an OrgMembership of acme — should be
    enrollable in the team."""
    resp = client_factory(acme_admin).post(
        f"/api/admin/teams/{acme_team.id}/members/",
        {"user_email": acme_approver.email},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201, resp.content
    assert TeamMembership.objects.filter(team=acme_team, user=acme_approver).exists()


def test_cannot_add_non_org_member_to_team(
    client_factory, acme_admin, acme_team
) -> None:
    """User who isn't in this org can't be enrolled in this org's team."""
    stranger = User.objects.create_user(email="stranger@nowhere.test", password="pw12345!")
    resp = client_factory(acme_admin).post(
        f"/api/admin/teams/{acme_team.id}/members/",
        {"user_email": stranger.email},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 400
    assert "user" in resp.json()


def test_add_member_unknown_email_400(client_factory, acme_admin, acme_team) -> None:
    resp = client_factory(acme_admin).post(
        f"/api/admin/teams/{acme_team.id}/members/",
        {"user_email": "nobody@nowhere.test"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 400


def test_add_member_requires_email_or_user(client_factory, acme_admin, acme_team) -> None:
    resp = client_factory(acme_admin).post(
        f"/api/admin/teams/{acme_team.id}/members/",
        {},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 400


def test_duplicate_membership_rejected(
    client_factory, acme_admin, acme_team, acme_approver
) -> None:
    TeamMembership.objects.create(team=acme_team, user=acme_approver)
    resp = client_factory(acme_admin).post(
        f"/api/admin/teams/{acme_team.id}/members/",
        {"user_email": acme_approver.email},
        format="json",
        **HDRS,
    )
    # Hits the (team, user) UniqueConstraint → 400 from DRF's IntegrityError handler
    assert resp.status_code == 400


def test_list_members(client_factory, acme_admin, acme_team, acme_approver) -> None:
    TeamMembership.objects.create(team=acme_team, user=acme_approver)
    resp = client_factory(acme_admin).get(
        f"/api/admin/teams/{acme_team.id}/members/", **HDRS
    )
    assert resp.status_code == 200
    data = resp.json()
    rows = data["results"] if isinstance(data, dict) else data
    emails = [m["user_email"] for m in rows]
    assert acme_approver.email in emails


def test_delete_member(client_factory, acme_admin, acme_team, acme_approver) -> None:
    m = TeamMembership.objects.create(team=acme_team, user=acme_approver)
    resp = client_factory(acme_admin).delete(
        f"/api/admin/teams/{acme_team.id}/members/{m.id}/", **HDRS
    )
    assert resp.status_code == 204
    assert not TeamMembership.objects.filter(id=m.id).exists()


def test_cannot_access_other_org_team_members(
    client_factory, acme_admin, globex_org
) -> None:
    other = Team.objects.create(org=globex_org, slug="x", name="X")
    resp = client_factory(acme_admin).get(
        f"/api/admin/teams/{other.id}/members/", **HDRS
    )
    assert resp.status_code == 404
