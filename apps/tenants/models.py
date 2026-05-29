"""Tenant models.

Org is the tenant root. Every user-facing model in other apps references Org
via a denormalized `org_id` column for RLS predicates. RLS migrations are
written by hand (see `apps/tenants/migrations/0002_rls.py`) — Django doesn't
generate them.

User identity is platform-wide (not tenant-scoped). OrgMembership joins users
to orgs, with a role.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Org(models.Model):
    """A tenant. The root of all org-scoped data."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Org"
        verbose_name_plural = "Orgs"

    def __str__(self) -> str:
        return f"{self.slug} ({self.name})"


class OrgMembership(models.Model):
    """Join table — a user can belong to multiple orgs with different roles."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        APPROVER = "approver", "Approver"
        REQUESTER = "requester", "Requester"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="org_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["org", "user"], name="uniq_org_user"),
        ]
        indexes = [
            models.Index(fields=["user", "org"]),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.org.slug} ({self.role})"
