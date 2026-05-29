"""RLS on Decision — org-scoped audit-row isolation."""
from __future__ import annotations

from django.db import migrations

SQL_UP = """
ALTER TABLE decisioning_decision ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON decisioning_decision
    USING (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
    WITH CHECK (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid);
"""

SQL_DOWN = """
DROP POLICY IF EXISTS tenant_isolation ON decisioning_decision;
ALTER TABLE decisioning_decision DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("decisioning", "0001_initial")]
    operations = [migrations.RunSQL(sql=SQL_UP, reverse_sql=SQL_DOWN)]
