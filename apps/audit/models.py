"""Append-only audit log — every meaningful event.

This is the source of truth for "what did Superstar do, and why?". Records are
never updated or deleted in normal operation. Compliance use cases may want
WORM storage (see SECURITY.md).
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.tenants.models import Org


class AuditEvent(models.Model):
    class EventType(models.TextChoices):
        TICKET_CREATED = "ticket.created"
        TICKET_ESCALATED = "ticket.escalated"
        DECISION_EMITTED = "decision.emitted"
        DECISION_APPLIED = "decision.applied"
        STAGE_DECIDED = "stage.decided"
        TICKET_CLOSED = "ticket.closed"
        KB_INGESTED = "kb.ingested"
        CONFIG_RELOADED = "config.reloaded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(
        Org, on_delete=models.PROTECT, related_name="audit_events", null=True
    )
    event_type = models.CharField(max_length=60, choices=EventType.choices, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    subject_type = models.CharField(max_length=60, blank=True)  # e.g. "Ticket"
    subject_id = models.CharField(max_length=64, blank=True)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["org", "-created_at"]),
            models.Index(fields=["subject_type", "subject_id"]),
        ]
