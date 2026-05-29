"""Create a new tenant org. Optionally provision the first owner user.

    python manage.py create_tenant --slug acme --name "Acme Inc"
    python manage.py create_tenant --slug acme --name "Acme Inc" \\
        --owner-email founder@acme.test --owner-password 'change-me'

If `--owner-email` is given:
- An existing user with that email is reused.
- A new user is created if not found. `--owner-password` is required for
  new users (no silent default — would be a security footgun).

The owner gets an OrgMembership with role=owner.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.services import log_event
from apps.tenants.models import Org, OrgMembership

User = get_user_model()


class Command(BaseCommand):
    help = "Create a tenant org and (optionally) its first owner user."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--slug", required=True, help="URL-safe org slug (e.g. 'acme')")
        parser.add_argument("--name", required=True, help="Display name")
        parser.add_argument("--owner-email", default=None, help="Email of the first owner")
        parser.add_argument(
            "--owner-password",
            default=None,
            help="Password for a NEW owner user (required if owner doesn't already exist)",
        )

    @transaction.atomic
    def handle(self, *args, **opts) -> None:
        slug = opts["slug"]
        name = opts["name"]
        owner_email = opts["owner_email"]
        owner_password = opts["owner_password"]

        if Org.objects.filter(slug=slug).exists():
            raise CommandError(f"Org with slug {slug!r} already exists")

        org = Org.objects.create(slug=slug, name=name)
        self.stdout.write(self.style.SUCCESS(f"Created org: {org.slug} — {org.name}"))

        owner = None
        if owner_email:
            owner = User.objects.filter(email=owner_email).first()
            if owner is None:
                if not owner_password:
                    raise CommandError(
                        f"User {owner_email!r} not found and --owner-password not given. "
                        "Either supply a password or create the user beforehand."
                    )
                owner = User.objects.create_user(email=owner_email, password=owner_password)
                self.stdout.write(self.style.SUCCESS(f"Created owner user: {owner.email}"))
            else:
                self.stdout.write(self.style.NOTICE(f"Re-using existing user: {owner.email}"))

            OrgMembership.objects.create(org=org, user=owner, role=OrgMembership.Role.OWNER)
            self.stdout.write(self.style.SUCCESS(f"Granted owner role to {owner.email}"))

        log_event(
            event_type="config.reloaded",  # closest existing event_type; could add tenant.created later
            org=org,
            data={"action": "tenant_created", "slug": slug, "owner_email": owner_email or None},
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. Try:\n"
            f"  curl -u <user>:<pw> -H 'X-Org-Slug: {slug}' "
            "http://localhost:8000/api/tickets/plugins/"
        ))
