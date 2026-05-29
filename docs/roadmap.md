# Roadmap

SuperStar is in **Phase 0** as of 2026-05-25. Target for HomeLane NSD.AI
production go-live: ~3-4 months from start of Phase 1.

## Phase 0 — scaffold (current, ~1 week)

- [x] Repo + OSS hygiene (LICENSE, README, CONTRIBUTING, SECURITY)
- [x] Django config layer (settings, urls, wsgi, asgi, celery)
- [x] Multi-tenant primitives (Org, OrgMembership, TenantMiddleware)
- [x] LLMClient interface + Ollama / vLLM / noop backends
- [x] Plugin contract (declarative + imperative)
- [x] Apps scaffolded with real models (tickets, kb, decisioning, audit, accounts)
- [x] Frontend skeleton (React + Vite + TS)
- [x] Demo config: IT Access Request KB
- [x] CI workflow (GitHub Actions)
- [ ] First migration set written (incl. hand-written RLS migration)
- [ ] kb_ingest management command
- [ ] Eval harness skeleton

## Phase 1 — core ticketing (3-4 weeks)

- Ticket create / list / detail API + UI
- Sequential approval chain execution + per-stage modes
- Plugin loader: read SUPERSTAR_CONFIG_DIR at startup, register declarative plugins
- Tenant onboarding flow (Org + first OrgMembership)
- Audit log writes from all state transitions
- RLS verification tests (Postgres-level isolation)

## Phase 2 — AI decisioning (3-4 weeks)

- BGE-M3 embedding pipeline + KB ingest from markdown + frontmatter
- Decisioning service (services.py is stubbed; wire it up end-to-end)
- Citation verifier (mechanically check cited rule_ids against retrieved chunks)
- Shadow mode harness — log decisions, never apply
- Eval set + precision/recall reporting
- Confidence calibration

## Phase 3 — HomeLane NSD.AI launch (2-3 weeks)

- Point a SuperStar deployment at `superstar-config-homelane/nsd-ai/`
- Validate the 12 normalized rules against 30-50 historical NSD tickets
- Tune retrieval / prompt / confidence threshold until precision ≥ 98%
- Bangalore launch (shadow → live on a subset of designers → full Bangalore)
- National rollout follows

## Phase 4 — Email layer (3-4 weeks)

- Outbound SMTP via configurable provider
- Postal (OSS) inbound for reply-to-approve
- Email mirroring on every ticket event
- Template overrides per plugin
- Phase 4 is *after* HomeLane go-live, not before — portal-only v1.

## Beyond v1

- Subdomain-routed tenants (alternative to `/o/<org-slug>/...`)
- Authentik (OSS) SSO integration
- Sc-Pro API integration (auto-post manual-selection markers)
- Additional HomeLane use cases (engineering ticketing, design QA, etc.)
- Multi-use-case-per-deployment (if HL ends up with 3+ use cases and wants
  one login across them)

## What deliberately isn't on the roadmap

- **Native mobile apps.** Web first; PWA if mobile becomes urgent.
- **Real-time collaboration on tickets.** Out of scope for v1.
- **Custom AI providers in v1.** `LLMClient` already supports new backends,
  but we don't ship adapters for hosted APIs (Anthropic, OpenAI, etc.) in v1.
  Decision: open-weight only, by design.
