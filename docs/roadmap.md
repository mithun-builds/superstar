# Roadmap

## Phase 0 — scaffold ✅

- [x] Repo + OSS hygiene (LICENSE, README, CONTRIBUTING, SECURITY)
- [x] Django config layer (settings, urls, wsgi, asgi, celery)
- [x] Multi-tenant primitives (Org, OrgMembership, TenantMiddleware)
- [x] LLMClient interface + Ollama / vLLM / noop backends
- [x] Apps scaffolded with real models (tickets, kb, decisioning, audit, accounts)
- [x] Frontend skeleton (React + Vite + TS)
- [x] CI workflow (GitHub Actions)
- [x] Initial migrations + RLS migrations

## Phase 1 — core ticketing ✅ (backend) + 🚧 (admin UI)

- [x] Ticket REST API (list / create / detail / decide)
- [x] Sequential approval chain execution + decide endpoint
- [x] Audit log helper wired to all state transitions
- [x] **DB-native tenant config** (TicketType + TicketTypeField + WorkflowStage)
- [x] Decisioning loop with four-guard pipeline:
      citation present → cited rules retrieved → applies_when matches → confidence threshold
- [x] `applies_when` DSL evaluator + 26 unit tests
- [x] `create_tenant` management command
- [x] Frontend: org picker, ticket list, dynamic plugin-driven form, ticket detail with decision card + inline approve/reject
- [ ] **Admin UI for ticket-type configuration** (next deliverable on `wip/db-backed-config`):
  - `/o/:slug/admin/ticket-types` (list)
  - `/o/:slug/admin/ticket-types/new` (create — schema fields, workflow stages, AI policy, prompt)
  - `/o/:slug/admin/ticket-types/:id` (edit)
  - `/o/:slug/admin/ticket-types/:id/rules` (KB management for that type)
  - `/o/:slug/admin/ticket-types/:id/rules/:id` (markdown editor + applies_when builder)
- [ ] Admin CRUD REST API backing the above
- [ ] RLS verification test with a non-superuser role

## Phase 2 — AI hardening + email

- BGE-M3 ingest hooked into rule save() so embeddings stay fresh on edit
- Eval harness skeleton + precision/recall/refusal metrics
- Async decisioning via Celery (`/decide/` returns 202 + polling endpoint)
- Outbound email + Postal inbound

## Phase 3 — first tenant launch

- Pick a real tenant (e.g. HomeLane NSD.AI) and onboard via admin UI
- Shadow mode → live on a subset of users → full rollout
- Tune retrieval / prompt / confidence threshold until precision ≥ 98%

## Beyond v1

- Subdomain-routed tenants (alternative to `/o/<org-slug>/...`)
- Authentik (OSS) SSO integration
- Multi-use-case-per-deployment (an org with 3+ ticket types and one login)
- Optional bulk import / export of ticket types (YAML or JSON) — admin convenience, not the primary configuration path

## What deliberately isn't on the roadmap

- Native mobile apps. Web first; PWA if mobile becomes urgent.
- Real-time collaboration on tickets. Out of scope for v1.
- Custom AI providers in v1. `LLMClient` already supports new backends, but we don't ship adapters for hosted APIs (Anthropic, OpenAI, etc.). Decision: open-weight only, by design.
