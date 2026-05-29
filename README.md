# SuperStar

**AI-native ticketing platform with grounded auto-decisioning.**

Requests come in. A knowledge base decides most of them — citing the rules it used. The rest escalate to humans on configurable approval chains. Everything is auditable.

```
Request ──► RAG over Knowledge Base ──► Decide
                                          │
                              ┌───────────┴───────────┐
                              ▼                       ▼
                         Auto-decide              Escalate to
                       (cite rules, close)        human approvers
```

SuperStar is a generic, self-hostable platform. Every tenant — your company, the customer next door, whoever — configures their ticket types, knowledge base, approval chains, and AI policy **through SuperStar's UI**, in the running product. No filesystem-edited YAML, no separate config repos. Onboard like any SaaS.

## Why SuperStar

- **Grounded decisions only.** Every auto-decision cites the rule_ids it used. Citations are mechanically verified against retrieved chunks *and* checked against each rule's `applies_when` conditions — no hallucinated rule references, no misapplied real rules.
- **Open-weight LLM by default.** Self-host Qwen 2.5 via Ollama or vLLM. Swap any backend via the `LLMClient` interface.
- **Multi-tenant from v1.** One platform, many orgs. Postgres RLS isolates tenants. Path-routed (`/o/{org-slug}/...`).
- **Configure in the product, not the filesystem.** Org admins create ticket types, schema fields, approval workflows, system prompts, and KB rules through the SuperStar admin UI. Everything lives in Postgres, scoped per-org.
- **MIT licensed.** Fork, deploy. Your tenant data stays in your DB.

## Status

**Phase 1 — DB-native config rework on `wip/db-backed-config`.** Backend foundation in place; admin UI lands next. See [docs/roadmap.md](docs/roadmap.md).

## Quickstart

Requires Python 3.11+ and Docker.

```bash
git clone https://github.com/mithun-builds/superstar.git
cd superstar
cp .env.example .env
docker compose up -d           # Postgres + pgvector + Redis

# Ollama runs natively (no Docker — needs Metal/GPU passthrough you can't get in a container on macOS):
#   macOS:  brew install ollama
#   Linux:  curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b-instruct-q4_K_M    # ~4.5 GB, dev default

# Backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
```

Bring up a demo tenant:

```bash
python manage.py create_tenant --slug demo --name "Demo Org"
```

Then sign in at `/admin/login/`, hit `http://localhost:5173/o/demo`, and:
1. Go to **Admin → Ticket types → New** to define your first ticket type
2. Add schema fields (the form requesters will fill in)
3. Add workflow stages (the human-approval chain on escalation)
4. Write the system prompt for AI decisioning
5. Add KB rules — markdown body + frontmatter for decision / price / `applies_when` conditions
6. Submit a test ticket and run decisioning on it

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                   SuperStar (this repo)                     │
│                                                              │
│   ┌────────────┐   ┌─────────────┐   ┌──────────────────┐   │
│   │  Tickets   │   │ Decisioning │   │  KB (RuleChunk)  │   │
│   │  (Django)  │──►│ (RAG + 4    │◄──│  with pgvector   │   │
│   │            │   │  guards)    │   │  embeddings      │   │
│   └────────────┘   └──────┬──────┘   └──────────────────┘   │
│         ▲                 │                                  │
│         │                 ▼                                  │
│   ┌────────────┐   ┌─────────────┐                           │
│   │  Approval  │   │ LLMClient   │ ─► Ollama (dev)           │
│   │  Chains    │   │ (interface) │ ─► vLLM   (prod)          │
│   └────────────┘   └─────────────┘                           │
│         ▲                                                    │
│         │                                                    │
│   ┌────────────────────────┐                                 │
│   │ TicketType +           │ ◄── all config is DB-native,    │
│   │ TicketTypeField +      │     scoped per-org, edited      │
│   │ WorkflowStage          │     via the admin UI            │
│   └────────────────────────┘                                 │
└────────────────────────────────────────────────────────────┘
```

## Stack

- **Backend:** Django 5 + DRF, Python 3.11+
- **Frontend:** React + Vite + TypeScript
- **DB:** Postgres + pgvector (one DB, less ops)
- **Queue:** Celery + Redis
- **Embeddings:** BGE-M3 via sentence-transformers (local, OSS, multilingual)
- **LLM:** Open-weight via `LLMClient` interface (Qwen 2.5 7B dev / 32B prod recommended)

See [docs/stack.md](docs/stack.md) for rationale.

## The four-guard decisioning pipeline

Non-negotiable safety contract:

1. **Citation present** — empty `cited_rule_ids` → escalate
2. **Citation real** — every cited id must appear in retrieved chunks → caught hallucinated IDs
3. **Citation applicable** — each cited rule's `applies_when` conditions must match the request payload → caught misapplied real rules
4. **Confidence threshold** — below floor → escalate

Plus: shadow mode (default on in dev), full audit log per decision.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security: [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
