"""Admin-side CRUD viewsets for ticket types, their fields, and their stages.

Mounted under `/api/admin/`. Org-scoped via TenantMiddleware (`request.org`)
+ `IsOrgAdmin` permission. Cross-org access returns 404 on detail (RLS
makes the row invisible) or empty on list.

Field and stage CRUD lives under the parent ticket-type URL — the URL
shape encodes ownership and prevents stray writes to a sibling org's
children. Pattern:

    GET    /api/admin/ticket-types/
    POST   /api/admin/ticket-types/
    GET    /api/admin/ticket-types/<id>/
    PATCH  /api/admin/ticket-types/<id>/
    DELETE /api/admin/ticket-types/<id>/

    GET    /api/admin/ticket-types/<id>/fields/
    POST   /api/admin/ticket-types/<id>/fields/
    PATCH  /api/admin/ticket-types/<id>/fields/<field_id>/
    DELETE /api/admin/ticket-types/<id>/fields/<field_id>/

    Same shape for stages.
"""
from __future__ import annotations

from rest_framework import viewsets
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.request import Request

from apps.tenants.permissions import IsOrgAdmin

from .admin_serializers import (
    TicketTypeAdminSerializer,
    TicketTypeFieldAdminSerializer,
    WorkflowStageAdminSerializer,
)
from .models import TicketType, TicketTypeField, WorkflowStage


def _require_org(request: Request):
    org = getattr(request, "org", None)
    if org is None:
        raise PermissionDenied("Org context required (X-Org-Slug or /o/<slug>/ route).")
    return org


class TicketTypeAdminViewSet(viewsets.ModelViewSet):
    """Org-scoped CRUD for ticket types."""
    serializer_class = TicketTypeAdminSerializer
    permission_classes = [IsOrgAdmin]

    def get_queryset(self):  # type: ignore[override]
        org = getattr(self.request, "org", None)
        if org is None:
            return TicketType.objects.none()
        return TicketType.objects.filter(org=org).prefetch_related("fields", "workflow_stages")

    def perform_create(self, serializer) -> None:
        serializer.save(org=_require_org(self.request))


class _NestedChildMixin:
    """Shared logic for the field + stage nested viewsets.

    Subclasses set `parent_model = TicketType`, `parent_lookup_kwarg`, and
    `parent_filter_field` to scope to the URL-given ticket type.
    """
    permission_classes = [IsOrgAdmin]
    parent_model = TicketType
    parent_lookup_kwarg = "ticket_type_pk"
    parent_filter_field = "ticket_type"

    def _parent(self):
        request_org = _require_org(self.request)
        pk = self.kwargs[self.parent_lookup_kwarg]
        try:
            return self.parent_model.objects.get(id=pk, org=request_org)
        except self.parent_model.DoesNotExist as exc:
            raise NotFound(f"Ticket type {pk!r} not found in this org.") from exc

    def perform_create(self, serializer) -> None:
        serializer.save(**{self.parent_filter_field: self._parent()})


class TicketTypeFieldAdminViewSet(_NestedChildMixin, viewsets.ModelViewSet):
    serializer_class = TicketTypeFieldAdminSerializer

    def get_queryset(self):  # type: ignore[override]
        if getattr(self.request, "org", None) is None:
            return TicketTypeField.objects.none()
        return (
            TicketTypeField.objects
            .filter(ticket_type__org=self.request.org, ticket_type_id=self.kwargs.get(self.parent_lookup_kwarg))
            .order_by("order")
        )


class WorkflowStageAdminViewSet(_NestedChildMixin, viewsets.ModelViewSet):
    serializer_class = WorkflowStageAdminSerializer

    def get_queryset(self):  # type: ignore[override]
        if getattr(self.request, "org", None) is None:
            return WorkflowStage.objects.none()
        return (
            WorkflowStage.objects
            .filter(ticket_type__org=self.request.org, ticket_type_id=self.kwargs.get(self.parent_lookup_kwarg))
            .order_by("order")
        )
