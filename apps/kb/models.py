"""Knowledge base — rule chunks + their embeddings.

Rules are created and edited via the SuperStar admin UI. Each row carries
its markdown body, frontmatter (decision, applies_when, price, post-actions),
and a BGE-M3 embedding for vector retrieval. Rules belong to a TicketType
(FK in apps.tickets.models) and are tenant-scoped via Org RLS.

The `rule_id` is the citation anchor — the decisioning service emits these
verbatim, and the citation verifier confirms each cited id exists in the
chunks retrieved for that decision.

Embedding refresh happens on save() (Phase 2 — currently the admin save
must trigger embedding explicitly; see the rule-edit view).
"""
from __future__ import annotations

import uuid

from django.db import models
from pgvector.django import VectorField

from apps.tenants.models import Org


class RuleChunk(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="rule_chunks")
    plugin_identifier = models.CharField(max_length=100, db_index=True)
    rule_id = models.CharField(max_length=120, db_index=True)
    source_path = models.CharField(max_length=500, blank=True, help_text="Origin marker — set if imported from a file, blank if created via UI.")
    title = models.CharField(max_length=300, blank=True)
    body = models.TextField()
    # Structured metadata extracted from frontmatter — keeps decisions queryable.
    category = models.CharField(max_length=100, blank=True)
    subcategory = models.CharField(max_length=100, blank=True)
    decision_hint = models.CharField(max_length=30, blank=True)  # compliant / non-compliant / escalate
    price_delta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    post_actions = models.JSONField(default=list)
    extra = models.JSONField(default=dict)
    embedding = VectorField(dimensions=1024)  # BGE-M3 native dim
    ingested_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["org", "plugin_identifier", "rule_id"], name="uniq_org_plugin_rule"
            ),
        ]
        indexes = [
            models.Index(fields=["org", "plugin_identifier"]),
        ]

    def __str__(self) -> str:
        return f"{self.rule_id} ({self.plugin_identifier})"
