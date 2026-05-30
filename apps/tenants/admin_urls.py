"""Team admin URLs — mounted under /api/admin/."""
from __future__ import annotations

from django.urls import path
from rest_framework.routers import DefaultRouter

from .admin_views import TeamAdminViewSet, TeamMembershipAdminViewSet

app_name = "tenants_admin"

router = DefaultRouter()
router.register("teams", TeamAdminViewSet, basename="team")

_member_list = TeamMembershipAdminViewSet.as_view({"get": "list", "post": "create"})
_member_detail = TeamMembershipAdminViewSet.as_view(
    {"get": "retrieve", "delete": "destroy"}
)

urlpatterns = router.urls + [
    path(
        "teams/<uuid:team_pk>/members/",
        _member_list,
        name="team-members-list",
    ),
    path(
        "teams/<uuid:team_pk>/members/<uuid:pk>/",
        _member_detail,
        name="team-members-detail",
    ),
]
