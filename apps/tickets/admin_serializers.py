"""Serializers for the admin-side CRUD endpoints.

Admin endpoints expose the full TicketType graph: schema fields, workflow
stages, AI policy, system prompt. These serializers carry every editable
column (unlike `TicketTypeDiscoverySerializer` in `serializers.py`, which is
the read-only view consumed by the requester-side form).
"""
from __future__ import annotations

from rest_framework import serializers

from .models import TicketType, TicketTypeField, WorkflowStage


class TicketTypeFieldAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = TicketTypeField
        fields = ["id", "order", "name", "field_type", "label", "required", "choices", "help_text"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        if attrs.get("field_type") == "enum" and not attrs.get("choices"):
            raise serializers.ValidationError(
                {"choices": "Required for enum-typed fields."}
            )
        return attrs


class WorkflowStageAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowStage
        fields = ["id", "order", "name", "approvers", "mode", "sla_hours"]
        read_only_fields = ["id"]


class TicketTypeAdminSerializer(serializers.ModelSerializer):
    """Full ticket-type shape with fields + stages nested read-only.

    Mutations to fields and stages go through their own viewsets (nested
    URLs) — this keeps the validation surface narrow.
    """
    fields = TicketTypeFieldAdminSerializer(many=True, read_only=True)
    workflow_stages = WorkflowStageAdminSerializer(many=True, read_only=True)

    class Meta:
        model = TicketType
        fields = [
            "id",
            "identifier",
            "display_name",
            "description",
            "sequential",
            "ai_enabled",
            "confidence_threshold",
            "require_citation",
            "shadow_mode",
            "system_prompt",
            "notifications",
            "is_active",
            "fields",
            "workflow_stages",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_confidence_threshold(self, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise serializers.ValidationError("Must be between 0 and 1.")
        return v

    def validate_identifier(self, v: str) -> str:
        # Identifiers are stable across edits — they're cited in tickets,
        # rules, and audit events. Allow only ascii + dots + dashes + underscores.
        import re
        if not re.match(r"^[a-z0-9][a-z0-9._-]{2,99}$", v):
            raise serializers.ValidationError(
                "Identifier must start with a letter/digit and contain only "
                "lowercase letters, digits, dots, dashes, underscores."
            )
        return v
