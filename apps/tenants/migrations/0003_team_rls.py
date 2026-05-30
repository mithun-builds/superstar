"""RLS policies for Team + TeamMembership.

Team has its own org_id column → direct predicate.
TeamMembership doesn't carry org_id → use an EXISTS join through Team.
"""
from __future__ import annotations

from django.db import migrations

SQL_UP = """
ALTER TABLE tenants_team ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenants_team
    USING (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
    WITH CHECK (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid);

ALTER TABLE tenants_teammembership ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tenants_teammembership
    USING (
        EXISTS (
            SELECT 1 FROM tenants_team t
            WHERE t.id = tenants_teammembership.team_id
              AND t.org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM tenants_team t
            WHERE t.id = tenants_teammembership.team_id
              AND t.org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
        )
    );
"""

SQL_DOWN = """
DROP POLICY IF EXISTS tenant_isolation ON tenants_teammembership;
ALTER TABLE tenants_teammembership DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON tenants_team;
ALTER TABLE tenants_team DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("tenants", "0002_team_teammembership_team_uniq_org_team_slug_and_more")]
    operations = [migrations.RunSQL(sql=SQL_UP, reverse_sql=SQL_DOWN)]
