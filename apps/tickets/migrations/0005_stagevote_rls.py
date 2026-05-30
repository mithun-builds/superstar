"""RLS on StageVote — org isolation via stage → ticket join."""
from __future__ import annotations

from django.db import migrations

SQL_UP = """
ALTER TABLE tickets_stagevote ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tickets_stagevote
    USING (
        EXISTS (
            SELECT 1 FROM tickets_approvalstage s
            JOIN tickets_ticket t ON t.id = s.ticket_id
            WHERE s.id = tickets_stagevote.stage_id
              AND t.org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM tickets_approvalstage s
            JOIN tickets_ticket t ON t.id = s.ticket_id
            WHERE s.id = tickets_stagevote.stage_id
              AND t.org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
        )
    );
"""

SQL_DOWN = """
DROP POLICY IF EXISTS tenant_isolation ON tickets_stagevote;
ALTER TABLE tickets_stagevote DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("tickets", "0004_stagevote")]
    operations = [migrations.RunSQL(sql=SQL_UP, reverse_sql=SQL_DOWN)]
