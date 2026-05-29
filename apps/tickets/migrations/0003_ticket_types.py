"""Ticket-type configuration tables.

Replaces the previous filesystem PluginContract YAML with first-class DB
models. Each tenant org configures its own ticket types — schema fields,
workflow stages, AI policy — entirely through the SuperStar UI.
"""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0002_rls"),
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TicketType",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("identifier", models.CharField(db_index=True, max_length=100)),
                ("display_name", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                ("sequential", models.BooleanField(default=True)),
                ("ai_enabled", models.BooleanField(default=True)),
                ("confidence_threshold", models.FloatField(default=0.85)),
                ("require_citation", models.BooleanField(default=True)),
                ("shadow_mode", models.BooleanField(default=True)),
                ("system_prompt", models.TextField(blank=True)),
                ("notifications", models.JSONField(blank=True, default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "org",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ticket_types",
                        to="tenants.org",
                    ),
                ),
            ],
            options={
                "ordering": ["org", "identifier"],
                "constraints": [
                    models.UniqueConstraint(fields=("org", "identifier"), name="uniq_org_ticket_type"),
                ],
            },
        ),
        migrations.CreateModel(
            name="TicketTypeField",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                ("name", models.CharField(max_length=100)),
                (
                    "field_type",
                    models.CharField(
                        choices=[
                            ("string", "String"),
                            ("int", "Integer"),
                            ("bool", "Boolean"),
                            ("text", "Long text"),
                            ("enum", "Enum (dropdown)"),
                        ],
                        default="string",
                        max_length=20,
                    ),
                ),
                ("label", models.CharField(max_length=200)),
                ("required", models.BooleanField(default=True)),
                ("choices", models.JSONField(blank=True, default=list)),
                ("help_text", models.CharField(blank=True, max_length=300)),
                (
                    "ticket_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fields",
                        to="tickets.tickettype",
                    ),
                ),
            ],
            options={
                "ordering": ["ticket_type", "order"],
                "constraints": [
                    models.UniqueConstraint(fields=("ticket_type", "name"), name="uniq_tt_field_name"),
                ],
            },
        ),
        migrations.CreateModel(
            name="WorkflowStage",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                ("name", models.CharField(max_length=100)),
                ("approvers", models.JSONField(blank=True, default=list)),
                (
                    "mode",
                    models.CharField(
                        choices=[
                            ("any_member", "Any member"),
                            ("unanimous_team", "Unanimous team"),
                            ("majority", "Majority"),
                            ("specific_user", "Specific user"),
                        ],
                        default="any_member",
                        max_length=30,
                    ),
                ),
                ("sla_hours", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "ticket_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_stages",
                        to="tickets.tickettype",
                    ),
                ),
            ],
            options={
                "ordering": ["ticket_type", "order"],
                "constraints": [
                    models.UniqueConstraint(fields=("ticket_type", "order"), name="uniq_tt_stage_order"),
                ],
            },
        ),
    ]
