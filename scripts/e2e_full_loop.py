#!/usr/bin/env python
"""End-to-end smoke against the running Django stack.

Drives the full UI-equivalent flow programmatically via DRF's APIClient:

  1. authenticate as the demo admin
  2. create a TicketType + fields + stages via /api/admin/...
  3. add a KB rule (triggers BGE-M3 embedding)
  4. discover the ticket type via /api/tickets/plugins/  (the requester-side view)
  5. submit a ticket via /api/tickets/
  6. run /decide/ (will use LLM_PROVIDER=noop → returns 'escalate')
  7. check that the approval chain materialized
  8. approve stage 1 → ticket transitions
  9. dump the audit trail

Run with the same env vars as runserver. Exits non-zero on any step failure.
"""
from __future__ import annotations

import os
import sys

# Bootstrap Django.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from rest_framework.test import APIClient  # noqa: E402

from apps.audit.models import AuditEvent  # noqa: E402
from apps.tenants.models import Org  # noqa: E402

GREEN, RED, BOLD, DIM, RESET = "\033[32m", "\033[31m", "\033[1m", "\033[2m", "\033[0m"
ORG_SLUG = "demo"
ADMIN_EMAIL = "admin@local.test"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def step(msg: str) -> None:
    print(f"\n{BOLD}{msg}{RESET}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")
    sys.exit(1)


def main() -> int:
    User = get_user_model()
    admin = User.objects.get(email=ADMIN_EMAIL)
    Org.objects.get(slug=ORG_SLUG)  # confirm tenant exists

    client = APIClient()
    client.force_authenticate(user=admin)
    headers = {"HTTP_X_ORG_SLUG": ORG_SLUG}

    # -------------------------------------------------------------------
    step("1. /api/me/ — current user + memberships")
    # -------------------------------------------------------------------
    r = client.get("/api/me/")
    assert r.status_code == 200, r.content
    me = r.json()
    ok(f"email={me['email']}, {len(me['memberships'])} membership(s)")
    assert any(m["org_slug"] == ORG_SLUG for m in me["memberships"]), "demo membership missing"

    # -------------------------------------------------------------------
    step("2. Create TicketType via /api/admin/")
    # -------------------------------------------------------------------
    r = client.post(
        "/api/admin/ticket-types/",
        {
            "identifier": "demo.access-request",
            "display_name": "Demo Access Request",
            "description": "Generic access workflow for the e2e smoke.",
            "sequential": True,
            "ai_enabled": True,
            "confidence_threshold": 0.85,
            "require_citation": True,
            "shadow_mode": False,  # so /decide/ actually applies the decision
            "system_prompt": (
                "You are Superstar's decisioning engine. Given a request payload and "
                "retrieved rule chunks, output exactly one JSON object — nothing else.\n\n"
                "Schema (every field required):\n"
                '{"decision": "approve"|"reject"|"escalate", "cited_rule_ids": ["..."], '
                '"confidence": 0.0, "reason_text": "...", "price_delta": 0, "post_actions": []}\n\n'
                "Rules:\n"
                "1. If a retrieved rule clearly applies → approve/reject with that rule_id cited.\n"
                "2. If no retrieved rule applies → escalate with cited_rule_ids: [] and confidence ≤ 0.5.\n"
                "3. Cite only rule_ids that appear verbatim in retrieved chunks.\n"
                "4. `decision` MUST be one of approve | reject | escalate — never null, never empty."
            ),
            "is_active": True,
        },
        format="json",
        **headers,
    )
    if r.status_code != 201:
        fail(f"ticket-type create failed: {r.status_code} {r.content}")
    tt_id = r.json()["id"]
    ok(f"ticket-type id={tt_id[:8]}…")

    # -------------------------------------------------------------------
    step("3. Add fields")
    # -------------------------------------------------------------------
    for f in [
        {"order": 0, "name": "requester_role", "field_type": "enum",
         "label": "Role", "required": True, "choices": ["engineer", "ops", "finance"]},
        {"order": 1, "name": "justification", "field_type": "text",
         "label": "Justification", "required": True},
    ]:
        r = client.post(f"/api/admin/ticket-types/{tt_id}/fields/", f, format="json", **headers)
        if r.status_code != 201:
            fail(f"field create failed: {r.status_code} {r.content}")
        ok(f"field '{f['name']}' ({f['field_type']})")

    # -------------------------------------------------------------------
    step("4. Add workflow stages")
    # -------------------------------------------------------------------
    for s in [
        {"order": 1, "name": "Security review", "approvers": ["security"], "mode": "any_member"},
        {"order": 2, "name": "Manager sign-off", "approvers": ["manager"], "mode": "any_member"},
    ]:
        r = client.post(f"/api/admin/ticket-types/{tt_id}/stages/", s, format="json", **headers)
        if r.status_code != 201:
            fail(f"stage create failed: {r.status_code} {r.content}")
        ok(f"stage '{s['name']}'")

    # -------------------------------------------------------------------
    step("5. Add a KB rule (will run BGE-M3 embedding — first call is slow)")
    # -------------------------------------------------------------------
    r = client.post(
        f"/api/admin/ticket-types/{tt_id}/rules/",
        {
            "rule_id": "RULE-001",
            "title": "Engineer access — auto-approve",
            "body": "Engineers requesting access can be auto-approved if justification "
                    "is provided. This rule triggers the citation guard.",
            "decision_hint": "approve",
            "price_delta": "0",
            "post_actions": ["Send welcome email"],
            "applies_when": {"requester_role": "engineer"},
        },
        format="json",
        **headers,
    )
    if r.status_code != 201:
        fail(f"rule create failed: {r.status_code} {r.content}")
    ok(f"rule {r.json()['rule_id']} (embedded with BGE-M3)")

    # -------------------------------------------------------------------
    step("6. Plugin discovery — the requester-side view")
    # -------------------------------------------------------------------
    r = client.get("/api/tickets/plugins/", **headers)
    assert r.status_code == 200, r.content
    types = r.json()
    found = next((t for t in types if t["identifier"] == "demo.access-request"), None)
    assert found is not None, "ticket type missing from discovery"
    ok(f"{len(types)} ticket type(s) discovered; demo.access-request has {len(found['fields'])} fields")

    # -------------------------------------------------------------------
    step("7. Submit a ticket")
    # -------------------------------------------------------------------
    r = client.post(
        "/api/tickets/",
        {
            "ticket_type": "demo.access-request",
            "title": "Need access for kernel debugging",
            "payload": {"requester_role": "engineer", "justification": "WFH this week"},
        },
        format="json",
        **headers,
    )
    if r.status_code != 201:
        fail(f"ticket create failed: {r.status_code} {r.content}")
    ticket_id = r.json()["id"]
    ok(f"ticket id={ticket_id[:8]}…")

    # -------------------------------------------------------------------
    step("8. Run /decide/ — outcome depends on the LLM backend")
    # -------------------------------------------------------------------
    r = client.post(f"/api/tickets/{ticket_id}/decide/", **headers)
    if r.status_code != 200:
        fail(f"decide failed: {r.status_code} {r.content}")
    d = r.json()
    ok(f"decision outcome={d['outcome']}, shadow_mode={d['shadow_mode']}, "
       f"cited={d['cited_rule_ids']}")

    # -------------------------------------------------------------------
    step("9. Two branches: auto-decide vs escalate")
    # -------------------------------------------------------------------
    if d["outcome"] in ("approve", "reject"):
        # Auto-decide: ticket transitions to DECIDED, no chain.
        ticket_after = client.get(f"/api/tickets/{ticket_id}/", **headers).json()
        if ticket_after["status"] != "decided":
            fail(f"auto-{d['outcome']} expected status='decided', got {ticket_after['status']!r}")
        ok(f"ticket auto-{d['outcome']}d → status=decided, no chain materialized (correct)")

        # Audit trail
        events = AuditEvent.objects.filter(subject_id=ticket_id).order_by("created_at")
        for e in events:
            print(f"  {DIM}{e.created_at:%H:%M:%S}{RESET}  {BOLD}{e.event_type}{RESET}  {e.data}")
        if events.count() < 3:
            fail(f"expected ≥3 audit events, got {events.count()}")
        ok(f"{events.count()} audit events recorded")
        print(f"\n{GREEN}{BOLD}All steps passed (auto-decide branch).{RESET}")
        return 0

    if d["outcome"] in ("escalate", "error"):
        # Escalate / error: chain materializes, humans take over.
        r = client.get(f"/api/tickets/{ticket_id}/stages/", **headers)
        assert r.status_code == 200, r.content
        stages = r.json()["stages"]
        if len(stages) != 2:
            fail(f"expected 2 stages on {d['outcome']}, got {len(stages)}: {stages}")
        ok(f"{len(stages)} stages materialized; active={r.json()['active_stage_id'][:8]}…")

        # Approve stage 1
        r = client.post(
            f"/api/tickets/{ticket_id}/stages/{stages[0]['id']}/decide/",
            {"decision": "approved", "note": "Looks fine."},
            format="json",
            **headers,
        )
        if r.status_code != 200:
            fail(f"stage decide failed: {r.status_code} {r.content}")
        out = r.json()
        ok(f"stage 1 approved; ticket_status={out['ticket_status']}; next_stage={out['next_stage']['name']}")

        # Audit trail
        events = AuditEvent.objects.filter(subject_id=ticket_id).order_by("created_at")
        for e in events:
            print(f"  {DIM}{e.created_at:%H:%M:%S}{RESET}  {BOLD}{e.event_type}{RESET}  {e.data}")
        if events.count() < 5:
            fail(f"expected ≥5 audit events on the escalate path, got {events.count()}")
        ok(f"{events.count()} audit events recorded")
        print(f"\n{GREEN}{BOLD}All steps passed (escalate branch).{RESET}")
        return 0

    fail(f"unrecognized outcome: {d['outcome']!r}")


if __name__ == "__main__":
    sys.exit(main())
