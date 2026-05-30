"""Ticket serializers.

Validation:
1. DRF field-level — title, ticket_type identifier presence.
2. TicketType lookup — must resolve in the requester's org.
3. Payload schema — each TicketTypeField row's `required`, `field_type`,
   `choices` is enforced against the payload dict.
"""
from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import ApprovalStage, Ticket, TicketType, TicketTypeField
from .services import TicketTypeNotFound, get_ticket_type


class TicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = [
            "id",
            "ticket_type",
            "title",
            "payload",
            "status",
            "decision_summary",
            "created_at",
            "updated_at",
            "closed_at",
        ]
        read_only_fields = ["id", "status", "decision_summary", "created_at", "updated_at", "closed_at"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        identifier = attrs.get("ticket_type")
        payload = attrs.get("payload", {}) or {}

        # The viewset's perform_create already has request.org; we read it
        # off the serializer context so the same validation works from
        # tests that don't go through the viewset.
        org = (self.context.get("request").org if self.context.get("request") else None)
        if org is None:
            raise serializers.ValidationError(
                {"ticket_type": "Cannot validate without an org context — set X-Org-Slug."}
            )

        try:
            tt = get_ticket_type(org=org, identifier=identifier)
        except TicketTypeNotFound as exc:
            raise serializers.ValidationError({"ticket_type": str(exc)}) from exc

        errors = _validate_payload_against_fields(payload, tt.fields.all())
        if errors:
            raise serializers.ValidationError({"payload": errors})

        return attrs


def _validate_payload_against_fields(payload: dict, fields) -> list[str]:
    """Plugin-driven payload validation, honoring conditional rendering:

    - A field whose `show_if` doesn't match the payload is considered
      hidden — its `required` flag is ignored, AND its value (if any)
      is dropped from the payload to keep stale-state out of the DB.
    - For enum fields with `choices_if`, the first rule whose conditions
      match wins, and validation runs against THAT rule's choices.
      No rule matches → fall back to the field's `choices`.
    """
    from superstar.applies_when import applies_to

    errors: list[str] = []
    known: dict[str, TicketTypeField] = {f.name: f for f in fields}

    unknown = [k for k in payload if k not in known]
    if unknown:
        errors.append(f"Unknown fields: {unknown}")

    for f in known.values():
        # show_if evaluation
        visible = True
        if f.show_if:
            visible, _ = applies_to(f.show_if, payload)
        if not visible:
            # Drop any value the client may have left in for this hidden field
            # so it doesn't roundtrip into the saved ticket payload.
            payload.pop(f.name, None)
            continue

        v = payload.get(f.name)
        if v in (None, ""):
            if f.required:
                errors.append(f"Field '{f.name}' is required.")
            continue

        ft = f.field_type
        if ft == "int" and not isinstance(v, int):
            errors.append(f"Field '{f.name}' must be int, got {type(v).__name__}")
        elif ft == "bool" and not isinstance(v, bool):
            errors.append(f"Field '{f.name}' must be bool, got {type(v).__name__}")
        elif ft in ("string", "text") and not isinstance(v, str):
            errors.append(f"Field '{f.name}' must be string, got {type(v).__name__}")
        elif ft == "enum":
            active_choices = _active_choices(f, payload)
            if active_choices and v not in active_choices:
                errors.append(
                    f"Field '{f.name}' value {v!r} not in choices {list(active_choices)}"
                )

    return errors


def _active_choices(field: TicketTypeField, payload: dict) -> list:
    """Pick the choices for an enum field, considering choices_if rules.

    Returns the first matching rule's choices, or the field's static
    choices as fallback. An empty result means "no constraint" — caller
    should not enforce membership.
    """
    from superstar.applies_when import applies_to

    for rule in field.choices_if or []:
        ok, _ = applies_to(rule.get("conditions"), payload)
        if ok:
            return list(rule.get("choices") or [])
    return list(field.choices or [])


class ApprovalStageSerializer(serializers.ModelSerializer):
    """Read shape for the ticket-detail UI.

    Includes a `vote_tally` for non-`any_member` modes: how many approves,
    how many rejects, how many required (the universe size), and the
    current user's vote if any. The frontend renders "you (1/3 approved
    so far)" UX from these counts.
    """
    vote_tally = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalStage
        fields = [
            "id", "order", "name", "mode", "status", "decided_by", "decided_at",
            "note", "approvers", "vote_tally",
        ]
        read_only_fields = [
            "id", "order", "name", "mode", "decided_by", "decided_at", "approvers", "vote_tally",
        ]

    def get_vote_tally(self, stage):
        from apps.tickets.approval import _required_voter_count
        from apps.tickets.models import StageVote

        votes = stage.votes.all()
        approves = sum(1 for v in votes if v.decision == StageVote.Decision.APPROVED)
        rejects = sum(1 for v in votes if v.decision == StageVote.Decision.REJECTED)
        try:
            required = _required_voter_count(stage, stage.org)
        except Exception:  # noqa: BLE001
            required = 0
        # current user's vote, if any
        request = self.context.get("request")
        my_vote = None
        if request and getattr(request, "user", None) and request.user.is_authenticated:
            mine = next((v for v in votes if v.user_id == request.user.id), None)
            my_vote = mine.decision if mine else None
        return {
            "approves": approves,
            "rejects": rejects,
            "required": required,
            "my_vote": my_vote,
        }


class StageDecisionSerializer(serializers.Serializer):
    """Input shape for `POST /api/tickets/<id>/stages/<stage_id>/decide/`."""
    decision = serializers.ChoiceField(choices=[("approved", "Approved"), ("rejected", "Rejected")])
    note = serializers.CharField(required=False, allow_blank=True, max_length=4000)


# ---------------------------------------------------------------------------
# Discovery — what ticket types exist + their forms.
# Replaces /api/tickets/plugins/ (which read from filesystem).
# ---------------------------------------------------------------------------
class TicketTypeFieldSerializer(serializers.ModelSerializer):
    """Read-only field shape for the requester-side form discovery.

    The model column is `field_type` (Python avoids shadowing `type`), but
    the public API exposes it as `type` — that's the contract the React
    DynamicForm component reads. The admin-side serializer uses the
    `field_type` name on purpose (admin UI mirrors the DB column names).
    """
    type = serializers.CharField(source="field_type", read_only=True)

    class Meta:
        model = TicketTypeField
        fields = [
            "name", "type", "label", "required", "choices", "help_text", "order",
            "show_if", "choices_if",
        ]


class TicketTypeDiscoverySerializer(serializers.ModelSerializer):
    """Read-only — used by NewTicket form to render the dynamic schema."""
    fields = TicketTypeFieldSerializer(many=True, read_only=True)

    class Meta:
        model = TicketType
        fields = [
            "identifier",
            "display_name",
            "description",
            "ai_enabled",
            "shadow_mode",
            "fields",
        ]
