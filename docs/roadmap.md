# Roadmap

## Phase 0 — scaffold ✅

- [x] Repo + OSS hygiene (LICENSE, README, CONTRIBUTING, SECURITY)
- [x] Django config layer (settings, urls, wsgi, asgi, celery)
- [x] Multi-tenant primitives (Org, OrgMembership, TenantMiddleware)
- [x] LLMClient interface + Ollama / vLLM / noop backends
- [x] Apps scaffolded with real models (tickets, kb, decisioning, audit, accounts)
- [x] Frontend skeleton (React + Vite + TS)
- [x] CI workflow (GitHub Actions — backend pytest with Postgres+pgvector service container, frontend vitest + tsc + lint + build, eval-harness smoke with `LLM_PROVIDER=noop`)
- [x] Initial migrations + RLS migrations

## Phase 1 — core ticketing ✅

- [x] Ticket REST API (list / create / detail / decide)
- [x] Sequential approval chain execution + decide endpoint
- [x] Audit log helper wired to all state transitions
- [x] **DB-native tenant config** (TicketType + TicketTypeField + WorkflowStage)
- [x] Decisioning loop with four-guard pipeline:
      citation present → cited rules retrieved → applies_when matches → confidence threshold
- [x] `applies_when` DSL evaluator + 26 unit tests
- [x] `create_tenant` management command
- [x] Frontend: org picker, ticket list, dynamic plugin-driven form, ticket detail with decision card + inline approve/reject
- [x] Admin UI for ticket-type configuration (list / create / edit, fields, stages, AI policy, prompt)
- [x] Admin UI for KB rule management (markdown editor + `applies_when` visual builder + live preview)
- [x] Admin CRUD REST API backing all of the above
- [x] RLS verification test with a non-superuser Postgres role (proves the policies actually engage)

## Phase 2 — AI hardening ✅ (mostly)

- [x] BGE-M3 ingest hooked into rule save() so embeddings stay fresh on edit
- [x] Async decisioning via Celery (`/decide/` returns 202 + polling endpoint)
- [x] Eval harness — `manage.py eval_decisioning` with CI-friendly threshold gates ([docs/eval.md](eval.md))
- [ ] Outbound email + Postal inbound — **deferred to post-v1**

## Phase 2.5 — extras shipped after the original plan

These weren't in the original phase plan but landed in this cycle because the
v1 footprint felt incomplete without them.

- [x] **Vote modes** on approval stages: `any_member`, `unanimous_team`, `majority`, `specific_user`
- [x] **Teams + team membership** (org-scoped, RLS-isolated) — stage approvers reference team slugs
- [x] **Stage-decide authorization gate** — backend enforces who can vote on a stage given its mode
- [x] **StageVote model** — records every vote, supports tally + per-user view
- [x] **Conditional form fields** — `show_if` (visibility) and `choices_if` (cascading choices) on `TicketTypeField`, both reusing the `applies_when` DSL
- [x] **Frontend port of the DSL** so the form reacts client-side without server round-trips

## Phase 3 — first tenant launch

- Pick a real tenant (e.g. HomeLane NSD.AI) and onboard via admin UI
- Curate a 30-50 row golden eval set from real historical tickets
- Shadow mode → live on a subset of users → full rollout
- Tune retrieval / prompt / confidence threshold until precision ≥ 98%
- Deployment recipe: Docker compose for dev, separate GPU box for vLLM, env secrets

## Phase 4 — email parity

- Outbound SMTP for state-change notifications
- Postal (OSS) for inbound — reply-to-approve, mirror every event to email
- Per-org notification config (already a JSONB field on `TicketType.notifications`,
  just needs a UI + workers)

## Beyond v1

- Subdomain-routed tenants (alternative to `/o/<org-slug>/...`)
- Authentik (OSS) SSO integration
- Multi-use-case-per-deployment (an org with 3+ ticket types and one login)
- Optional bulk import / export of ticket types (YAML or JSON) — admin convenience, not the primary configuration path

## What deliberately isn't on the roadmap

- Native mobile apps. Web first; PWA if mobile becomes urgent.
- Real-time collaboration on tickets. Out of scope for v1.
- Custom AI providers in v1. `LLMClient` already supports new backends, but we don't ship adapters for hosted APIs (Anthropic, OpenAI, etc.). Decision: open-weight only, by design.
