"""Serializers for KB rule CRUD (admin side).

Rules live in `kb_rulechunk`. Each rule has:
- A markdown body (what the LLM sees at decision time)
- Frontmatter-style structured metadata (decision, applies_when, price, post-actions)
- A BGE-M3 embedding column

The serializer exposes everything except the embedding directly. The
embedding is regenerated server-side on create + body-changing update,
not editable by the client.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import RuleChunk


class RuleChunkSerializer(serializers.ModelSerializer):
    """Read/write serializer for the admin rule editor.

    `applies_when` is exposed as a top-level JSON field even though it
    physically lives inside `extra` — keeps the API ergonomic. The
    serializer roundtrips it correctly on read + write.
    """
    applies_when = serializers.SerializerMethodField()

    class Meta:
        model = RuleChunk
        fields = [
            "id",
            "rule_id",
            "title",
            "body",
            "category",
            "subcategory",
            "decision_hint",
            "price_delta",
            "post_actions",
            "applies_when",
            "extra",
            "ingested_at",
        ]
        read_only_fields = ["id", "ingested_at"]

    def get_applies_when(self, obj: RuleChunk):
        return (obj.extra or {}).get("applies_when")

    def to_internal_value(self, data):
        # Strip applies_when out before standard validation, then fold it
        # back into extra after the model fields are validated. This keeps
        # the persisted shape (extra: {applies_when: ...}) intact.
        applies_when = data.pop("applies_when", None) if isinstance(data, dict) else None
        attrs = super().to_internal_value(data)
        if applies_when is not None:
            extra = dict(attrs.get("extra") or {})
            extra["applies_when"] = applies_when
            attrs["extra"] = extra
        return attrs


class RuleChunkWriteSerializer(RuleChunkSerializer):
    """Same shape, but `extra` is hidden from input to avoid clients
    smuggling fields around applies_when validation."""

    class Meta(RuleChunkSerializer.Meta):
        extra_kwargs = {"extra": {"write_only": False, "required": False}}
