"""Admin-side CRUD viewsets for Team + TeamMembership.

URL shape (mounted under /api/admin/):
    GET    /api/admin/teams/
    POST   /api/admin/teams/
    GET    /api/admin/teams/<id>/
    PATCH  /api/admin/teams/<id>/
    DELETE /api/admin/teams/<id>/
    GET    /api/admin/teams/<id>/members/
    POST   /api/admin/teams/<id>/members/
    DELETE /api/admin/teams/<id>/members/<id>/

All gated by IsOrgAdmin. Team membership reads are public-ish (any
org member could be allowed) but for v0 we keep them admin-only too,
so the team roster lives behind the same gate as everything else
that admins configure.
"""
from __future__ import annotations

from rest_framework import viewsets
from rest_framework.exceptions import NotFound

from apps.tenants.permissions import IsOrgAdmin

from .admin_serializers import (
    TeamMembershipReadSerializer,
    TeamMembershipWriteSerializer,
    TeamSerializer,
)
from .models import Team, TeamMembership


def _require_org(request):
    org = getattr(request, "org", None)
    if org is None:
        from rest_framework.exceptions import PermissionDenied

        raise PermissionDenied("Org context required (X-Org-Slug or /o/<slug>/ route).")
    return org


class TeamAdminViewSet(viewsets.ModelViewSet):
    serializer_class = TeamSerializer
    permission_classes = [IsOrgAdmin]

    def get_queryset(self):  # type: ignore[override]
        org = getattr(self.request, "org", None)
        if org is None:
            return Team.objects.none()
        return Team.objects.filter(org=org).prefetch_related("memberships__user")

    def perform_create(self, serializer) -> None:
        serializer.save(org=_require_org(self.request))


class TeamMembershipAdminViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOrgAdmin]

    def initial(self, request, *args, **kwargs):
        """Resolve + cache the parent Team. 404 if it doesn't exist in this org
        (mirrors the rules viewset's contract).
        """
        super().initial(request, *args, **kwargs)
        if getattr(request, "org", None) is None:
            return
        team_pk = kwargs.get("team_pk")
        try:
            self.team = Team.objects.get(id=team_pk, org=request.org)
        except Team.DoesNotExist as exc:
            raise NotFound(f"Team {team_pk!r} not found in this org.") from exc

    def get_serializer_class(self):  # type: ignore[override]
        return TeamMembershipWriteSerializer if self.action in ("create",) else TeamMembershipReadSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["team"] = getattr(self, "team", None)
        return ctx

    def get_queryset(self):  # type: ignore[override]
        org = getattr(self.request, "org", None)
        if org is None:
            return TeamMembership.objects.none()
        return TeamMembership.objects.filter(
            team__org=org, team_id=self.kwargs.get("team_pk")
        ).select_related("user")

    def perform_create(self, serializer) -> None:
        serializer.save(team=self.team)
