"""Postgres Row-Level Security for tickets.

The TenantMiddleware sets `app.org_id` per request via
    SELECT set_config('app.org_id', <uuid>, true);
The policies below enforce that any row read/written has matching org_id.

Notes for prod:
- Django typically connects as a superuser in dev. Postgres superusers bypass
  RLS unless `FORCE ROW LEVEL SECURITY` is set. We don't force it here so dev
  /admin paths keep working. In prod, use a non-superuser app role and the
  policies will engage automatically.
- The `true` second arg to `current_setting` returns NULL when unset (rather
  than erroring) — allows non-tenant code paths (admin, migrations) to run.
- When `app.org_id` is NULL, the policy denies access. This is intentional;
  tenant-scoped data requires explicit tenant context.
"""
from __future__ import annotations

from django.db import migrations

SQL_UP = """
ALTER TABLE tickets_ticket ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tickets_ticket
    USING (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
    WITH CHECK (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid);

ALTER TABLE tickets_approvalstage ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tickets_approvalstage
    USING (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
    WITH CHECK (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid);
"""

SQL_DOWN = """
DROP POLICY IF EXISTS tenant_isolation ON tickets_approvalstage;
ALTER TABLE tickets_approvalstage DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON tickets_ticket;
ALTER TABLE tickets_ticket DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("tickets", "0001_initial")]
    operations = [migrations.RunSQL(sql=SQL_UP, reverse_sql=SQL_DOWN)]
