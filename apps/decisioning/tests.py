"""Tests for async decisioning dispatch + polling.

Uses CELERY_TASK_ALWAYS_EAGER=True so the Celery task runs inline. That
exercises the same code path as a real worker but without needing a
broker. The exception: this won't catch worker-side bugs that only show
up in true async (e.g. serialization issues with task args). Worth
remembering for future work.

LLM_PROVIDER=noop means the inner decisioning loop returns
escalate-by-policy → guard 1 (no citation) → ESCALATED, which lets the
test assert the full path without an actual model.
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.kb.models import RuleChunk
from apps.tickets.models import (
    Ticket,
    TicketType,
    TicketTypeField,
    WorkflowStage,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _eager_celery():
    """Force CELERY_TASK_ALWAYS_EAGER=True for every test in this module so
    .delay() runs inline. Real worker behavior is exercised separately —
    see the manual smoke in scripts/e2e_full_loop.py."""
    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
    ):
        yield

User = get_user_model()
HDRS = {"HTTP_X_ORG_SLUG": "acme"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def configured_tt(acme_org):
    """A TicketType with one field, one stage, a working system prompt, and
    one rule — enough for the decisioning loop to do real work."""
    tt = TicketType.objects.create(
        org=acme_org,
        identifier="acme.access-request",
        display_name="Access Request",
        sequential=True,
        ai_enabled=True,
        shadow_mode=False,
        confidence_threshold=0.85,
        system_prompt="Decide based on rules. Output JSON.",
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=0, name="role", field_type="enum",
        label="Role", required=True, choices=["engineer"],
    )
    WorkflowStage.objects.create(
        ticket_type=tt, order=1, name="Security review",
        approvers=["security"], mode="any_member",
    )
    RuleChunk.objects.create(
        org=acme_org, plugin_identifier="acme.access-request",
        ticket_type=tt, rule_id="R-1", title="Engineer access",
        body="Engineers are approved.", embedding=[0.0] * 1024,
        extra={"applies_when": {"role": "engineer"}},
    )
    return tt


@pytest.fixture
def acme_ticket(acme_org, acme_admin, configured_tt):
    return Ticket.objects.create(
        org=acme_org,
        requester=acme_admin,
        ticket_type="acme.access-request",
        title="Need VPN",
        payload={"role": "engineer"},
    )


# ---------------------------------------------------------------------------
# Dispatch shape
# ---------------------------------------------------------------------------
def test_decide_returns_202_with_task_id(client_factory, acme_admin, acme_ticket) -> None:
    """POST /decide/ no longer blocks — it returns the Celery task id."""
    resp = client_factory(acme_admin).post(
        f"/api/tickets/{acme_ticket.id}/decide/", **HDRS
    )
    assert resp.status_code == 202, resp.content
    body = resp.json()
    assert body["status"] == "dispatched"
    assert "task_id" in body and uuid.UUID(body["task_id"])
    assert body["poll_url"] == f"/api/decisions/by-task/{body['task_id']}/"


def test_decide_rejects_when_ticket_type_missing(client_factory, acme_admin, acme_org) -> None:
    """No matching ticket type → 400, NOT a 202 + later worker explosion."""
    requester = User.objects.create_user(email="r@x.test", password="pw12345!")
    ticket = Ticket.objects.create(
        org=acme_org, requester=requester,
        ticket_type="nope.gone", title="t", payload={},
    )
    resp = client_factory(acme_admin).post(
        f"/api/tickets/{ticket.id}/decide/", **HDRS
    )
    assert resp.status_code == 400


def test_decide_rejects_when_ai_disabled(
    client_factory, acme_admin, acme_org, configured_tt
) -> None:
    configured_tt.ai_enabled = False
    configured_tt.save()
    ticket = Ticket.objects.create(
        org=acme_org, requester=acme_admin,
        ticket_type="acme.access-request", title="t", payload={"role": "engineer"},
    )
    resp = client_factory(acme_admin).post(
        f"/api/tickets/{ticket.id}/decide/", **HDRS
    )
    assert resp.status_code == 400
    assert "disabled" in resp.json()["detail"].lower()


def test_decide_rejects_empty_system_prompt(
    client_factory, acme_admin, acme_org, configured_tt
) -> None:
    configured_tt.system_prompt = "   "  # whitespace-only
    configured_tt.save()
    ticket = Ticket.objects.create(
        org=acme_org, requester=acme_admin,
        ticket_type="acme.access-request", title="t", payload={"role": "engineer"},
    )
    resp = client_factory(acme_admin).post(
        f"/api/tickets/{ticket.id}/decide/", **HDRS
    )
    assert resp.status_code == 400
    assert "prompt" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Eager-mode end-to-end — the worker writes the Decision before /decide/ returns,
# so polling immediately should see it.
# ---------------------------------------------------------------------------
def test_eager_dispatch_writes_decision_row(client_factory, acme_admin, acme_ticket) -> None:
    """With ALWAYS_EAGER=True, by the time POST returns there's already a
    Decision row stamped with the task_id."""
    from apps.decisioning.models import Decision

    resp = client_factory(acme_admin).post(
        f"/api/tickets/{acme_ticket.id}/decide/", **HDRS
    )
    body = resp.json()

    decision = Decision.objects.get(task_id=body["task_id"])
    assert decision.ticket_id == acme_ticket.id
    assert decision.started_at is not None
    # LLM_PROVIDER=noop returns no citations → guard 1 forces escalate.
    assert decision.outcome == Decision.Outcome.ESCALATED


def test_polling_returns_decision_after_eager_dispatch(
    client_factory, acme_admin, acme_ticket
) -> None:
    """End-to-end: dispatch → poll → get the decision payload."""
    c = client_factory(acme_admin)
    post = c.post(f"/api/tickets/{acme_ticket.id}/decide/", **HDRS)
    task_id = post.json()["task_id"]

    poll = c.get(f"/api/decisions/by-task/{task_id}/", **HDRS)
    assert poll.status_code == 200, poll.content
    body = poll.json()
    assert body["outcome"] == "escalate"
    assert body["task_id"] == task_id


# ---------------------------------------------------------------------------
# Polling endpoint semantics — 202 when no row yet, 200 when ready
# ---------------------------------------------------------------------------
def test_polling_unknown_task_returns_202_pending(client_factory, acme_admin, acme_org) -> None:
    """A poll for a task_id that has no Decision yet → 202 + status:pending.
    The frontend reads 202 as "keep polling" without parsing the body shape."""
    unknown = uuid.uuid4()
    resp = client_factory(acme_admin).get(
        f"/api/decisions/by-task/{unknown}/", **HDRS
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "pending"


def test_polling_other_org_decision_returns_202(
    client_factory, acme_admin, globex_org, configured_tt
) -> None:
    """Decision for globex's task — visible to admin@globex, NOT to admin@acme.
    From acme's perspective: 202 pending (treats it as "not yet" rather than
    leaking the existence of a foreign-org decision)."""
    from apps.decisioning.models import Decision

    requester = User.objects.create_user(email="r@g.test", password="pw12345!")
    globex_ticket = Ticket.objects.create(
        org=globex_org, requester=requester,
        ticket_type="x.t", title="t", payload={},
    )
    task_id = uuid.uuid4()
    Decision.objects.create(
        org=globex_org, ticket=globex_ticket,
        outcome=Decision.Outcome.ESCALATED, confidence=0.0,
        task_id=task_id,
    )

    resp = client_factory(acme_admin).get(
        f"/api/decisions/by-task/{task_id}/", **HDRS
    )
    assert resp.status_code == 202  # invisible to acme


def test_polling_requires_org_context(client_factory, acme_admin) -> None:
    """Without X-Org-Slug, the endpoint returns 400 — there's no way to
    scope the lookup."""
    unknown = uuid.uuid4()
    resp = client_factory(acme_admin).get(f"/api/decisions/by-task/{unknown}/")
    assert resp.status_code == 400
