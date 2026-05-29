"""Ticket-type lookup service.

The single place that resolves a string identifier into the configured
TicketType row for an org. Everything that used to call
`superstar.plugins.get_plugin(identifier)` now calls `get_ticket_type(org, identifier)`.

Why a service module and not just inline `TicketType.objects.get(...)`:
- centralizes the "ticket type not found" error message
- gives us one place to add per-request caching later if hot enough
- keeps the import shape stable across the (eventual) refactor of the
  ORM access pattern
"""
from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from apps.tenants.models import Org

from .models import TicketType


class TicketTypeNotFound(LookupError):
    """No active TicketType row matched (org, identifier)."""


def get_ticket_type(*, org: Org, identifier: str) -> TicketType:
    """Resolve a ticket type by its identifier within an org.

    Raises `TicketTypeNotFound` if there's no active row — callers should
    surface this as a 400/404 to the requester.
    """
    try:
        return TicketType.objects.get(org=org, identifier=identifier, is_active=True)
    except ObjectDoesNotExist as exc:
        raise TicketTypeNotFound(
            f"No active ticket type {identifier!r} in org {org.slug!r}. "
            "Configure it via the admin UI."
        ) from exc
