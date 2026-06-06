"""Decision records — one per auto-decision attempt.

Persisted regardless of outcome (auto-decide / escalate / error). This is the
audit trail for grounding: every record has the prompt, the retrieved chunks,
and the raw model output. Required for shadow-mode comparison and for
debugging "why did Superstar approve this?".
"""
from __future__ import annotations

import uuid

from django.db import models

from apps.tenants.models import Org
from apps.tickets.models import Ticket


class Decision(models.Model):
    class Outcome(models.TextChoices):
        APPROVED = "approve", "Approved"
        REJECTED = "reject", "Rejected"
        ESCALATED = "escalate", "Escalated"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="decisions")
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="decisions")

    outcome = models.CharField(max_length=20, choices=Outcome.choices)
    cited_rule_ids = models.JSONField(default=list)
    confidence = models.FloatField()
    reason_text = models.TextField(blank=True)
    price_delta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    post_actions = models.JSONField(default=list)

    # Audit fields
    retrieved_chunk_ids = models.JSONField(default=list)
    system_prompt = models.TextField(blank=True)
    user_prompt = models.TextField(blank=True)
    raw_model_output = models.TextField(blank=True)
    model_name = models.CharField(max_length=200, blank=True)

    # Was this decision auto-applied to the ticket, or held in shadow?
    shadow_mode = models.BooleanField(default=True)

    # Async dispatch tracking. When the decision was kicked off via Celery
    # (the standard path), `task_id` is the Celery task UUID — used by the
    # polling endpoint to find the row before the requester has the
    # decision_id. `started_at` lets us measure end-to-end latency from
    # dispatch to completion (vs. just LLM call latency in `created_at`).
    task_id = models.UUIDField(null=True, blank=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["org", "-created_at"]),
            models.Index(fields=["ticket", "-created_at"]),
        ]
