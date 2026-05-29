"""Admin URL routes for ticket-type CRUD.

DRF's `DefaultRouter` doesn't do nested routes out of the box. Rather than
pull in `drf-nested-routers`, the nested URLs are wired by hand — small
table of patterns, easy to audit. Each viewset (Fields, Stages) gets
list/detail URLs under `/ticket-types/<id>/`.
"""
from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .admin_views import (
    TicketTypeAdminViewSet,
    TicketTypeFieldAdminViewSet,
    WorkflowStageAdminViewSet,
)

app_name = "tickets_admin"

router = DefaultRouter()
router.register("ticket-types", TicketTypeAdminViewSet, basename="ticket-type")


_field_list = TicketTypeFieldAdminViewSet.as_view({"get": "list", "post": "create"})
_field_detail = TicketTypeFieldAdminViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)
_stage_list = WorkflowStageAdminViewSet.as_view({"get": "list", "post": "create"})
_stage_detail = WorkflowStageAdminViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)

urlpatterns = router.urls + [
    path(
        "ticket-types/<uuid:ticket_type_pk>/fields/",
        _field_list,
        name="ticket-type-fields-list",
    ),
    path(
        "ticket-types/<uuid:ticket_type_pk>/fields/<uuid:pk>/",
        _field_detail,
        name="ticket-type-fields-detail",
    ),
    path(
        "ticket-types/<uuid:ticket_type_pk>/stages/",
        _stage_list,
        name="ticket-type-stages-list",
    ),
    path(
        "ticket-types/<uuid:ticket_type_pk>/stages/<uuid:pk>/",
        _stage_detail,
        name="ticket-type-stages-detail",
    ),
]
