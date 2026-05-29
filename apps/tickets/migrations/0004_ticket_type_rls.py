"""RLS policies on TicketType + child tables (TicketTypeField, WorkflowStage).

TicketType has its own `org_id` column. The two child tables don't — their
isolation is via FK → TicketType → org_id. Policies on the child tables
use the JOIN form via `EXISTS (...)` so a query that doesn't filter by
ticket_type still gets policy-restricted.
"""
from __future__ import annotations

from django.db import migrations

SQL_UP = """
ALTER TABLE tickets_tickettype ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tickets_tickettype
    USING (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid)
    WITH CHECK (org_id = NULLIF(current_setting('app.org_id', true), '')::uuid);

ALTER TABLE tickets_tickettypefield ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tickets_tickettypefield
    USING (
        EXISTS (
            SELECT 1 FROM tickets_tickettype tt
            WHERE tt.id = tickets_tickettypefield.ticket_type_id
              AND tt.org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM tickets_tickettype tt
            WHERE tt.id = tickets_tickettypefield.ticket_type_id
              AND tt.org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
        )
    );

ALTER TABLE tickets_workflowstage ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON tickets_workflowstage
    USING (
        EXISTS (
            SELECT 1 FROM tickets_tickettype tt
            WHERE tt.id = tickets_workflowstage.ticket_type_id
              AND tt.org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
        )
    )
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM tickets_tickettype tt
            WHERE tt.id = tickets_workflowstage.ticket_type_id
              AND tt.org_id = NULLIF(current_setting('app.org_id', true), '')::uuid
        )
    );
"""

SQL_DOWN = """
DROP POLICY IF EXISTS tenant_isolation ON tickets_workflowstage;
ALTER TABLE tickets_workflowstage DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON tickets_tickettypefield;
ALTER TABLE tickets_tickettypefield DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON tickets_tickettype;
ALTER TABLE tickets_tickettype DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("tickets", "0003_ticket_types")]
    operations = [migrations.RunSQL(sql=SQL_UP, reverse_sql=SQL_DOWN)]
