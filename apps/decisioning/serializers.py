"""Read-only serializers for Decision rows.

The /by-task/ polling endpoint returns this shape once the worker has
finished. Includes the audit fields (cited_rule_ids, confidence,
reason_text) the frontend renders in the decision card.
"""
from __future__ import annotations

from rest_framework import serializers

from .models import Decision


class DecisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Decision
        fields = [
            "id",
            "outcome",
            "cited_rule_ids",
            "confidence",
            "reason_text",
            "price_delta",
            "post_actions",
            "shadow_mode",
            "task_id",
            "started_at",
            "created_at",
        ]
        read_only_fields = fields
