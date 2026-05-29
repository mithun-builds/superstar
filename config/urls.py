"""SuperStar URL config.

Two top-level URL spaces:
- /admin/             Django admin (platform-level: superusers managing orgs)
- /o/<org_slug>/...   Tenant-scoped routes. TenantMiddleware resolves the org
                       from the slug and sets request.org.
- /api/               REST endpoints (also tenant-aware via the same middleware).
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.accounts.urls", namespace="accounts")),
    path("api/", include("apps.tickets.urls", namespace="tickets")),
    path("o/<slug:org_slug>/", include("apps.tenants.urls", namespace="tenants")),
]
