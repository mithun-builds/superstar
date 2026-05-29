"""Tenant-scoped URLs — mounted under /o/<org_slug>/."""
from django.urls import path

app_name = "tenants"

# Phase 1 will populate this with org-scoped dashboard / tickets list / approvals.
urlpatterns: list = []
