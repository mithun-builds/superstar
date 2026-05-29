"""Admin REST API tests — TicketType + Fields + Stages.

Covers: permission matrix (anon / requester / approver / admin / owner /
superuser / cross-org admin), validation rules (identifier shape,
confidence bounds, enum-without-choices), CRUD on nested fields and
stages, parent-ownership boundary on nested routes, and the discovery
endpoint's read-only contract.

Runs against a real Postgres test DB (pytest-django provisions it). The
RLS policies are present in the test DB too — but Django connects as a
superuser-ish role by default, so they don't enforce here. The
correctness we exercise in this file is at the ORM + serializer + viewset
level. A separate test suite drops to a non-superuser DB role for real
RLS verification (not yet written).
"""
from __future__ import annotations

import pytest

from .models import TicketType, TicketTypeField, WorkflowStage

pytestmark = pytest.mark.django_db


HDRS = {"HTTP_X_ORG_SLUG": "acme"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _new_tt_payload(**overrides) -> dict:
    base = {
        "identifier": "acme.access-request",
        "display_name": "Access Request",
        "description": "",
        "sequential": True,
        "ai_enabled": True,
        "confidence_threshold": 0.85,
        "require_citation": True,
        "shadow_mode": True,
        "system_prompt": "",
        "is_active": True,
    }
    return {**base, **overrides}


# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------
def test_anon_cannot_list(anon_client, acme_org) -> None:
    resp = anon_client.get("/api/admin/ticket-types/", **HDRS)
    assert resp.status_code in (401, 403)


def test_requester_cannot_list(client_factory, acme_requester) -> None:
    resp = client_factory(acme_requester).get("/api/admin/ticket-types/", **HDRS)
    assert resp.status_code == 403


def test_approver_cannot_list(client_factory, acme_approver) -> None:
    resp = client_factory(acme_approver).get("/api/admin/ticket-types/", **HDRS)
    assert resp.status_code == 403


def test_admin_can_list(client_factory, acme_admin) -> None:
    resp = client_factory(acme_admin).get("/api/admin/ticket-types/", **HDRS)
    assert resp.status_code == 200


def test_owner_can_list(client_factory, acme_owner) -> None:
    resp = client_factory(acme_owner).get("/api/admin/ticket-types/", **HDRS)
    assert resp.status_code == 200


def test_superuser_bypasses(client_factory, superuser, acme_org) -> None:
    """Superuser is not a member of acme but should still pass IsOrgAdmin."""
    resp = client_factory(superuser).get("/api/admin/ticket-types/", **HDRS)
    assert resp.status_code == 200


def test_cross_org_admin_blocked(
    client_factory, globex_admin, acme_org
) -> None:
    """An admin of globex hitting acme's admin URLs is rejected — IsOrgAdmin
    checks membership in the URL's org, not in any org the user happens to
    admin elsewhere."""
    resp = client_factory(globex_admin).get("/api/admin/ticket-types/", **HDRS)
    assert resp.status_code == 403


def test_no_org_context_returns_403(client_factory, acme_admin) -> None:
    """No X-Org-Slug header → no org context → IsOrgAdmin denies."""
    resp = client_factory(acme_admin).get("/api/admin/ticket-types/")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cross-org data isolation
# ---------------------------------------------------------------------------
def test_admin_sees_only_own_org_ticket_types(
    client_factory, acme_admin, acme_org, globex_org
) -> None:
    TicketType.objects.create(org=acme_org, identifier="acme.x", display_name="Acme X")
    TicketType.objects.create(org=globex_org, identifier="globex.x", display_name="Globex X")

    resp = client_factory(acme_admin).get("/api/admin/ticket-types/", **HDRS)
    assert resp.status_code == 200
    data = resp.json()
    ids = [t["identifier"] for t in (data["results"] if isinstance(data, dict) else data)]
    assert "acme.x" in ids
    assert "globex.x" not in ids


def test_admin_cannot_retrieve_other_org_ticket_type(
    client_factory, acme_admin, globex_org
) -> None:
    tt = TicketType.objects.create(org=globex_org, identifier="globex.y", display_name="Y")
    resp = client_factory(acme_admin).get(f"/api/admin/ticket-types/{tt.id}/", **HDRS)
    # 404, not 403 — RLS-style: the row doesn't exist as far as this org is concerned.
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# TicketType create / validation
# ---------------------------------------------------------------------------
def test_admin_can_create_ticket_type(client_factory, acme_admin) -> None:
    resp = client_factory(acme_admin).post(
        "/api/admin/ticket-types/", _new_tt_payload(), format="json", **HDRS
    )
    assert resp.status_code == 201, resp.content
    assert TicketType.objects.filter(identifier="acme.access-request").exists()


def test_invalid_identifier_rejected(client_factory, acme_admin) -> None:
    bad = ["UPPERCASE.x", "has spaces", "x", ".starts-with-dot"]
    c = client_factory(acme_admin)
    for ident in bad:
        resp = c.post(
            "/api/admin/ticket-types/",
            _new_tt_payload(identifier=ident),
            format="json",
            **HDRS,
        )
        assert resp.status_code == 400, f"{ident!r} should have been rejected: {resp.content}"
        assert "identifier" in resp.json()


def test_confidence_threshold_out_of_range_rejected(client_factory, acme_admin) -> None:
    c = client_factory(acme_admin)
    for v in [-0.1, 1.5, 99]:
        resp = c.post(
            "/api/admin/ticket-types/",
            _new_tt_payload(confidence_threshold=v),
            format="json",
            **HDRS,
        )
        assert resp.status_code == 400, f"{v} should have been rejected"
        assert "confidence_threshold" in resp.json()


def test_duplicate_identifier_within_org_rejected(client_factory, acme_admin) -> None:
    c = client_factory(acme_admin)
    r1 = c.post("/api/admin/ticket-types/", _new_tt_payload(), format="json", **HDRS)
    assert r1.status_code == 201
    r2 = c.post("/api/admin/ticket-types/", _new_tt_payload(), format="json", **HDRS)
    # DRF returns 400 with a non_field_errors / unique constraint message
    assert r2.status_code == 400


# ---------------------------------------------------------------------------
# TicketType update / delete
# ---------------------------------------------------------------------------
def test_admin_can_patch_ticket_type(client_factory, acme_admin, acme_org) -> None:
    tt = TicketType.objects.create(org=acme_org, identifier="acme.t", display_name="T")
    resp = client_factory(acme_admin).patch(
        f"/api/admin/ticket-types/{tt.id}/",
        {"display_name": "New Name", "confidence_threshold": 0.9},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 200, resp.content
    tt.refresh_from_db()
    assert tt.display_name == "New Name"
    assert tt.confidence_threshold == 0.9


def test_admin_can_delete_ticket_type(client_factory, acme_admin, acme_org) -> None:
    tt = TicketType.objects.create(org=acme_org, identifier="acme.t", display_name="T")
    resp = client_factory(acme_admin).delete(f"/api/admin/ticket-types/{tt.id}/", **HDRS)
    assert resp.status_code == 204
    assert not TicketType.objects.filter(id=tt.id).exists()


# ---------------------------------------------------------------------------
# Nested fields: CRUD + cross-org boundary
# ---------------------------------------------------------------------------
@pytest.fixture
def acme_tt(acme_org):
    return TicketType.objects.create(org=acme_org, identifier="acme.t", display_name="T")


def test_create_field(client_factory, acme_admin, acme_tt) -> None:
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/fields/",
        {
            "order": 0,
            "name": "role",
            "field_type": "enum",
            "label": "Role",
            "required": True,
            "choices": ["engineer", "sales"],
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201, resp.content
    assert TicketTypeField.objects.filter(ticket_type=acme_tt, name="role").exists()


def test_enum_field_without_choices_rejected(client_factory, acme_admin, acme_tt) -> None:
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/fields/",
        {"order": 0, "name": "role", "field_type": "enum", "label": "Role", "choices": []},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 400
    assert "choices" in resp.json()


def test_field_list_ordered(client_factory, acme_admin, acme_tt) -> None:
    # Inserted out of order — list should sort by `order`.
    TicketTypeField.objects.create(
        ticket_type=acme_tt, order=2, name="b", field_type="string", label="B"
    )
    TicketTypeField.objects.create(
        ticket_type=acme_tt, order=1, name="a", field_type="string", label="A"
    )
    resp = client_factory(acme_admin).get(
        f"/api/admin/ticket-types/{acme_tt.id}/fields/", **HDRS
    )
    assert resp.status_code == 200
    names = [f["name"] for f in (resp.json()["results"] if isinstance(resp.json(), dict) else resp.json())]
    assert names == ["a", "b"]


def test_cannot_post_field_to_other_org_ticket_type(
    client_factory, acme_admin, globex_org
) -> None:
    """The nested URL's ticket_type_pk lookup is scoped to request.org —
    targeting a globex ticket type from an acme request must 404."""
    other = TicketType.objects.create(org=globex_org, identifier="g.t", display_name="G")
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{other.id}/fields/",
        {"order": 0, "name": "x", "field_type": "string", "label": "X"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 404


def test_patch_field(client_factory, acme_admin, acme_tt) -> None:
    f = TicketTypeField.objects.create(
        ticket_type=acme_tt, order=0, name="role", field_type="string", label="Role"
    )
    resp = client_factory(acme_admin).patch(
        f"/api/admin/ticket-types/{acme_tt.id}/fields/{f.id}/",
        {"label": "Updated"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 200
    f.refresh_from_db()
    assert f.label == "Updated"


def test_delete_field(client_factory, acme_admin, acme_tt) -> None:
    f = TicketTypeField.objects.create(
        ticket_type=acme_tt, order=0, name="role", field_type="string", label="Role"
    )
    resp = client_factory(acme_admin).delete(
        f"/api/admin/ticket-types/{acme_tt.id}/fields/{f.id}/", **HDRS
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Nested stages
# ---------------------------------------------------------------------------
def test_create_stage(client_factory, acme_admin, acme_tt) -> None:
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{acme_tt.id}/stages/",
        {"order": 1, "name": "Security review", "approvers": ["security"], "mode": "any_member"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201
    assert WorkflowStage.objects.filter(ticket_type=acme_tt, name="Security review").exists()


def test_stage_list_ordered(client_factory, acme_admin, acme_tt) -> None:
    WorkflowStage.objects.create(ticket_type=acme_tt, order=2, name="Second", approvers=["x"], mode="any_member")
    WorkflowStage.objects.create(ticket_type=acme_tt, order=1, name="First", approvers=["x"], mode="any_member")
    resp = client_factory(acme_admin).get(
        f"/api/admin/ticket-types/{acme_tt.id}/stages/", **HDRS
    )
    names = [s["name"] for s in (resp.json()["results"] if isinstance(resp.json(), dict) else resp.json())]
    assert names == ["First", "Second"]


def test_cannot_post_stage_to_other_org_ticket_type(
    client_factory, acme_admin, globex_org
) -> None:
    other = TicketType.objects.create(org=globex_org, identifier="g.t", display_name="G")
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{other.id}/stages/",
        {"order": 1, "name": "S", "approvers": ["x"], "mode": "any_member"},
        format="json",
        **HDRS,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Discovery endpoint (requester-side)
# ---------------------------------------------------------------------------
def test_discovery_returns_active_ticket_types(client_factory, acme_admin, acme_org) -> None:
    TicketType.objects.create(
        org=acme_org, identifier="acme.live", display_name="Live", is_active=True
    )
    TicketType.objects.create(
        org=acme_org, identifier="acme.dead", display_name="Dead", is_active=False
    )
    resp = client_factory(acme_admin).get("/api/tickets/plugins/", **HDRS)
    assert resp.status_code == 200
    ids = [t["identifier"] for t in resp.json()]
    assert "acme.live" in ids
    assert "acme.dead" not in ids


def test_discovery_field_uses_type_alias(client_factory, acme_admin, acme_tt) -> None:
    """Frontend reads `f.type`, not `f.field_type`. Discovery API must alias."""
    TicketTypeField.objects.create(
        ticket_type=acme_tt,
        order=0,
        name="role",
        field_type="enum",
        label="Role",
        choices=["a", "b"],
    )
    resp = client_factory(acme_admin).get("/api/tickets/plugins/", **HDRS)
    assert resp.status_code == 200
    tt = next(t for t in resp.json() if t["identifier"] == "acme.t")
    field = tt["fields"][0]
    assert "type" in field, f"expected `type` alias, got keys: {list(field)}"
    assert field["type"] == "enum"
    assert "field_type" not in field
