"""Project-level pytest fixtures.

Two orgs (acme + globex) with the four membership roles, so any test that
needs to assert cross-org isolation or permission gating can compose
without duplication.

Also exposes a `rls_conn` fixture — a psycopg connection authenticated as a
non-superuser Postgres role. Used by the RLS verification tests in
apps/tenants/test_rls.py to prove the tenant_isolation policies actually
engage at the DB level. Django's default connection bypasses RLS because
it runs as the superuser-ish owner.
"""
from __future__ import annotations

import psycopg
import pytest
from django.contrib.auth import get_user_model
from django.db import connection as django_connection
from rest_framework.test import APIClient

from apps.tenants.models import Org, OrgMembership

User = get_user_model()


# Non-superuser role used for RLS testing. Created once per session in the
# `_setup_rls_test_role` fixture below, then connected to per test via
# `rls_conn`. The role name is deliberately distinct from any production
# role name so it can't accidentally affect deploys.
RLS_TEST_ROLE = "superstar_rls_test"
RLS_TEST_PW = "rls-test-only"


# ---------------------------------------------------------------------------
# Orgs
# ---------------------------------------------------------------------------
@pytest.fixture
def acme_org(db) -> Org:
    return Org.objects.create(slug="acme", name="Acme Inc")


@pytest.fixture
def globex_org(db) -> Org:
    return Org.objects.create(slug="globex", name="Globex Corp")


# ---------------------------------------------------------------------------
# Users + memberships (acme)
# ---------------------------------------------------------------------------
def _make_member(org: Org, email: str, role: str):
    user = User.objects.create_user(email=email, password="pw12345!")
    OrgMembership.objects.create(org=org, user=user, role=role)
    return user


@pytest.fixture
def acme_owner(acme_org: Org):
    return _make_member(acme_org, "owner@acme.test", OrgMembership.Role.OWNER)


@pytest.fixture
def acme_admin(acme_org: Org):
    return _make_member(acme_org, "admin@acme.test", OrgMembership.Role.ADMIN)


@pytest.fixture
def acme_approver(acme_org: Org):
    return _make_member(acme_org, "approver@acme.test", OrgMembership.Role.APPROVER)


@pytest.fixture
def acme_requester(acme_org: Org):
    return _make_member(acme_org, "requester@acme.test", OrgMembership.Role.REQUESTER)


# ---------------------------------------------------------------------------
# Users + memberships (globex)
# ---------------------------------------------------------------------------
@pytest.fixture
def globex_admin(globex_org: Org):
    return _make_member(globex_org, "admin@globex.test", OrgMembership.Role.ADMIN)


# ---------------------------------------------------------------------------
# Platform superuser (bypasses IsOrgAdmin)
# ---------------------------------------------------------------------------
@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(email="root@local.test", password="pw12345!")


# ---------------------------------------------------------------------------
# Authenticated API clients
# ---------------------------------------------------------------------------
@pytest.fixture
def client_factory():
    """Build an authenticated APIClient for a given user."""
    def _make(user) -> APIClient:
        c = APIClient()
        c.force_authenticate(user=user)
        return c
    return _make


@pytest.fixture
def anon_client() -> APIClient:
    return APIClient()


# ---------------------------------------------------------------------------
# RLS fixtures — proves the tenant_isolation policies engage. The pytest-django
# default DB connection runs as a Postgres role with BYPASSRLS, which silently
# skips the policies. To verify enforcement we open a *separate* psycopg
# connection as a non-superuser role.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def _setup_rls_test_role(django_db_setup, django_db_blocker):
    """Idempotently create the RLS test role and grant it the perms it needs
    on the test DB. Runs once per pytest session.
    """
    with django_db_blocker.unblock():
        with django_connection.cursor() as cur:
            # Role create — Postgres has no "CREATE ROLE IF NOT EXISTS".
            cur.execute(
                f"DO $$ BEGIN "
                f"  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{RLS_TEST_ROLE}') THEN "
                f"    CREATE ROLE {RLS_TEST_ROLE} LOGIN PASSWORD '{RLS_TEST_PW}'; "
                f"  END IF; "
                f"END $$;"
            )
            cur.execute(f"GRANT USAGE ON SCHEMA public TO {RLS_TEST_ROLE};")
            cur.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {RLS_TEST_ROLE};"
            )
            cur.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {RLS_TEST_ROLE};"
            )
    yield


@pytest.fixture
def rls_conn(_setup_rls_test_role):
    """Open a psycopg connection AS the non-superuser RLS test role.

    Uses the same DB Django's test runner is on — Django exposes the DB name
    via the default connection settings. Auto-commits each statement so the
    test can directly see what RLS lets through.
    """
    settings_dict = django_connection.settings_dict
    conn = psycopg.connect(
        host=settings_dict.get("HOST") or "localhost",
        port=settings_dict.get("PORT") or 5432,
        dbname=settings_dict["NAME"],
        user=RLS_TEST_ROLE,
        password=RLS_TEST_PW,
        autocommit=False,
    )
    try:
        yield conn
    finally:
        conn.close()
