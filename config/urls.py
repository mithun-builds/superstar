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
    path("api/", include("apps.decisioning.urls", namespace="decisioning")),
    # Admin (org-side, not Django superuser admin) — ticket-type + rules CRUD.
    path("api/admin/", include("apps.tickets.admin_urls", namespace="tickets_admin")),
    path("api/admin/", include("apps.kb.urls", namespace="kb_admin")),
    path("o/<slug:org_slug>/", include("apps.tenants.urls", namespace="tenants")),
]
