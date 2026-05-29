"""RuleChunk → TicketType FK.

Adds a real foreign key from rules to the configurable TicketType row that
owns them. The old `plugin_identifier` string column stays for backward
compatibility (and as a denormalized lookup key during the transition).

Nullable for now — existing rules from earlier migrations have no FK
target. New rules created via the admin UI will always set it.
"""
from __future__ import annotations

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kb", "0002_rls"),
        ("tickets", "0003_ticket_types"),
    ]

    operations = [
        migrations.AddField(
            model_name="rulechunk",
            name="ticket_type",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rules",
                to="tickets.tickettype",
            ),
        ),
    ]
