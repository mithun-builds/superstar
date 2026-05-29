"""DRF permission classes that key off OrgMembership.role.

Used by the admin viewsets — only org owners + admins can mutate ticket
types, fields, stages, and KB rules. Regular requesters and approvers see
405 on those endpoints.
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated

from .models import OrgMembership


class IsOrgAdmin(IsAuthenticated):
    """Allows owner + admin members of `request.org`. Superusers bypass.

    Requires TenantMiddleware to have set `request.org` — which it does on
    org-scoped routes (`/o/<slug>/...`) and on API requests carrying
    `X-Org-Slug`. Returns 403 if no org context.
    """

    message = "Org admin or owner role required."

    def has_permission(self, request, view) -> bool:
        if not super().has_permission(request, view):
            return False
        user = request.user
        if getattr(user, "is_superuser", False):
            return True
        org = getattr(request, "org", None)
        if org is None:
            return False
        return OrgMembership.objects.filter(
            org=org,
            user=user,
            role__in=(OrgMembership.Role.OWNER, OrgMembership.Role.ADMIN),
        ).exists()
