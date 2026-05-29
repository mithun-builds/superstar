"""Initial migration for kb — RuleChunk with pgvector embedding column."""
from __future__ import annotations

import uuid

import django.db.models.deletion
import pgvector.django
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("tenants", "0001_initial"),  # pgvector extension enabled there
    ]

    operations = [
        migrations.CreateModel(
            name="RuleChunk",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
                ),
                ("plugin_identifier", models.CharField(db_index=True, max_length=100)),
                ("rule_id", models.CharField(db_index=True, max_length=120)),
                ("source_path", models.CharField(max_length=500)),
                ("title", models.CharField(blank=True, max_length=300)),
                ("body", models.TextField()),
                ("category", models.CharField(blank=True, max_length=100)),
                ("subcategory", models.CharField(blank=True, max_length=100)),
                ("decision_hint", models.CharField(blank=True, max_length=30)),
                ("price_delta", models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ("post_actions", models.JSONField(default=list)),
                ("extra", models.JSONField(default=dict)),
                ("embedding", pgvector.django.VectorField(dimensions=1024)),
                ("ingested_at", models.DateTimeField(auto_now=True)),
                (
                    "org",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rule_chunks",
                        to="tenants.org",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("org", "plugin_identifier", "rule_id"),
                        name="uniq_org_plugin_rule",
                    ),
                ],
                "indexes": [
                    models.Index(fields=["org", "plugin_identifier"], name="kb_org_plugin_idx"),
                ],
            },
        ),
    ]
