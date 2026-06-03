"""Platform-level (org-agnostic) admin endpoints.

These exist so a superuser can spawn / list / delete tenants from the UI
instead of having to SSH into the box and run `manage.py create_tenant`.
The flow + side effects mirror that command exactly:

  - Create the Org row
  - If owner_email is given:
      - Reuse an existing user with that email, OR
      - Create a new user (password required for new users — no silent
        default; that would be a security footgun)
  - Grant the owner an OrgMembership with role=OWNER
  - Write an audit log entry

POST /api/platform/orgs/  →  201 with the created Org
GET  /api/platform/orgs/  →  200 with the list of all orgs
DELETE /api/platform/orgs/<id>/  →  204 (cascade deletes memberships +
                                          tenant-scoped rows via FK CASCADE)
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from rest_framework import serializers, status, viewsets
from rest_framework.response import Response

from apps.audit.services import log_event
from apps.tenants.models import Org, OrgMembership
from apps.tenants.permissions import IsPlatformAdmin

User = get_user_model()


class PlatformOrgSerializer(serializers.ModelSerializer):
    """Read shape. POST uses PlatformOrgCreateSerializer below — the two
    are split because create takes optional owner fields that aren't part
    of the Org model itself."""
    member_count = serializers.IntegerField(read_only=True)
    owner_emails = serializers.SerializerMethodField()

    class Meta:
        model = Org
        fields = ["id", "slug", "name", "created_at", "member_count", "owner_emails"]
        read_only_fields = ["id", "created_at"]

    def get_owner_emails(self, obj: Org) -> list[str]:
        return list(
            OrgMembership.objects.filter(org=obj, role=OrgMembership.Role.OWNER)
            .values_list("user__email", flat=True)
        )


class PlatformOrgCreateSerializer(serializers.Serializer):
    """Mirrors the `create_tenant` management command's argument shape."""
    slug = serializers.SlugField(max_length=64)
    name = serializers.CharField(max_length=200)
    owner_email = serializers.EmailField(required=False, allow_blank=True)
    owner_password = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
        style={"input_type": "password"},
    )

    def validate_slug(self, value: str) -> str:
        if Org.objects.filter(slug=value).exists():
            raise serializers.ValidationError(f"Org with slug {value!r} already exists.")
        return value

    def validate(self, attrs: dict) -> dict:
        email = (attrs.get("owner_email") or "").strip()
        password = (attrs.get("owner_password") or "").strip()
        if email and not User.objects.filter(email=email).exists() and not password:
            raise serializers.ValidationError({
                "owner_password":
                    "Required for a new user. Either supply a password or use "
                    "an email that already has an account.",
            })
        return attrs


class OrgPlatformViewSet(viewsets.ViewSet):
    """Platform-level org CRUD. Superuser-only.

    Not using ModelViewSet because the create path has side effects
    (owner provisioning + audit log + transaction) that don't fit
    DRF's generic flow cleanly.
    """
    permission_classes = [IsPlatformAdmin]

    def list(self, request):
        orgs = (
            Org.objects.all()
            .order_by("created_at")
            .annotate(member_count=Count("memberships"))
        )
        return Response(PlatformOrgSerializer(orgs, many=True).data)

    @transaction.atomic
    def create(self, request):
        ser = PlatformOrgCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        org = Org.objects.create(slug=data["slug"], name=data["name"])

        owner_email = (data.get("owner_email") or "").strip()
        owner = None
        if owner_email:
            owner = User.objects.filter(email=owner_email).first()
            if owner is None:
                owner = User.objects.create_user(
                    email=owner_email, password=data["owner_password"],
                )
            OrgMembership.objects.create(
                org=org, user=owner, role=OrgMembership.Role.OWNER,
            )

        log_event(
            event_type="config.reloaded",
            org=org,
            data={
                "action": "tenant_created",
                "slug": org.slug,
                "owner_email": owner_email or None,
                "via": "platform_api",
            },
        )

        # Re-fetch with the count annotation so the response shape matches list().
        org = Org.objects.filter(pk=org.pk).annotate(
            member_count=Count("memberships"),
        ).first()
        return Response(
            PlatformOrgSerializer(org).data, status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, pk=None):
        try:
            org = Org.objects.get(pk=pk)
        except Org.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        slug, name = org.slug, org.name
        org.delete()
        # Audit event lands with org=None — the deleted Org is gone, but we
        # preserve its slug + name in the event payload so the audit trail
        # is still complete. AuditEvent.org is nullable for this reason.
        log_event(
            event_type="config.reloaded",
            org=None,
            data={
                "action": "tenant_deleted",
                "slug": slug,
                "name": name,
                "via": "platform_api",
            },
        )
        return Response(status=status.HTTP_204_NO_CONTENT)
