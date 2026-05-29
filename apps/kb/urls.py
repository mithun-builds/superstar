"""Admin KB URLs — nested under a ticket type.

Mounted at `/api/admin/` alongside the ticket-type admin URLs.
"""
from __future__ import annotations

from django.urls import path

from .views import RuleAdminViewSet

app_name = "kb_admin"

_rule_list = RuleAdminViewSet.as_view({"get": "list", "post": "create"})
_rule_detail = RuleAdminViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)

urlpatterns = [
    path(
        "ticket-types/<uuid:ticket_type_pk>/rules/",
        _rule_list,
        name="rules-list",
    ),
    path(
        "ticket-types/<uuid:ticket_type_pk>/rules/<uuid:pk>/",
        _rule_detail,
        name="rules-detail",
    ),
]
