"""Row-Level Security policies for tickets-app tables.

Tenant context is set per-request via TenantMiddleware:
    SELECT set_config('app.org_id', '<uuid>', true);

Tables with an `org_id` column use the direct predicate. Tables without
(TicketTypeField, WorkflowStage) join through TicketType for isolation.
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

DROP POLICY IF EXISTS tenant_isolation ON tickets_approvalstage;
ALTER TABLE tickets_approvalstage DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS tenant_isolation ON tickets_ticket;
ALTER TABLE tickets_ticket DISABLE ROW LEVEL SECURITY;
"""


class Migration(migrations.Migration):
    dependencies = [("tickets", "0001_initial")]
    operations = [migrations.RunSQL(sql=SQL_UP, reverse_sql=SQL_DOWN)]
