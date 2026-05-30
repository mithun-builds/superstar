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
        fields = [
            "id", "order", "name", "field_type", "label", "required",
            "choices", "help_text", "show_if", "choices_if",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        # Enum needs at least one choice source — either a static `choices`
        # list or a `choices_if` rule. Validate "you've given me neither"
        # rather than just "no choices".
        if attrs.get("field_type") == "enum":
            if not attrs.get("choices") and not attrs.get("choices_if"):
                raise serializers.ValidationError(
                    {"choices": "Enum needs either `choices` or at least one `choices_if` rule."}
                )
        # choices_if validation — each rule needs both conditions + choices.
        for i, rule in enumerate(attrs.get("choices_if") or []):
            if not isinstance(rule, dict):
                raise serializers.ValidationError(
                    {"choices_if": f"Rule {i}: must be an object, got {type(rule).__name__}"}
                )
            if "conditions" not in rule or "choices" not in rule:
                raise serializers.ValidationError(
                    {"choices_if": f"Rule {i}: needs both `conditions` and `choices` keys."}
                )
            if not isinstance(rule["choices"], list):
                raise serializers.ValidationError(
                    {"choices_if": f"Rule {i}: `choices` must be a list."}
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

    def validate(self, attrs: dict) -> dict:
        # Django 5's UniqueConstraint isn't auto-promoted into a DRF
        # UniqueTogetherValidator — surface the (org, identifier) uniqueness
        # at the validation layer so duplicates return 400, not 500 from
        # a downstream IntegrityError.
        request = self.context.get("request")
        org = getattr(request, "org", None) if request else None
        identifier = attrs.get("identifier") or (self.instance.identifier if self.instance else None)
        if org and identifier:
            existing = TicketType.objects.filter(org=org, identifier=identifier)
            if self.instance is not None:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    {"identifier": f"Identifier {identifier!r} already in use in this org."}
                )
        return attrs
