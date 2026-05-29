"""Ticket serializers.

Validation runs in two passes:
1. DRF field-level — title, ticket_type presence.
2. Plugin contract — payload fields, required, choices. Done in
   `validate_payload()` against the plugin's `SchemaSpec`.

If the plugin defines an imperative `validate()` hook, it runs after (1) and (2).
"""
from __future__ import annotations

from typing import Any

from rest_framework import serializers

from superstar.plugins import get_plugin

from .models import ApprovalStage, Ticket


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
        ticket_type = attrs.get("ticket_type")
        payload = attrs.get("payload", {})

        try:
            plugin = get_plugin(ticket_type)
        except KeyError as exc:
            raise serializers.ValidationError({"ticket_type": str(exc)}) from exc

        schema = plugin.contract.schema if hasattr(plugin, "contract") else plugin.schema
        errors = _validate_against_schema(payload, schema)

        # Imperative hook, if any.
        if hasattr(plugin, "validate"):
            try:
                hook_errors = plugin.validate(payload) or []
            except Exception as exc:  # noqa: BLE001
                hook_errors = [f"Plugin validate() raised: {exc}"]
            errors.extend(hook_errors)

        if errors:
            raise serializers.ValidationError({"payload": errors})
        return attrs


def _validate_against_schema(payload: dict, schema) -> list[str]:
    errors: list[str] = []
    known_field_names = {f.name for f in schema.fields}

    # Unknown fields.
    unknown = [k for k in payload if k not in known_field_names]
    if unknown:
        errors.append(f"Unknown fields: {unknown}")

    for field in schema.fields:
        v = payload.get(field.name)
        if v in (None, ""):
            if field.required:
                errors.append(f"Field '{field.name}' is required.")
            continue

        # Type checks.
        if field.type == "int" and not isinstance(v, int):
            errors.append(f"Field '{field.name}' must be int, got {type(v).__name__}")
        elif field.type == "bool" and not isinstance(v, bool):
            errors.append(f"Field '{field.name}' must be bool, got {type(v).__name__}")
        elif field.type in ("string", "text") and not isinstance(v, str):
            errors.append(f"Field '{field.name}' must be string, got {type(v).__name__}")
        elif field.type == "enum":
            if field.choices and v not in field.choices:
                errors.append(
                    f"Field '{field.name}' value {v!r} not in choices {list(field.choices)}"
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
