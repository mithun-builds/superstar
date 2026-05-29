"""Integration tests for the ticket API — requires a live Postgres+pgvector.

Validates: org-scoped queryset, plugin-driven payload validation, the
404-on-unknown-tenant path in TenantMiddleware. RLS isolation tests are in
a separate suite (`apps/tenants/test_rls.py`) because they require a
non-superuser DB role to be meaningful.
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.tenants.models import Org, OrgMembership
from superstar.plugins import base as plugins_base
from superstar.plugins.base import (
    AIPolicy,
    FieldSpec,
    PluginContract,
    SchemaSpec,
    StageSpec,
    WorkflowSpec,
)

User = get_user_model()


pytestmark = pytest.mark.django_db


@pytest.fixture
def acme_org() -> Org:
    return Org.objects.create(slug="acme", name="Acme Inc")


@pytest.fixture
def acme_user(acme_org: Org) -> "User":
    u = User.objects.create_user(email="alice@acme.test", password="pw12345!")
    OrgMembership.objects.create(org=acme_org, user=u, role="requester")
    return u


@pytest.fixture(autouse=True)
def register_demo_plugin() -> None:
    """Register a minimal plugin so the serializer can validate payloads."""
    plugins_base._REGISTRY.clear()
    contract = PluginContract(
        identifier="demo.access",
        display_name="Demo Access",
        schema=SchemaSpec(fields=(
            FieldSpec(name="role", type="enum", label="Role", required=True,
                      choices=("engineer", "sales")),
            FieldSpec(name="reason", type="text", label="Reason", required=True),
        )),
        workflow=WorkflowSpec(stages=(
            StageSpec(name="Review", approvers=("security",), mode="any_member"),
        )),
        ai_policy=AIPolicy(),
    )
    plugins_base._REGISTRY["demo.access"] = contract
    yield
    plugins_base._REGISTRY.clear()


def _client_for(user) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def test_create_ticket_happy_path(acme_org, acme_user) -> None:
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


def test_unknown_plugin_rejected(acme_org, acme_user) -> None:
    c = _client_for(acme_user)
    resp = c.post(
        "/api/tickets/",
        {"ticket_type": "nope.gone", "title": "X", "payload": {}},
        format="json",
        HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 400
    assert "ticket_type" in resp.json()


def test_payload_validation_against_plugin_schema(acme_org, acme_user) -> None:
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


def test_cross_org_isolation(acme_org, acme_user) -> None:
    other = Org.objects.create(slug="globex", name="Globex")
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
    """No tenant context → empty queryset (not 500)."""
    c = _client_for(acme_user)
    resp = c.get("/api/tickets/")
    # No X-Org-Slug, no /o/<slug>/ — middleware skips tenant resolution.
    # Viewset's get_queryset returns Ticket.objects.none() because request.org is None.
    assert resp.status_code == 200
    assert resp.json()["count"] == 0


# ---------------------------------------------------------------------------
# Approval chain integration tests
# ---------------------------------------------------------------------------
@pytest.fixture
def multi_stage_plugin() -> None:
    """Replace the demo plugin with a 2-stage workflow."""
    plugins_base._REGISTRY.clear()
    plugins_base._REGISTRY["demo.access"] = PluginContract(
        identifier="demo.access",
        display_name="Demo Access",
        schema=SchemaSpec(fields=(
            FieldSpec(name="role", type="enum", choices=("engineer", "sales")),
        )),
        workflow=WorkflowSpec(stages=(
            StageSpec(name="Security review", approvers=("security",), mode="any_member"),
            StageSpec(name="Manager sign-off", approvers=("manager",), mode="any_member"),
        )),
        ai_policy=AIPolicy(shadow_mode=False),  # actually apply decisions
    )
    yield
    plugins_base._REGISTRY.clear()


def _create_ticket(client, org_slug: str, payload: dict | None = None) -> dict:
    resp = client.post(
        "/api/tickets/",
        {
            "ticket_type": "demo.access",
            "title": "Test ticket",
            "payload": payload or {"role": "engineer"},
        },
        format="json",
        HTTP_X_ORG_SLUG=org_slug,
    )
    assert resp.status_code == 201, resp.content
    return resp.json()


def test_materialize_stages_idempotent(acme_org, acme_user, multi_stage_plugin) -> None:
    """Calling materialize_stages twice creates stages once."""
    from apps.tickets.approval import materialize_stages
    from apps.tickets.models import Ticket

    ticket = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"},
    )
    first = materialize_stages(ticket)
    second = materialize_stages(ticket)
    assert len(first) == 2
    assert [s.id for s in first] == [s.id for s in second]


def test_approve_chain_end_to_end(acme_org, acme_user, multi_stage_plugin) -> None:
    """Approve both stages → ticket transitions to APPROVED + CLOSED."""
    from apps.tickets.approval import materialize_stages
    from apps.tickets.models import Ticket

    t = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"}, status=Ticket.Status.ESCALATED,
    )
    materialize_stages(t)

    c = _client_for(acme_user)
    # GET stages
    resp = c.get(f"/api/tickets/{t.id}/stages/", HTTP_X_ORG_SLUG="acme")
    assert resp.status_code == 200
    stages = resp.json()["stages"]
    assert len(stages) == 2
    assert resp.json()["active_stage_id"] == stages[0]["id"]

    # Approve stage 1
    resp = c.post(
        f"/api/tickets/{t.id}/stages/{stages[0]['id']}/decide/",
        {"decision": "approved", "note": "ok"},
        format="json", HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["stage"]["status"] == "approved"
    assert resp.json()["ticket_status"] == "escalated"  # not yet closed
    assert resp.json()["next_stage"]["name"] == "Manager sign-off"

    # Approve stage 2
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


def test_reject_chain_closes_ticket_immediately(acme_org, acme_user, multi_stage_plugin) -> None:
    """First reject short-circuits the whole chain."""
    from apps.tickets.approval import materialize_stages
    from apps.tickets.models import Ticket

    t = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"}, status=Ticket.Status.ESCALATED,
    )
    stages = materialize_stages(t)

    c = _client_for(acme_user)
    resp = c.post(
        f"/api/tickets/{t.id}/stages/{stages[0].id}/decide/",
        {"decision": "rejected", "note": "not yet"},
        format="json", HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 200
    assert resp.json()["ticket_status"] == "rejected"
    assert resp.json()["next_stage"] is None

    t.refresh_from_db()
    assert t.status == "rejected"
    # Second stage should still be PENDING — it wasn't acted on.
    assert t.stages.get(order=2).status == "pending"


def test_out_of_order_decision_rejected(acme_org, acme_user, multi_stage_plugin) -> None:
    """Sequential workflow forbids skipping ahead."""
    from apps.tickets.approval import materialize_stages
    from apps.tickets.models import Ticket

    t = Ticket.objects.create(
        org=acme_org, requester=acme_user, ticket_type="demo.access",
        title="t", payload={"role": "engineer"}, status=Ticket.Status.ESCALATED,
    )
    stages = materialize_stages(t)

    c = _client_for(acme_user)
    # Try to decide stage 2 before stage 1 is done.
    resp = c.post(
        f"/api/tickets/{t.id}/stages/{stages[1].id}/decide/",
        {"decision": "approved"},
        format="json", HTTP_X_ORG_SLUG="acme",
    )
    assert resp.status_code == 409  # ApprovalError → 409 Conflict
    assert "out-of-order" in resp.json()["detail"].lower()


def test_double_decide_same_stage_rejected(acme_org, acme_user, multi_stage_plugin) -> None:
    from apps.tickets.approval import materialize_stages
    from apps.tickets.models import Ticket

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
def test_ticket_create_writes_audit_event(acme_org, acme_user) -> None:
    from apps.audit.models import AuditEvent

    _create_ticket(_client_for(acme_user), "acme")

    evt = AuditEvent.objects.filter(event_type="ticket.created").first()
    assert evt is not None
    assert evt.org_id == acme_org.id
    assert evt.actor_id == acme_user.id
    assert evt.data["ticket_type"] == "demo.access"


def test_stage_decision_writes_audit_event(acme_org, acme_user, multi_stage_plugin) -> None:
    from apps.audit.models import AuditEvent
    from apps.tickets.approval import materialize_stages
    from apps.tickets.models import Ticket

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


def test_audit_failure_does_not_break_caller(acme_org, acme_user, monkeypatch) -> None:
    """log_event must swallow internal errors — never block the user action."""
    from apps.audit import services as audit_services

    def boom(*a, **k):
        raise RuntimeError("audit storage down")

    monkeypatch.setattr(audit_services.AuditEvent.objects, "create", boom)

    # Ticket create should still succeed even if audit insert errors.
    resp = _create_ticket(_client_for(acme_user), "acme")
    assert "id" in resp
