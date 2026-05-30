"""Integration tests for the ticket API — requires a live Postgres+pgvector.

Validates: org-scoped queryset, DB-native ticket-type validation,
approval chain advancement, audit writes. RLS isolation tests with a
non-superuser DB role live in `apps/tenants/test_rls.py` (not yet written).
"""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.tenants.models import Org, OrgMembership

from .models import Ticket, TicketType, TicketTypeField, WorkflowStage

User = get_user_model()


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def acme_org() -> Org:
    return Org.objects.create(slug="acme", name="Acme Inc")


@pytest.fixture
def acme_user(acme_org: Org) -> "User":
    """Acts as the API caller for the tests in this file. Given admin role so
    these tests (which exercise the state machine + audit log, not the team
    authorization gate) can drive stage decisions without setting up teams.
    The dedicated authorization tests live in test_stage_auth.py."""
    u = User.objects.create_user(email="alice@acme.test", password="pw12345!")
    OrgMembership.objects.create(org=acme_org, user=u, role="admin")
    return u


@pytest.fixture
def demo_ticket_type(acme_org: Org) -> TicketType:
    """Single-stage ticket type with a couple of fields."""
    tt = TicketType.objects.create(
        org=acme_org,
        identifier="demo.access",
        display_name="Demo Access",
        sequential=True,
        ai_enabled=True,
        shadow_mode=True,
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=0, name="role", field_type="enum", label="Role",
        required=True, choices=["engineer", "sales"],
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=1, name="reason", field_type="text", label="Reason",
        required=True,
    )
    WorkflowStage.objects.create(
        ticket_type=tt, order=1, name="Review", approvers=["security"], mode="any_member",
    )
    return tt


@pytest.fixture
def multi_stage_ticket_type(acme_org: Org) -> TicketType:
    """Two-stage ticket type for approval-chain tests."""
    tt = TicketType.objects.create(
        org=acme_org,
        identifier="demo.access",
        display_name="Demo Access",
        sequential=True,
        ai_enabled=True,
        shadow_mode=False,
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=0, name="role", field_type="enum", label="Role",
        required=True, choices=["engineer", "sales"],
    )
    WorkflowStage.objects.create(
        ticket_type=tt, order=1, name="Security review",
        approvers=["security"], mode="any_member",
    )
    WorkflowStage.objects.create(
        ticket_type=tt, order=2, name="Manager sign-off",
        approvers=["manager"], mode="any_member",
    )
    return tt


def _client_for(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


# ---------------------------------------------------------------------------
# Ticket creation + payload validation
# ---------------------------------------------------------------------------
def test_create_ticket_happy_path(acme_user, demo_ticket_type) -> None:
    c = _client_for(acme_user)
    resp = c.post(
        "/api/tickets/",
        {
            "ticket_type": "demo.access",
            "title": "Need VPN access",
            "payload": {"role": "engineer", "reason": "Working from home this week."},
        },
        format="json",
        HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 201, resp.content
    assert resp.json()["status"] == "open"


def test_unknown_ticket_type_rejected(acme_user, acme_org) -> None:
    c = _client_for(acme_user)
    resp = c.post(
        "/api/tickets/",
        {"ticket_type": "nope.gone", "title": "X", "payload": {}},
        format="json",
        HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 400
    assert "ticket_type" in resp.json()


def test_payload_validation_against_ticket_type_schema(acme_user, demo_ticket_type) -> None:
    c = _client_for(acme_user)
    resp = c.post(
        "/api/tickets/",
        {
            "ticket_type": "demo.access",
            "title": "Bad payload",
            "payload": {"role": "marketing", "reason": "test"},  # invalid enum
        },
        format="json",
        HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 400
    assert "payload" in resp.json()


def test_cross_org_isolation(acme_user, demo_ticket_type) -> None:
    other = Org.objects.create(slug="globex", name="Globex")
    # Same ticket-type identifier, but in a different org — should not collide.
    other_tt = TicketType.objects.create(
        org=other, identifier="demo.access", display_name="Demo Access", shadow_mode=True,
    )
    TicketTypeField.objects.create(
        ticket_type=other_tt, name="role", field_type="enum", label="Role",
        choices=["engineer"], required=True, order=0,
    )
    bob = User.objects.create_user(email="bob@globex.test", password="pw12345!")
    OrgMembership.objects.create(org=other, user=bob, role="requester")

    # Alice creates a ticket in acme.
    _client_for(acme_user).post(
        "/api/tickets/",
        {
            "ticket_type": "demo.access",
            "title": "Acme ticket",
            "payload": {"role": "engineer", "reason": "x"},
        },
        format="json",
        HTTP_X_ORG_SLUG="acme",
    )

    # Bob in globex must not see it.
    resp = _client_for(bob).get("/api/tickets/", HTTP_X_ORG_SLUG="globex")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


def test_unknown_org_404(acme_user) -> None:
    c = _client_for(acme_user)
    resp = c.get("/api/tickets/", HTTP_X_ORG_SLUG="does-not-exist")
    assert resp.status_code == 404


def test_no_org_header_returns_empty(acme_user) -> None:
    c = _client_for(acme_user)
    resp = c.get("/api/tickets/")
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


# ---------------------------------------------------------------------------
# Ticket type discovery (/api/tickets/plugins/)
# ---------------------------------------------------------------------------
def test_list_plugins_returns_org_ticket_types(acme_user, demo_ticket_type) -> None:
    """Discovery endpoint reads from DB, not filesystem."""
    resp = _client_for(acme_user).get("/api/tickets/plugins/", HTTP_X_ORG_SLUG="acme")
    assert resp.status_code == 200
    items = resp.json()
    assert any(t["identifier"] == "demo.access" for t in items)
    demo = next(t for t in items if t["identifier"] == "demo.access")
    field_names = [f["name"] for f in demo["fields"]]
    assert field_names == ["role", "reason"]


def test_list_plugins_isolated_per_org(acme_user, demo_ticket_type) -> None:
    """Org A's ticket types must not be visible to org B."""
    globex = Org.objects.create(slug="globex", name="Globex")
    bob = User.objects.create_user(email="bob@globex.test", password="pw12345!")
    OrgMembership.objects.create(org=globex, user=bob, role="admin")

    resp = _client_for(bob).get("/api/tickets/plugins/", HTTP_X_ORG_SLUG="globex")
    assert resp.status_code == 200
    assert resp.json() == []


# ---------------------------------------------------------------------------
# Approval chain integration tests
# ---------------------------------------------------------------------------
def test_materialize_stages_idempotent(acme_org, acme_user, multi_stage_ticket_type) -> None:
    from .approval import materialize_stages

    ticket = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"},
    )
    first = materialize_stages(ticket)
    second = materialize_stages(ticket)
    assert len(first) == 2
    assert [s.id for s in first] == [s.id for s in second]


def test_approve_chain_end_to_end(acme_org, acme_user, multi_stage_ticket_type) -> None:
    from .approval import materialize_stages

    t = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"}, status=Ticket.Status.ESCALATED,
    )
    materialize_stages(t)

    c = _client_for(acme_user)
    resp = c.get(f"/api/tickets/{t.id}/stages/", HTTP_X_ORG_SLUG="acme")
    assert resp.status_code == 200
    stages = resp.json()["stages"]
    assert len(stages) == 2
    assert resp.json()["active_stage_id"] == stages[0]["id"]

    resp = c.post(
        f"/api/tickets/{t.id}/stages/{stages[0]['id']}/decide/",
        {"decision": "approved", "note": "ok"},
        format="json", HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["ticket_status"] == "escalated"
    assert resp.json()["next_stage"]["name"] == "Manager sign-off"

    resp = c.post(
        f"/api/tickets/{t.id}/stages/{stages[1]['id']}/decide/",
        {"decision": "approved"},
        format="json", HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 200
    assert resp.json()["ticket_status"] == "approved"
    assert resp.json()["next_stage"] is None

    t.refresh_from_db()
    assert t.status == "approved"
    assert t.closed_at is not None


def test_reject_chain_closes_ticket_immediately(acme_org, acme_user, multi_stage_ticket_type) -> None:
    from .approval import materialize_stages

    t = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"}, status=Ticket.Status.ESCALATED,
    )
    stages = materialize_stages(t)

    resp = _client_for(acme_user).post(
        f"/api/tickets/{t.id}/stages/{stages[0].id}/decide/",
        {"decision": "rejected", "note": "not yet"},
        format="json", HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 200
    assert resp.json()["ticket_status"] == "rejected"
    assert resp.json()["next_stage"] is None

    t.refresh_from_db()
    assert t.status == "rejected"
    assert t.stages.get(order=2).status == "pending"


def test_out_of_order_decision_rejected(acme_org, acme_user, multi_stage_ticket_type) -> None:
    from .approval import materialize_stages

    t = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"}, status=Ticket.Status.ESCALATED,
    )
    stages = materialize_stages(t)

    resp = _client_for(acme_user).post(
        f"/api/tickets/{t.id}/stages/{stages[1].id}/decide/",
        {"decision": "approved"},
        format="json", HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 409
    assert "out-of-order" in resp.json()["detail"].lower()


def test_double_decide_same_stage_rejected(acme_org, acme_user, multi_stage_ticket_type) -> None:
    from .approval import materialize_stages

    t = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"}, status=Ticket.Status.ESCALATED,
    )
    stages = materialize_stages(t)

    c = _client_for(acme_user)
    c.post(
        f"/api/tickets/{t.id}/stages/{stages[0].id}/decide/",
        {"decision": "approved"}, format="json", HTTP_X_ORG_SLUG="acme",
    )
    resp = c.post(
        f"/api/tickets/{t.id}/stages/{stages[0].id}/decide/",
        {"decision": "rejected"}, format="json", HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 409
    assert "already decided" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Audit log writes
# ---------------------------------------------------------------------------
def test_ticket_create_writes_audit_event(acme_org, acme_user, demo_ticket_type) -> None:
    from apps.audit.models import AuditEvent

    _client_for(acme_user).post(
        "/api/tickets/",
        {
            "ticket_type": "demo.access",
            "title": "t",
            "payload": {"role": "engineer", "reason": "x"},
        },
        format="json",
        HTTP_X_ORG_SLUG="acme",
    )

    evt = AuditEvent.objects.filter(event_type="ticket.created").first()
    assert evt is not None
    assert evt.org_id == acme_org.id
    assert evt.actor_id == acme_user.id
    assert evt.data["ticket_type"] == "demo.access"


def test_stage_decision_writes_audit_event(acme_org, acme_user, multi_stage_ticket_type) -> None:
    from apps.audit.models import AuditEvent

    from .approval import materialize_stages

    t = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"}, status=Ticket.Status.ESCALATED,
    )
    stages = materialize_stages(t)

    _client_for(acme_user).post(
        f"/api/tickets/{t.id}/stages/{stages[0].id}/decide/",
        {"decision": "approved", "note": "lgtm"},
        format="json", HTTP_X_ORG_SLUG="acme",
    )

    evt = AuditEvent.objects.filter(event_type="stage.decided").first()
    assert evt is not None
    assert evt.data["decision"] == "approved"
    assert evt.data["note"] == "lgtm"


def test_audit_failure_does_not_break_caller(acme_user, demo_ticket_type, monkeypatch) -> None:
    """log_event must swallow internal errors — never block the user action."""
    from apps.audit import services as audit_services

    def boom(*a, **k):
        raise RuntimeError("audit storage down")

    monkeypatch.setattr(audit_services.AuditEvent.objects, "create", boom)

    resp = _client_for(acme_user).post(
        "/api/tickets/",
        {
            "ticket_type": "demo.access",
            "title": "t",
            "payload": {"role": "engineer", "reason": "x"},
        },
        format="json",
        HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 201
    assert "id" in resp.json()
