# Security policy

## Reporting a vulnerability

Email **security@superstar.dev** (or, until that's set up, mithun.ganesh@homelane.com). Do not open a public GitHub issue.

Include:
- A description of the issue and its impact
- Steps to reproduce
- Affected Superstar version
- Whether the issue has been disclosed elsewhere

We'll acknowledge within 72 hours and aim for a fix or mitigation within 30 days for critical issues.

## Scope

In scope:
- Tenant isolation bypasses (cross-tenant data leaks)
- Authentication / session handling
- Decisioning pipeline tampering (grounding bypass, citation forging)
- RCE in plugin loaders or KB ingest
- SQL injection or RLS policy bypass

Out of scope:
- Self-XSS
- Issues that require physical access to a dev machine
- Vulnerabilities in dependencies that don't affect Superstar's exposed surface

## Hardening guidance

- Always run with `DEBUG=false` in production.
- Postgres RLS must be enforced — verify with `SELECT relrowsecurity FROM pg_class WHERE relname = 'tickets_ticket';` (and other tenant-scoped tables). Run Superstar against a non-superuser DB role in production so the policies actually engage.
- LLM endpoints used in production should never be exposed to untrusted networks. Run vLLM/Ollama behind your VPC or auth gateway.
- Admin UI access to ticket-type and KB editing must be restricted to org owners/admins — see the `OrgMembership.role` field. Don't grant `requester`-role users access to admin endpoints.
- Audit logs are immutable by convention; consider WORM storage for compliance use cases.
