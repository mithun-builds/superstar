"""Ticket model + approval stage tracking + tenant-configurable ticket types.

A Ticket is org-scoped (Org FK + `org_id` for RLS). The `ticket_type` field
references a `TicketType` row in the same org, which carries:

- form schema (TicketTypeField rows — what the requester fills in)
- approval workflow (WorkflowStage rows — what happens on escalation)
- AI policy (confidence threshold, shadow mode, the system prompt body)
- KB rules (RuleChunk rows in apps.kb, FK back to TicketType)

All of this is editable per-org via the admin UI. There is no filesystem
configuration of ticket types — tenants configure themselves entirely
through SuperStar's running product.

`payload` is JSONB on Ticket — its schema is enforced by walking the
TicketType's field rows in the serializer.

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


# ---------------------------------------------------------------------------
# TicketType — per-org configurable. Admins create + edit these via the UI.
# ---------------------------------------------------------------------------
class TicketType(models.Model):
    """A configurable ticket type owned by an org.

    Identifier is unique within an org (e.g. `homelane.nonstandard`,
    `homelane.engineering`). The identifier shape is the org's choice —
    SuperStar doesn't impose a naming scheme.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="ticket_types")
    identifier = models.CharField(max_length=100, db_index=True)
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    # Workflow
    sequential = models.BooleanField(
        default=True,
        help_text="If true, stages must be decided in order. If false, any stage can decide in parallel.",
    )

    # AI policy (inline — no separate table for v0)
    ai_enabled = models.BooleanField(default=True)
    confidence_threshold = models.FloatField(default=0.85)
    require_citation = models.BooleanField(default=True)
    shadow_mode = models.BooleanField(
        default=True,
        help_text="When true, decisions are logged but not applied to the ticket. "
        "Flip off once eval precision is ≥98%.",
    )
    system_prompt = models.TextField(
        blank=True,
        help_text="The prompt prepended to every decisioning call for this ticket type. "
        "Edited in the UI — no file paths.",
    )

    # Notifications — JSONB for v0; could promote to a table once event types stabilize.
    notifications = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "identifier"], name="uniq_org_ticket_type"),
        ]
        ordering = ["org", "identifier"]

    def __str__(self) -> str:
        return f"{self.identifier} ({self.org.slug})"


class TicketTypeField(models.Model):
    """One field on a TicketType's request form.

    Stable `name` is the JSONB key in Ticket.payload. Editing the name on
    an existing field is allowed but will silently invalidate historical
    payloads — admin UI should warn.
    """

    class FieldType(models.TextChoices):
        STRING = "string", "String"
        INT = "int", "Integer"
        BOOL = "bool", "Boolean"
        TEXT = "text", "Long text"
        ENUM = "enum", "Enum (dropdown)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE, related_name="fields")
    order = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FieldType.choices, default=FieldType.STRING)
    label = models.CharField(max_length=200)
    required = models.BooleanField(default=True)
    choices = models.JSONField(default=list, blank=True, help_text="Only for enum fields.")
    help_text = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["ticket_type", "order"]
        constraints = [
            models.UniqueConstraint(fields=["ticket_type", "name"], name="uniq_tt_field_name"),
        ]

    def __str__(self) -> str:
        return f"{self.ticket_type.identifier}.{self.name}"


class WorkflowStage(models.Model):
    """One stage in a TicketType's approval workflow."""

    class Mode(models.TextChoices):
        ANY_MEMBER = "any_member", "Any member"
        UNANIMOUS_TEAM = "unanimous_team", "Unanimous team"
        MAJORITY = "majority", "Majority"
        SPECIFIC_USER = "specific_user", "Specific user"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_type = models.ForeignKey(TicketType, on_delete=models.CASCADE, related_name="workflow_stages")
    order = models.PositiveIntegerField(default=0)
    name = models.CharField(max_length=100)
    approvers = models.JSONField(
        default=list,
        blank=True,
        help_text="Role or group identifiers (strings). v0 doesn't promote these to "
        "a Team table — see WorkflowStage for the typed extension point.",
    )
    mode = models.CharField(max_length=30, choices=Mode.choices, default=Mode.ANY_MEMBER)
    sla_hours = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["ticket_type", "order"]
        constraints = [
            models.UniqueConstraint(fields=["ticket_type", "order"], name="uniq_tt_stage_order"),
        ]

    def __str__(self) -> str:
        return f"{self.ticket_type.identifier} stage[{self.order}] {self.name}"


# ---------------------------------------------------------------------------
# Ticket — the request itself.
# ---------------------------------------------------------------------------
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
