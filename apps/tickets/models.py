"""Ticket model + approval stage tracking.

A Ticket is org-scoped (Org FK + `org_id` for RLS). The `ticket_type` field
maps to a plugin identifier (e.g. `homelane.nonstandard`). The plugin defines
the schema validation, workflow, and AI policy for this ticket.

`payload` is JSONB — schema is enforced by the plugin contract, not by Django.
This is the trade-off for pluggable ticket types: column-level type safety
gives way to plugin-validated JSON.

State machine (intentionally minimal in v0):
    OPEN -> DECIDED  (auto, via decisioning service)
    OPEN -> ESCALATED  (auto, when grounding/confidence fails)
    ESCALATED -> APPROVED | REJECTED  (human via approval chain)
    DECIDED -> CLOSED  (system, after notifications)
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.tenants.models import Org


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ESCALATED = "escalated", "Escalated"
        DECIDED = "decided", "Decided (auto)"
        APPROVED = "approved", "Approved (human)"
        REJECTED = "rejected", "Rejected (human)"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Org, on_delete=models.PROTECT, related_name="tickets")
    ticket_type = models.CharField(max_length=100, db_index=True)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tickets_created"
    )
    title = models.CharField(max_length=300)
    payload = models.JSONField(default=dict)  # plugin-validated
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    decision_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["org", "status", "-created_at"]),
            models.Index(fields=["org", "ticket_type", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.ticket_type} :: {self.title}"


class ApprovalStage(models.Model):
    """One stage of a sequential approval chain on an escalated ticket."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="approval_stages")
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="stages")
    order = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)
    mode = models.CharField(max_length=30)  # mirrors WorkflowSpec stage modes
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approval_decisions",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ticket", "order"]
        constraints = [
            models.UniqueConstraint(fields=["ticket", "order"], name="uniq_ticket_stage_order"),
        ]
