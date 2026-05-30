"""Tests for show_if + choices_if conditional form fields.

Covers:
- Backend payload validation honors show_if (hidden fields aren't required,
  hidden values are dropped from saved payload)
- choices_if rules: matching rule's choices win; no match → static `choices`
- Admin API can persist + read back the conditional config
- Discovery API exposes show_if + choices_if to the requester-side form
- Validation error when admin sends an enum with neither choices nor choices_if
"""
from __future__ import annotations

import pytest

from apps.tickets.models import Ticket, TicketType, TicketTypeField

pytestmark = pytest.mark.django_db


HDRS = {"HTTP_X_ORG_SLUG": "acme"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def conditional_tt(acme_org):
    """Schema:
       request_type (enum) — always required
       shutter_finish (enum) — required only when request_type=lock or air_vent
       module_width_mm (int) — required only when request_type=air_vent
       sub_category (enum) — choices depend on room_type
       room_type (enum) — always required
    """
    tt = TicketType.objects.create(
        org=acme_org, identifier="acme.cond", display_name="Conditional", shadow_mode=True,
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=0, name="room_type", field_type="enum",
        label="Room type", required=True, choices=["kitchen", "wardrobe"],
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=1, name="request_type", field_type="enum",
        label="Request type", required=True,
        choices=["additional_lock", "air_vent", "remove_fascia"],
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=2, name="shutter_finish", field_type="enum",
        label="Finish", required=True,
        choices=["Laminate", "PU", "Membrane"],
        show_if={"request_type": ["additional_lock", "air_vent"]},
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=3, name="module_width_mm", field_type="int",
        label="Width (mm)", required=True,
        show_if={"request_type": "air_vent"},
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=4, name="sub_category", field_type="enum",
        label="Sub category", required=True,
        choices=[],  # no default — all choices come from rules
        choices_if=[
            {
                "conditions": {"room_type": "kitchen"},
                "choices": ["base_unit", "wall_unit", "sink_unit", "hob_unit"],
            },
            {
                "conditions": {"room_type": "wardrobe"},
                "choices": ["base_unit", "wall_unit", "dresser"],
            },
        ],
    )
    return tt


# ---------------------------------------------------------------------------
# show_if — hidden fields don't require values
# ---------------------------------------------------------------------------
def test_show_if_skips_required_when_hidden(client_factory, acme_admin, conditional_tt) -> None:
    """request_type=remove_fascia → shutter_finish and module_width_mm both hidden.
    The ticket should validate without them."""
    resp = client_factory(acme_admin).post(
        "/api/tickets/",
        {
            "ticket_type": "acme.cond",
            "title": "fascia removal",
            "payload": {
                "room_type": "kitchen",
                "request_type": "remove_fascia",
                "sub_category": "base_unit",
            },
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201, resp.content


def test_show_if_required_when_visible(client_factory, acme_admin, conditional_tt) -> None:
    """request_type=air_vent → module_width_mm IS required. Submitting without it 400s."""
    resp = client_factory(acme_admin).post(
        "/api/tickets/",
        {
            "ticket_type": "acme.cond",
            "title": "vent",
            "payload": {
                "room_type": "kitchen",
                "request_type": "air_vent",
                "shutter_finish": "Laminate",
                "sub_category": "base_unit",
                # module_width_mm intentionally missing
            },
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 400
    err = resp.json()
    assert "module_width_mm" in str(err["payload"])


def test_hidden_field_value_dropped_from_saved_payload(
    client_factory, acme_admin, conditional_tt, acme_org,
) -> None:
    """If the requester sent a value for a since-hidden field (e.g. they
    selected air_vent + entered a finish, then changed to remove_fascia
    without clearing finish), the saved ticket payload should NOT carry the
    stale finish value."""
    resp = client_factory(acme_admin).post(
        "/api/tickets/",
        {
            "ticket_type": "acme.cond",
            "title": "stale state",
            "payload": {
                "room_type": "kitchen",
                "request_type": "remove_fascia",
                "shutter_finish": "Laminate",  # stale — request_type doesn't require it
                "sub_category": "base_unit",
            },
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201, resp.content
    saved = Ticket.objects.get(id=resp.json()["id"])
    assert "shutter_finish" not in saved.payload


# ---------------------------------------------------------------------------
# choices_if — cascading dropdown
# ---------------------------------------------------------------------------
def test_choices_if_kitchen_accepts_kitchen_choices(
    client_factory, acme_admin, conditional_tt,
) -> None:
    resp = client_factory(acme_admin).post(
        "/api/tickets/",
        {
            "ticket_type": "acme.cond",
            "title": "x",
            "payload": {
                "room_type": "kitchen",
                "request_type": "remove_fascia",
                "sub_category": "sink_unit",  # only valid for kitchen
            },
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201, resp.content


def test_choices_if_wardrobe_rejects_kitchen_only_choice(
    client_factory, acme_admin, conditional_tt,
) -> None:
    """sink_unit is a kitchen choice; sending it with room_type=wardrobe 400s."""
    resp = client_factory(acme_admin).post(
        "/api/tickets/",
        {
            "ticket_type": "acme.cond",
            "title": "x",
            "payload": {
                "room_type": "wardrobe",
                "request_type": "remove_fascia",
                "sub_category": "sink_unit",  # invalid for wardrobe
            },
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 400
    assert "sub_category" in str(resp.json()["payload"])


def test_choices_if_wardrobe_accepts_wardrobe_choices(
    client_factory, acme_admin, conditional_tt,
) -> None:
    resp = client_factory(acme_admin).post(
        "/api/tickets/",
        {
            "ticket_type": "acme.cond",
            "title": "x",
            "payload": {
                "room_type": "wardrobe",
                "request_type": "remove_fascia",
                "sub_category": "dresser",
            },
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201, resp.content


# ---------------------------------------------------------------------------
# Discovery API exposes show_if + choices_if
# ---------------------------------------------------------------------------
def test_discovery_api_exposes_show_if(client_factory, acme_admin, conditional_tt) -> None:
    resp = client_factory(acme_admin).get("/api/tickets/plugins/", **HDRS)
    assert resp.status_code == 200
    tt = next(t for t in resp.json() if t["identifier"] == "acme.cond")
    finish = next(f for f in tt["fields"] if f["name"] == "shutter_finish")
    assert finish["show_if"] == {"request_type": ["additional_lock", "air_vent"]}


def test_discovery_api_exposes_choices_if(client_factory, acme_admin, conditional_tt) -> None:
    resp = client_factory(acme_admin).get("/api/tickets/plugins/", **HDRS)
    tt = next(t for t in resp.json() if t["identifier"] == "acme.cond")
    sub = next(f for f in tt["fields"] if f["name"] == "sub_category")
    rules = sub["choices_if"]
    assert len(rules) == 2
    assert rules[0]["conditions"] == {"room_type": "kitchen"}
    assert "sink_unit" in rules[0]["choices"]


# ---------------------------------------------------------------------------
# Admin API: create + edit + read back
# ---------------------------------------------------------------------------
def test_admin_can_persist_show_if(client_factory, acme_admin, acme_org) -> None:
    tt = TicketType.objects.create(org=acme_org, identifier="acme.t", display_name="T")
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{tt.id}/fields/",
        {
            "order": 0,
            "name": "extra_notes",
            "field_type": "text",
            "label": "Extra notes",
            "required": False,
            "show_if": {"request_type": "escalate"},
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201, resp.content
    f = TicketTypeField.objects.get(ticket_type=tt, name="extra_notes")
    assert f.show_if == {"request_type": "escalate"}


def test_admin_can_persist_choices_if(client_factory, acme_admin, acme_org) -> None:
    tt = TicketType.objects.create(org=acme_org, identifier="acme.t", display_name="T")
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{tt.id}/fields/",
        {
            "order": 0,
            "name": "sub_category",
            "field_type": "enum",
            "label": "Sub",
            "required": True,
            "choices": [],
            "choices_if": [
                {"conditions": {"room_type": "kitchen"},
                 "choices": ["base_unit", "sink_unit"]},
                {"conditions": {"room_type": "wardrobe"},
                 "choices": ["base_unit", "dresser"]},
            ],
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 201, resp.content


def test_admin_enum_with_no_choices_and_no_rules_rejected(
    client_factory, acme_admin, acme_org,
) -> None:
    tt = TicketType.objects.create(org=acme_org, identifier="acme.t", display_name="T")
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{tt.id}/fields/",
        {
            "order": 0,
            "name": "broken",
            "field_type": "enum",
            "label": "Broken enum",
            "choices": [],
            "choices_if": [],
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 400


def test_admin_choices_if_validation_malformed_rule(
    client_factory, acme_admin, acme_org,
) -> None:
    tt = TicketType.objects.create(org=acme_org, identifier="acme.t", display_name="T")
    resp = client_factory(acme_admin).post(
        f"/api/admin/ticket-types/{tt.id}/fields/",
        {
            "order": 0,
            "name": "broken",
            "field_type": "enum",
            "label": "X",
            "choices": ["a"],
            "choices_if": [{"conditions": {"x": 1}}],  # missing `choices` key
        },
        format="json",
        **HDRS,
    )
    assert resp.status_code == 400
    assert "choices_if" in resp.json()
