"""Admin KB rule CRUD tests.

The viewset re-embeds rules whenever body, title, or applies_when change.
We mock the embedder to a deterministic 1024-dim vector so tests don't
load BGE-M3 (which is slow and downloads a model on first run). The mock
also lets us assert WHEN re-embedding happens.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.tickets.models import TicketType

from .models import RuleChunk

pytestmark = pytest.mark.django_db


HDRS = {"HTTP_X_ORG_SLUG": "acme"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def acme_tt(acme_org):
    return TicketType.objects.create(org=acme_org, identifier="acme.t", display_name="T")


@pytest.fixture
def fake_embedding():
    """Deterministic 1024-dim 'embedding' so RuleChunk's VectorField accepts it."""
    return [0.1] * 1024


@pytest.fixture
def mock_embed(fake_embedding):
    """Mock the BGE-M3 embedder used by apps.kb.views — patches the lazy
    import path inside _embed_text. Yields the mock so tests can assert
    call counts.
    """
    with patch("apps.decisioning.embedding.embed", return_value=fake_embedding) as m:
        yield m


# ---------------------------------------------------------------------------
# Permission gating (mirrors test_admin.py for ticket types)
# ---------------------------------------------------------------------------
def test_anon_cannot_list_rules(anon_client, acme_tt) -> None:
    resp = anon_client.get(f"/api/admin/ticket-types/{acme_tt.id}/rules/", **HDRS)
    assert resp.status_code in (401, 403)


def test_requester_cannot_list_rules(client_factory, acme_requester, acme_tt) -> None:
    resp = client_factory(acme_requester).get(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/", **HDRS
    )
    assert resp.status_code == 403


def test_admin_can_list_rules(client_factory, acme_admin, acme_tt) -> None:
    resp = client_factory(acme_admin).get(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/", **HDRS
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cross-org boundary on the parent ticket_type lookup
# ---------------------------------------------------------------------------
def test_cannot_list_rules_on_other_org_ticket_type(
    client_factory, acme_admin, globex_org
) -> None:
    other = TicketType.objects.create(
        org=globex_org, identifier="g.t", display_name="G"
    )
    resp = client_factory(acme_admin).get(
        f"/api/admin/ticket-types/{other.id}/rules/", **HDRS
    )
    assert resp.status_code == 404


def test_cannot_create_rule_on_other_org_ticket_type(
    client_factory, acme_admin, globex_org, mock_embed
) -> None:
    other = TicketType.objects.create(
        org=globex_org, identifier="g.t", display_name="G"
    )
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{other.id}/rules/",
        {"rule_id": "R-1", "title": "X", "body": "..."},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 404
    assert mock_embed.call_count == 0


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def test_create_rule_embeds(client_factory, acme_admin, acme_tt, mock_embed) -> None:
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/",
        {
            "rule_id": "RULE-001",
            "title": "Engineer access",
            "body": "Engineers requesting access can be auto-approved.",
            "decision_hint": "approve",
            "price_delta": "0",
            "post_actions": ["Send welcome email"],
            "applies_when": {"requester_role": "engineer"},
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201, resp.content
    assert mock_embed.call_count == 1
    rule = RuleChunk.objects.get(ticket_type=acme_tt, rule_id="RULE-001")
    assert rule.org_id == acme_tt.org_id
    assert rule.plugin_identifier == acme_tt.identifier
    # applies_when round-trips through extra
    assert rule.extra.get("applies_when") == {"requester_role": "engineer"}


def test_rule_applies_when_round_trip(client_factory, acme_admin, acme_tt, mock_embed) -> None:
    """applies_when in → out without mangling."""
    aw = {"width_mm": {"gte": 350}, "finish": {"not_in": ["PU", "Membrane"]}}
    client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/",
        {"rule_id": "R-1", "title": "T", "body": "B", "applies_when": aw},
        format="json",
        **HDRS,
    )
    rule = RuleChunk.objects.get(rule_id="R-1")
    assert rule.extra["applies_when"] == aw

    # GET round-trip
    resp = client_factory(acme_admin).get(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/{rule.id}/", **HDRS
    )
    assert resp.json()["applies_when"] == aw


# ---------------------------------------------------------------------------
# Re-embedding policy on update
# ---------------------------------------------------------------------------
def test_patch_body_triggers_reembed(client_factory, acme_admin, acme_tt, mock_embed) -> None:
    client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/",
        {"rule_id": "R-1", "title": "T", "body": "original body"},
        format="json",
        **HDRS,
    )
    rule = RuleChunk.objects.get(rule_id="R-1")
    assert mock_embed.call_count == 1  # one for create

    resp = client_factory(acme_admin).patch(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/{rule.id}/",
        {"body": "new body content"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 200
    assert mock_embed.call_count == 2  # re-embedded on body change


def test_patch_title_triggers_reembed(client_factory, acme_admin, acme_tt, mock_embed) -> None:
    client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/",
        {"rule_id": "R-1", "title": "Original title", "body": "B"},
        format="json",
        **HDRS,
    )
    rule = RuleChunk.objects.get(rule_id="R-1")
    assert mock_embed.call_count == 1

    client_factory(acme_admin).patch(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/{rule.id}/",
        {"title": "Renamed"},
        format="json",
        **HDRS,
    )
    assert mock_embed.call_count == 2


def test_patch_applies_when_triggers_reembed(client_factory, acme_admin, acme_tt, mock_embed) -> None:
    client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/",
        {"rule_id": "R-1", "title": "T", "body": "B", "applies_when": {"x": 1}},
        format="json",
        **HDRS,
    )
    rule = RuleChunk.objects.get(rule_id="R-1")
    assert mock_embed.call_count == 1

    client_factory(acme_admin).patch(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/{rule.id}/",
        {"applies_when": {"x": 2}},
        format="json",
        **HDRS,
    )
    assert mock_embed.call_count == 2


def test_patch_price_only_does_NOT_reembed(client_factory, acme_admin, acme_tt, mock_embed) -> None:
    """Editing price/post-actions doesn't change what the LLM sees at
    retrieval time — no need to recompute the embedding."""
    client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/",
        {"rule_id": "R-1", "title": "T", "body": "B", "price_delta": "0"},
        format="json",
        **HDRS,
    )
    rule = RuleChunk.objects.get(rule_id="R-1")
    assert mock_embed.call_count == 1

    resp = client_factory(acme_admin).patch(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/{rule.id}/",
        {"price_delta": "100"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 200
    # No re-embed for frontmatter-only changes.
    assert mock_embed.call_count == 1


def test_patch_post_actions_only_does_NOT_reembed(client_factory, acme_admin, acme_tt, mock_embed) -> None:
    client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/",
        {"rule_id": "R-1", "title": "T", "body": "B", "post_actions": []},
        format="json",
        **HDRS,
    )
    rule = RuleChunk.objects.get(rule_id="R-1")
    assert mock_embed.call_count == 1

    client_factory(acme_admin).patch(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/{rule.id}/",
        {"post_actions": ["Notify ops"]},
        format="json",
        **HDRS,
    )
    assert mock_embed.call_count == 1


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
def test_delete_rule(client_factory, acme_admin, acme_tt, mock_embed) -> None:
    client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/",
        {"rule_id": "R-1", "title": "T", "body": "B"},
        format="json",
        **HDRS,
    )
    rule = RuleChunk.objects.get(rule_id="R-1")
    resp = client_factory(acme_admin).delete(
        f"/api/admin/ticket-types/{acme_tt.id}/rules/{rule.id}/", **HDRS
    )
    assert resp.status_code == 204
    assert not RuleChunk.objects.filter(id=rule.id).exists()
