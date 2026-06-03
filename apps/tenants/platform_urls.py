"""Platform-level URLs — mounted under /api/platform/.

Note these are NOT under /api/admin/ because /api/admin/ presupposes
an X-Org-Slug header and the IsOrgAdmin gate. Platform endpoints
have no org context; they create orgs from scratch.
"""
from __future__ import annotations

from rest_framework.routers import DefaultRouter

from .platform_views import OrgPlatformViewSet

app_name = "tenants_platform"

router = DefaultRouter()
router.register("orgs", OrgPlatformViewSet, basename="platform-org")

urlpatterns = router.urls
