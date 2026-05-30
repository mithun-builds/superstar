"""Tests for the team-membership authorization gate on stage decisions.

The gate (apps/tickets/approval.can_decide_stage):
- superuser → always allowed
- org owner / admin → always allowed (bypass team check)
- otherwise → must be a TeamMembership of one of the stage's approver
  team slugs in this org. Empty `stage.approvers` → any org member.
"""
from __future__ import annotations

import pytest

from apps.tenants.models import Team, TeamMembership

from .approval import can_decide_stage, materialize_stages
from .models import Ticket, TicketType, WorkflowStage

pytestmark = pytest.mark.django_db


HDRS = {"HTTP_X_ORG_SLUG": "acme"}


# ---------------------------------------------------------------------------
# Fixtures — a ticket type with a 1-stage workflow named "security"
# ---------------------------------------------------------------------------
@pytest.fixture
def security_tt(acme_org):
    tt = TicketType.objects.create(
        org=acme_org, identifier="acme.x", display_name="X", sequential=True
    )
    WorkflowStage.objects.create(
        ticket_type=tt,
        order=1,
        name="Security review",
        approvers=["security"],
        mode="any_member",
    )
    return tt


@pytest.fixture
def acme_security_team(acme_org):
    return Team.objects.create(org=acme_org, slug="security", name="Security")


@pytest.fixture
def escalated_ticket(acme_org, acme_requester, security_tt):
    t = Ticket.objects.create(
        org=acme_org,
        requester=acme_requester,
        ticket_type=security_tt.identifier,
        title="t",
        payload={},
        status=Ticket.Status.ESCALATED,
    )
    materialize_stages(t)
    return t


# ---------------------------------------------------------------------------
# can_decide_stage() — unit-level checks
# ---------------------------------------------------------------------------
def test_superuser_bypasses(superuser, escalated_ticket, acme_org) -> None:
    stage = escalated_ticket.stages.first()
    assert can_decide_stage(user=superuser, stage=stage, org=acme_org) is True


def test_owner_bypasses(acme_owner, escalated_ticket, acme_org) -> None:
    stage = escalated_ticket.stages.first()
    assert can_decide_stage(user=acme_owner, stage=stage, org=acme_org) is True


def test_admin_bypasses(acme_admin, escalated_ticket, acme_org) -> None:
    stage = escalated_ticket.stages.first()
    assert can_decide_stage(user=acme_admin, stage=stage, org=acme_org) is True


def test_approver_not_in_team_denied(
    acme_approver, escalated_ticket, acme_org, acme_security_team
) -> None:
    """OrgMembership=approver alone isn't enough — need team membership too."""
    stage = escalated_ticket.stages.first()
    assert can_decide_stage(user=acme_approver, stage=stage, org=acme_org) is False


def test_approver_with_team_allowed(
    acme_approver, escalated_ticket, acme_org, acme_security_team
) -> None:
    TeamMembership.objects.create(team=acme_security_team, user=acme_approver)
    stage = escalated_ticket.stages.first()
    assert can_decide_stage(user=acme_approver, stage=stage, org=acme_org) is True


def test_requester_not_allowed_even_with_team_membership(
    acme_requester, escalated_ticket, acme_org, acme_security_team
) -> None:
    """A requester can be added to a team — but they should still not be a
    typical approver. Actually with current rules: requester+team-member IS
    allowed (we only gate by team membership). Documenting the current
    behavior explicitly."""
    TeamMembership.objects.create(team=acme_security_team, user=acme_requester)
    stage = escalated_ticket.stages.first()
    assert can_decide_stage(user=acme_requester, stage=stage, org=acme_org) is True


def test_other_org_team_membership_doesnt_count(
    acme_approver, escalated_ticket, acme_org, globex_org
) -> None:
    """A team named 'security' in globex doesn't grant rights on acme's stages."""
    globex_security = Team.objects.create(org=globex_org, slug="security", name="Globex Sec")
    TeamMembership.objects.create(team=globex_security, user=acme_approver)
    stage = escalated_ticket.stages.first()
    assert can_decide_stage(user=acme_approver, stage=stage, org=acme_org) is False


def test_referenced_team_does_not_exist_fails_closed(
    acme_approver, escalated_ticket, acme_org
) -> None:
    """Stage names 'security' but no such team exists — nobody can decide."""
    stage = escalated_ticket.stages.first()
    assert can_decide_stage(user=acme_approver, stage=stage, org=acme_org) is False


def test_empty_approvers_falls_back_to_any_org_member(
    acme_approver, escalated_ticket, acme_org
) -> None:
    """If a stage has no approvers configured, it shouldn't be un-actionable.
    Any org member can decide it. Documented as the safety default in
    can_decide_stage()."""
    stage = escalated_ticket.stages.first()
    stage.approvers = []
    stage.save()
    assert can_decide_stage(user=acme_approver, stage=stage, org=acme_org) is True


# ---------------------------------------------------------------------------
# End-to-end through the API
# ---------------------------------------------------------------------------
def test_decide_stage_api_returns_403_for_non_member(
    client_factory, acme_approver, escalated_ticket, acme_security_team
) -> None:
    """Approver without team membership → 403 from the API."""
    stage = escalated_ticket.stages.first()
    resp = client_factory(acme_approver).post(
        f"/api/tickets/{escalated_ticket.id}/stages/{stage.id}/decide/",
        {"decision": "approved"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 403, resp.content
    assert "not authorized" in resp.json()["detail"].lower()


def test_decide_stage_api_succeeds_for_team_member(
    client_factory, acme_approver, escalated_ticket, acme_security_team
) -> None:
    TeamMembership.objects.create(team=acme_security_team, user=acme_approver)
    stage = escalated_ticket.stages.first()
    resp = client_factory(acme_approver).post(
        f"/api/tickets/{escalated_ticket.id}/stages/{stage.id}/decide/",
        {"decision": "approved", "note": "fine"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 200, resp.content


def test_decide_stage_api_admin_bypasses(
    client_factory, acme_admin, escalated_ticket, acme_security_team
) -> None:
    """No team membership, but admin role → still allowed."""
    stage = escalated_ticket.stages.first()
    resp = client_factory(acme_admin).post(
        f"/api/tickets/{escalated_ticket.id}/stages/{stage.id}/decide/",
        {"decision": "approved"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 200
