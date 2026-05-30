"""Serializers for the team-admin endpoints.

Teams are slug-keyed (referenced from WorkflowStage.approvers as strings),
so the admin form's slug field carries the same validation rules as the
ticket-type identifier: lowercase, ASCII, no spaces.
"""
from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import OrgMembership, Team, TeamMembership

User = get_user_model()


class TeamMembershipReadSerializer(serializers.ModelSerializer):
    """Nested-on-Team read shape. POSTs use TeamMembershipWriteSerializer."""
    user_email = serializers.CharField(source="user.email", read_only=True)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = TeamMembership
        fields = ["id", "user", "user_email", "user_full_name", "created_at"]


class TeamSerializer(serializers.ModelSerializer):
    memberships = TeamMembershipReadSerializer(many=True, read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            "id",
            "slug",
            "name",
            "description",
            "memberships",
            "member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "memberships", "member_count", "created_at", "updated_at"]

    def get_member_count(self, obj: Team) -> int:
        # When prefetch_related is in play (list view), this counts in Python
        # without an extra query; in detail view it falls back to a count().
        # Acceptable for the v0 admin where teams are small.
        try:
            return len(obj.memberships.all())
        except Exception:  # noqa: BLE001
            return obj.memberships.count()

    def validate_slug(self, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]{1,79}$", v):
            raise serializers.ValidationError(
                "Team slug must start with a letter/digit and contain only "
                "lowercase letters, digits, dashes."
            )
        return v

    def validate(self, attrs: dict) -> dict:
        """Surface (org, slug) uniqueness at validation time (DRF doesn't
        auto-promote Django 5's UniqueConstraint to a validator — same trick
        we use in TicketTypeAdminSerializer)."""
        request = self.context.get("request")
        org = getattr(request, "org", None) if request else None
        slug = attrs.get("slug") or (self.instance.slug if self.instance else None)
        if org and slug:
            qs = Team.objects.filter(org=org, slug=slug)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"slug": f"Team slug {slug!r} already exists in this org."}
                )
        return attrs


class TeamMembershipWriteSerializer(serializers.ModelSerializer):
    """POST shape: accepts either user_id (UUID) or user_email to enroll.
    The user must already be an org member — otherwise the team would
    contain a stranger to the org."""
    user_email = serializers.EmailField(write_only=True, required=False)
    user_full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = TeamMembership
        fields = ["id", "user", "user_email", "user_full_name", "created_at"]
        extra_kwargs = {"user": {"required": False}}

    def validate(self, attrs: dict) -> dict:
        user = attrs.get("user")
        if user is None:
            email = attrs.pop("user_email", None)
            if not email:
                raise serializers.ValidationError(
                    {"user": "Provide either user (id) or user_email."}
                )
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"user_email": f"No user with email {email!r}."}
                ) from exc
            attrs["user"] = user

        # Team is set in perform_create from the URL; org_membership check
        # uses the view's kwargs-resolved team.
        team = self.context.get("team")
        if team is not None and not OrgMembership.objects.filter(
            org=team.org, user=user
        ).exists():
            raise serializers.ValidationError(
                {"user": f"User {user.email!r} isn't a member of org {team.org.slug!r}."}
            )
        # Duplicate-membership check — DRF doesn't auto-promote Django 5's
        # UniqueConstraint to a validator, so reject here for a clean 400.
        if (
            team is not None
            and self.instance is None
            and TeamMembership.objects.filter(team=team, user=user).exists()
        ):
            raise serializers.ValidationError(
                {"user": f"{user.email!r} is already a member of this team."}
            )
        attrs.pop("user_email", None)
        return attrs
