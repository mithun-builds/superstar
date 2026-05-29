"""Postgres Row-Level Security verification.

We've claimed multi-tenant isolation throughout the codebase. The migrations
create `tenant_isolation` policies on every tenant-scoped table. The Django
TenantMiddleware sets `app.org_id` per request. ORM-level cross-org tests
exist in apps/tickets/tests.py + apps/tickets/test_admin.py.

But Django's default DB connection runs as a Postgres role with `BYPASSRLS`,
so all of those tests pass *whether or not the policies engage*. This file
closes that gap by opening a separate psycopg connection AS a non-superuser
role and asserting Postgres really does enforce the policies for that role.

If these tests pass, the claim "tenant_isolation is enforced at the DB level"
is real. If they fail, every other cross-org test in the suite is also
unsafe (it just looks isolated because of app-layer filters).

Each test follows the same pattern:
  1. Insert tenant data via the Django ORM (superuser; not affected by RLS).
  2. Open the non-superuser psycopg connection (the `rls_conn` fixture).
  3. Set `app.org_id` to one tenant, run a query, assert the other tenant's
     data is invisible / inaccessible.
"""
from __future__ import annotations

import uuid

import psycopg
import pytest
from django.contrib.auth import get_user_model

from apps.audit.models import AuditEvent
from apps.kb.models import RuleChunk
from apps.tenants.models import Org
from apps.tickets.models import Ticket, TicketType

# RLS testing needs ORM inserts to be visible to the separate psycopg
# connection — pytest-django's default `django_db` mark wraps each test
# in a transaction that the second connection can't see. `transaction=True`
# disables that wrapper and TRUNCATES tables between tests instead.
pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _set_org(conn, org_id: uuid.UUID | None) -> None:
    """Bind app.org_id on the connection. Mirrors what TenantMiddleware does."""
    with conn.cursor() as cur:
        cur.execute("SELECT set_config('app.org_id', %s, false)", [str(org_id) if org_id else ""])


def _commit(conn) -> None:
    """psycopg defaults to a transaction; close it so subsequent SELECTs
    see committed inserts. Tests use this between setup + assert."""
    conn.commit()


@pytest.fixture
def two_orgs_with_tickets(acme_org, globex_org):
    """Seed two orgs with one ticket each (via Django ORM = superuser, bypasses RLS).

    Returns (acme_ticket_id, globex_ticket_id).
    """
    requester = User.objects.create_user(email="r@x.test", password="pw12345!")
    tt_acme = TicketType.objects.create(org=acme_org, identifier="a.t", display_name="A")
    tt_globex = TicketType.objects.create(org=globex_org, identifier="g.t", display_name="G")
    acme_ticket = Ticket.objects.create(
        org=acme_org, requester=requester, ticket_type="a.t", title="Acme thing", payload={},
    )
    globex_ticket = Ticket.objects.create(
        org=globex_org, requester=requester, ticket_type="g.t", title="Globex thing", payload={},
    )
    return acme_ticket.id, globex_ticket.id, tt_acme, tt_globex


# ---------------------------------------------------------------------------
# SELECT — visibility under different app.org_id contexts
# ---------------------------------------------------------------------------
def test_unset_org_id_sees_no_tickets(two_orgs_with_tickets, rls_conn) -> None:
    """No app.org_id → policy denies all rows. Without this property,
    a forgotten middleware step would leak every org's data."""
    _set_org(rls_conn, None)
    with rls_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tickets_ticket")
        assert cur.fetchone()[0] == 0


def test_acme_org_id_sees_only_acme_tickets(
    two_orgs_with_tickets, acme_org, rls_conn
) -> None:
    acme_id, _, _, _ = two_orgs_with_tickets
    _set_org(rls_conn, acme_org.id)
    with rls_conn.cursor() as cur:
        cur.execute("SELECT id FROM tickets_ticket")
        rows = [r[0] for r in cur.fetchall()]
        assert rows == [acme_id], f"expected only {acme_id}, got {rows}"


def test_globex_org_id_sees_only_globex_tickets(
    two_orgs_with_tickets, globex_org, rls_conn
) -> None:
    _, globex_id, _, _ = two_orgs_with_tickets
    _set_org(rls_conn, globex_org.id)
    with rls_conn.cursor() as cur:
        cur.execute("SELECT id FROM tickets_ticket")
        rows = [r[0] for r in cur.fetchall()]
        assert rows == [globex_id]


def test_switching_org_id_within_session_swaps_visible_rows(
    two_orgs_with_tickets, acme_org, globex_org, rls_conn
) -> None:
    """Same connection, different `app.org_id` → row visibility flips.
    This is the core single-connection-per-request guarantee."""
    acme_id, globex_id, _, _ = two_orgs_with_tickets

    _set_org(rls_conn, acme_org.id)
    with rls_conn.cursor() as cur:
        cur.execute("SELECT id FROM tickets_ticket")
        assert [r[0] for r in cur.fetchall()] == [acme_id]

    _set_org(rls_conn, globex_org.id)
    with rls_conn.cursor() as cur:
        cur.execute("SELECT id FROM tickets_ticket")
        assert [r[0] for r in cur.fetchall()] == [globex_id]


# ---------------------------------------------------------------------------
# INSERT — the WITH CHECK clause rejects writes for other orgs
# ---------------------------------------------------------------------------
def test_cannot_insert_ticket_into_other_org(
    two_orgs_with_tickets, acme_org, globex_org, rls_conn
) -> None:
    """app.org_id=acme but try to INSERT a row with org_id=globex → reject."""
    requester = User.objects.first()
    _, _, tt_acme, _ = two_orgs_with_tickets

    _set_org(rls_conn, acme_org.id)
    with rls_conn.cursor() as cur, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cur.execute(
            "INSERT INTO tickets_ticket "
            "(id, org_id, ticket_type, title, payload, status, decision_summary, "
            " created_at, updated_at, requester_id) "
            "VALUES (gen_random_uuid(), %s, %s, 'forged', '{}', 'open', '', "
            "        NOW(), NOW(), %s)",
            [str(globex_org.id), "a.t", str(requester.id)],
        )


def test_can_insert_ticket_into_own_org(
    two_orgs_with_tickets, acme_org, rls_conn
) -> None:
    requester = User.objects.first()
    _set_org(rls_conn, acme_org.id)
    with rls_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tickets_ticket "
            "(id, org_id, ticket_type, title, payload, status, decision_summary, "
            " created_at, updated_at, requester_id) "
            "VALUES (gen_random_uuid(), %s, %s, 'real', '{}', 'open', '', "
            "        NOW(), NOW(), %s) "
            "RETURNING id",
            [str(acme_org.id), "a.t", str(requester.id)],
        )
        new_id = cur.fetchone()[0]
        assert new_id is not None
    rls_conn.commit()


def test_cannot_insert_without_org_id_set(
    two_orgs_with_tickets, acme_org, rls_conn
) -> None:
    """No app.org_id, no insert — even when the row's own org_id is valid."""
    requester = User.objects.first()
    _set_org(rls_conn, None)
    with rls_conn.cursor() as cur, pytest.raises(psycopg.errors.InsufficientPrivilege):
        cur.execute(
            "INSERT INTO tickets_ticket "
            "(id, org_id, ticket_type, title, payload, status, decision_summary, "
            " created_at, updated_at, requester_id) "
            "VALUES (gen_random_uuid(), %s, %s, 'sneaky', '{}', 'open', '', "
            "        NOW(), NOW(), %s)",
            [str(acme_org.id), "a.t", str(requester.id)],
        )


# ---------------------------------------------------------------------------
# UPDATE / DELETE — cannot reach across orgs
# ---------------------------------------------------------------------------
def test_update_cannot_reach_other_org_row(
    two_orgs_with_tickets, acme_org, rls_conn
) -> None:
    """With app.org_id=acme, an UPDATE against globex's row affects zero rows
    (not an error — the row is just invisible to the policy)."""
    _, globex_id, _, _ = two_orgs_with_tickets

    _set_org(rls_conn, acme_org.id)
    with rls_conn.cursor() as cur:
        cur.execute(
            "UPDATE tickets_ticket SET title = 'hacked' WHERE id = %s",
            [str(globex_id)],
        )
        assert cur.rowcount == 0


def test_delete_cannot_reach_other_org_row(
    two_orgs_with_tickets, acme_org, rls_conn
) -> None:
    _, globex_id, _, _ = two_orgs_with_tickets

    _set_org(rls_conn, acme_org.id)
    with rls_conn.cursor() as cur:
        cur.execute("DELETE FROM tickets_ticket WHERE id = %s", [str(globex_id)])
        assert cur.rowcount == 0


# ---------------------------------------------------------------------------
# RuleChunk + TicketType + AuditEvent each enforce too
# ---------------------------------------------------------------------------
def test_rls_on_kb_rulechunk(acme_org, globex_org, rls_conn) -> None:
    """RuleChunk is the KB-side equivalent — same policy shape, separate test."""
    embedding = [0.0] * 1024
    RuleChunk.objects.create(
        org=acme_org, plugin_identifier="a.t", rule_id="A-1",
        body="acme", embedding=embedding,
    )
    RuleChunk.objects.create(
        org=globex_org, plugin_identifier="g.t", rule_id="G-1",
        body="globex", embedding=embedding,
    )

    _set_org(rls_conn, acme_org.id)
    with rls_conn.cursor() as cur:
        cur.execute("SELECT rule_id FROM kb_rulechunk")
        assert {r[0] for r in cur.fetchall()} == {"A-1"}


def test_rls_on_tickettype_via_org_column(
    two_orgs_with_tickets, acme_org, rls_conn
) -> None:
    """TicketType has its own org_id column; policy is direct."""
    _set_org(rls_conn, acme_org.id)
    with rls_conn.cursor() as cur:
        cur.execute("SELECT identifier FROM tickets_tickettype")
        assert {r[0] for r in cur.fetchall()} == {"a.t"}


def test_rls_on_audit_event_allows_null_org(acme_org, globex_org, rls_conn) -> None:
    """AuditEvent's policy is special — platform-level (NULL org_id) events
    are visible to everyone, plus rows matching app.org_id."""
    AuditEvent.objects.create(event_type="kb.ingested", data={"x": 1})  # org=None
    AuditEvent.objects.create(org=acme_org, event_type="ticket.created", data={"y": 2})
    AuditEvent.objects.create(org=globex_org, event_type="ticket.created", data={"z": 3})

    _set_org(rls_conn, acme_org.id)
    with rls_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit_auditevent")
        # acme's event + the platform-level NULL-org event — but NOT globex's
        assert cur.fetchone()[0] == 2
