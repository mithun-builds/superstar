"""Initial migration for audit — append-only event log."""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("tenants", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                (
                    "event_type",
                    models.CharField(
                        choices=[
                            ("ticket.created", "Ticket Created"),
                            ("decision.emitted", "Decision Emitted"),
                            ("decision.applied", "Decision Applied"),
                            ("stage.decided", "Stage Decided"),
                            ("ticket.closed", "Ticket Closed"),
                            ("kb.ingested", "Kb Ingested"),
                            ("config.reloaded", "Config Reloaded"),
                        ],
                        db_index=True,
                        max_length=60,
                    ),
                ),
                ("subject_type", models.CharField(blank=True, max_length=60)),
                ("subject_id", models.CharField(blank=True, max_length=64)),
                ("data", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "org",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to="tenants.org",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["org", "-created_at"], name="audit_org_created_idx"),
                    models.Index(fields=["subject_type", "subject_id"], name="audit_subject_idx"),
                ],
            },
        ),
    ]
