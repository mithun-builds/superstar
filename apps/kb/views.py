"""Admin KB rule CRUD — nested under a ticket type.

URL shape: `/api/admin/ticket-types/<ticket_type_pk>/rules/[<pk>/]`.

Embedding refresh:
- On create, always compute the BGE-M3 embedding.
- On update, recompute only if `body`, `title`, or `applies_when` changed.
  These are the fields that influence retrieval — frontmatter-only edits
  (decision flip, price tweak) don't need a re-embed.
- The embedder is loaded lazily on first use to keep cold-start fast.
"""
from __future__ import annotations

import logging

from rest_framework import viewsets
from rest_framework.exceptions import NotFound, PermissionDenied

from apps.tenants.permissions import IsOrgAdmin
from apps.tickets.models import TicketType

from .models import RuleChunk
from .serializers import RuleChunkSerializer

logger = logging.getLogger(__name__)


def _require_org(request):
    org = getattr(request, "org", None)
    if org is None:
        raise PermissionDenied("Org context required.")
    return org


def _resolve_ticket_type(kwargs, org) -> TicketType:
    pk = kwargs["ticket_type_pk"]
    try:
        return TicketType.objects.get(id=pk, org=org)
    except TicketType.DoesNotExist as exc:
        raise NotFound(f"Ticket type {pk!r} not found in this org.") from exc


def _embed_text(rule_body: str, title: str) -> list[float]:
    """Compute BGE-M3 embedding for a rule. Heavy import is lazy."""
    from apps.decisioning.embedding import embed

    payload = f"{title}\n\n{rule_body}" if title else rule_body
    return embed(payload)


class RuleAdminViewSet(viewsets.ModelViewSet):
    """Org+ticket-type-scoped CRUD for rules."""
    serializer_class = RuleChunkSerializer
    permission_classes = [IsOrgAdmin]

    def get_queryset(self):  # type: ignore[override]
        org = getattr(self.request, "org", None)
        if org is None:
            return RuleChunk.objects.none()
        return (
            RuleChunk.objects
            .filter(org=org, ticket_type_id=self.kwargs.get("ticket_type_pk"))
            .order_by("rule_id")
        )

    def perform_create(self, serializer) -> None:
        org = _require_org(self.request)
        tt = _resolve_ticket_type(self.kwargs, org)
        body = serializer.validated_data.get("body", "")
        title = serializer.validated_data.get("title", "")
        embedding = _embed_text(body, title)
        serializer.save(
            org=org,
            ticket_type=tt,
            plugin_identifier=tt.identifier,  # denormalized for lookup compat
            embedding=embedding,
        )

    def perform_update(self, serializer) -> None:
        instance: RuleChunk = self.get_object()
        old_body, old_title = instance.body, instance.title
        old_applies = (instance.extra or {}).get("applies_when")

        instance = serializer.save()

        # Re-embed only if body/title/applies_when changed.
        new_applies = (instance.extra or {}).get("applies_when")
        if (
            instance.body != old_body
            or instance.title != old_title
            or new_applies != old_applies
        ):
            instance.embedding = _embed_text(instance.body, instance.title)
            instance.save(update_fields=["embedding"])
            logger.info("Re-embedded rule %s after content change.", instance.rule_id)
