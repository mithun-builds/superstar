"""RLS on AuditEvent.

`org_id` is nullable on AuditEvent (platform-level events have no org). The
policy allows nullable rows through *and* rows matching the current
`app.org_id`. That way platform-level audit events (KB ingest by a
superuser, config reload) are still readable by the admin path.
"""
from __future__ import annotations

from django.db import migrations

SQL_UP = """
ALTER TABLE audit_auditevent ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON audit_auditevent
    USING (
        org_id IS NULL
        OR org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
    )
    WITH CHECK (
        org_id IS NULL
        OR org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
    );
"""

SQL_DOWN = """
DROP POLICY IF EXISTS tenant_isolation ON audit_auditevent;
ALTER TABLE audit_auditevent DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_initial")]
    operations = [migrations.RunSQL(sql=SQL_UP, reverse_sql=SQL_DOWN)]
