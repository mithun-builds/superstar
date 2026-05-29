"""Serializers for the current-user / org-membership endpoints.

`/api/me/` returns the logged-in user and the list of orgs they're a member
of — the frontend needs both to render the org picker and to call tenant-
scoped endpoints with the correct X-Org-Slug header.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.tenants.models import OrgMembership

from .models import User


class OrgMembershipMiniSerializer(serializers.ModelSerializer):
    org_slug = serializers.CharField(source="org.slug", read_only=True)
    org_name = serializers.CharField(source="org.name", read_only=True)

    class Meta:
        model = OrgMembership
        fields = ["id", "org_slug", "org_name", "role", "created_at"]


class MeSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "is_staff", "is_superuser", "memberships"]

    def get_memberships(self, user: User) -> list[dict]:
        qs = user.org_memberships.select_related("org").order_by("org__slug")
        return OrgMembershipMiniSerializer(qs, many=True).data
