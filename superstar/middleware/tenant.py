"""Tenant middleware — resolves the current org and binds it to the connection.

Two jobs:
1. **Resolve** the org from the request:
   - Path: `/o/<org_slug>/...` (default in v0)
   - Subdomain: `<org_slug>.superstar.example` (optional, set per deployment)
   - API: `X-Org-Slug` header (programmatic clients)

2. **Bind** the resolved org_id to the Postgres connection via
   `SET LOCAL app.org_id = '<uuid>'`. Postgres RLS policies on tenant-scoped
   tables reference `current_setting('app.org_id')::uuid` as the predicate.

Why bind on the connection: cleaner than every queryset filtering by org_id.
Single source of truth (RLS) — no app-layer leak surface.

Admin (`/admin/...`) and unauthenticated paths bypass tenant resolution; the
RLS predicate falls back to allow-all for the platform superuser role.
"""
from __future__ import annotations

import logging
from typing import Callable

from django.db import connection
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound

logger = logging.getLogger(__name__)


# Path prefixes that bypass tenant resolution entirely.
_BYPASS_PREFIXES = ("/admin/", "/static/", "/media/", "/health", "/")


class TenantMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        org_slug = self._resolve_org_slug(request)

        if org_slug is None:
            request.org = None
            return self.get_response(request)

        # Late import to avoid app-loading order issues.
        from apps.tenants.models import Org

        try:
            org = Org.objects.get(slug=org_slug, is_active=True)
        except Org.DoesNotExist:
            return HttpResponseNotFound(f"Unknown org: {org_slug}")

        request.org = org
        self._bind_connection(org.id)
        try:
            return self.get_response(request)
        finally:
            self._unbind_connection()

    @staticmethod
    def _resolve_org_slug(request: HttpRequest) -> str | None:
        # Skip bypass paths first.
        if any(request.path.startswith(p) for p in ("/admin/", "/static/", "/media/", "/health")):
            return None

        # Path-based: /o/<slug>/...
        if request.path.startswith("/o/"):
            parts = request.path.split("/", 3)
            if len(parts) >= 3 and parts[2]:
                return parts[2]

        # Header (API clients).
        header_slug = request.headers.get("X-Org-Slug")
        if header_slug:
            return header_slug.strip().lower()

        # TODO Phase 1: subdomain resolution (parse request.get_host()).
        return None

    @staticmethod
    def _bind_connection(org_id) -> None:
        with connection.cursor() as cursor:
            # SET LOCAL is transaction-scoped — safe inside Django's per-request
            # transaction wrapper (ATOMIC_REQUESTS=True recommended in prod).
            cursor.execute("SELECT set_config('app.org_id', %s, true)", [str(org_id)])

    @staticmethod
    def _unbind_connection() -> None:
        # SET LOCAL auto-clears at transaction end; this is belt-and-suspenders
        # for non-atomic request paths.
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.org_id', '', true)")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to clear app.org_id: %s", exc)
