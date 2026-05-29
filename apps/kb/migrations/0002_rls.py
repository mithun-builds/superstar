"""RLS on RuleChunk — org-scoped KB isolation."""
from __future__ import annotations

from django.db import migrations

SQL_UP = """
ALTER TABLE kb_rulechunk ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON kb_rulechunk
    USING (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
    WITH CHECK (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid);
"""

SQL_DOWN = """
DROP POLICY IF EXISTS tenant_isolation ON kb_rulechunk;
ALTER TABLE kb_rulechunk DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("kb", "0001_initial")]
    operations = [migrations.RunSQL(sql=SQL_UP, reverse_sql=SQL_DOWN)]
