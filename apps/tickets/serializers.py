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
    errors: list[str] = []
    known: dict[str, TicketTypeField] = {f.name: f for f in fields}

    unknown = [k for k in payload if k not in known]
    if unknown:
        errors.append(f"Unknown fields: {unknown}")

    for f in known.values():
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
            if f.choices and v not in f.choices:
                errors.append(
                    f"Field '{f.name}' value {v!r} not in choices {list(f.choices)}"
                )

    return errors


class ApprovalStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalStage
        fields = ["id", "order", "name", "mode", "status", "decided_by", "decided_at", "note"]
        read_only_fields = ["id", "order", "name", "mode", "decided_by", "decided_at"]


class StageDecisionSerializer(serializers.Serializer):
    """Input shape for `POST /api/tickets/<id>/stages/<stage_id>/decide/`."""
    decision = serializers.ChoiceField(choices=[("approved", "Approved"), ("rejected", "Rejected")])
    note = serializers.CharField(required=False, allow_blank=True, max_length=4000)


# ---------------------------------------------------------------------------
# Discovery — what ticket types exist + their forms.
# Replaces /api/tickets/plugins/ (which read from filesystem).
# ---------------------------------------------------------------------------
class TicketTypeFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketTypeField
        fields = ["name", "field_type", "label", "required", "choices", "help_text", "order"]


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
