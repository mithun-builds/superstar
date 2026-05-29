"""Initial migration for decisioning — Decision audit row."""
from __future__ import annotations

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("tenants", "0001_initial"),
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Decision",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("approve", "Approved"),
                            ("reject", "Rejected"),
                            ("escalate", "Escalated"),
                            ("error", "Error"),
                        ],
                        max_length=20,
                    ),
                ),
                ("cited_rule_ids", models.JSONField(default=list)),
                ("confidence", models.FloatField()),
                ("reason_text", models.TextField(blank=True)),
                ("price_delta", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("post_actions", models.JSONField(default=list)),
                ("retrieved_chunk_ids", models.JSONField(default=list)),
                ("system_prompt", models.TextField(blank=True)),
                ("user_prompt", models.TextField(blank=True)),
                ("raw_model_output", models.TextField(blank=True)),
                ("model_name", models.CharField(blank=True, max_length=200)),
                ("shadow_mode", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "org",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="decisions",
                        to="tenants.org",
                    ),
                ),
                (
                    "ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="decisions",
                        to="tickets.ticket",
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["org", "-created_at"], name="decisioning_org_idx"),
                    models.Index(fields=["ticket", "-created_at"], name="decisioning_ticket_idx"),
                ],
            },
        ),
    ]
