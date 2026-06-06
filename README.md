# Superstar

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

Superstar is a generic, self-hostable platform. Every tenant — your company, the customer next door, whoever — configures their ticket types, knowledge base, approval chains, and AI policy **through Superstar's UI**, in the running product. No filesystem-edited YAML, no separate config repos. Onboard like any SaaS.

## Why Superstar

- **Grounded decisions only.** Every auto-decision cites the rule_ids it used. Citations are mechanically verified against retrieved chunks *and* checked against each rule's `applies_when` conditions — no hallucinated rule references, no misapplied real rules.
- **Open-weight LLM by default.** Self-host Qwen 2.5 via Ollama or vLLM. Swap any backend via the `LLMClient` interface.
- **Multi-tenant from v1.** One platform, many orgs. Postgres RLS isolates tenants. Path-routed (`/o/{org-slug}/...`).
- **Configure in the product, not the filesystem.** Org admins create ticket types, schema fields, approval workflows, system prompts, and KB rules through the Superstar admin UI. Everything lives in Postgres, scoped per-org.
- **Approval chains with real vote semantics.** Four stage modes — `any_member`, `unanimous_team`, `majority`, `specific_user` — backed by team membership and a vote tally that updates live.
- **Conditional forms.** Schema fields support `show_if` (visibility) and `choices_if` (cascading dropdowns) via the same `applies_when` DSL admins already learn for rule conditions.
- **Async decisioning.** `POST /decide/` returns 202 + a task id; a Celery worker runs the LLM call; the frontend polls. Long inference doesn't block the request thread.
- **Eval harness built in.** `python manage.py eval_decisioning` runs a JSONL golden set through the loop and reports precision / citation accuracy / refusal recall. `--min-*` thresholds make CI gate shadow → live promotions.
- **MIT licensed.** Fork, deploy. Your tenant data stays in your DB.

## Status

**v1 backend complete.** 196 tests passing. Multi-tenant, configurable through the UI, with the full decisioning loop (RAG → 4 guards → auto-decide or escalate), approval chains, async dispatch, and an eval harness. Email + a packaged deployment recipe are the remaining v1 items. See [docs/roadmap.md](docs/roadmap.md).

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

# Celery worker (separate terminal) — async decisioning lives here.
# Skip in dev with `CELERY_TASK_ALWAYS_EAGER=true` in .env (runs tasks inline).
celery -A config worker --loglevel=info

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
│                   Superstar (this repo)                     │
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

## Evaluating decision quality

The eval harness runs a golden JSONL through the decisioning loop and gates promotions on the three metrics:

```bash
python manage.py eval_decisioning examples/eval/sample.jsonl --org demo \
    --min-precision 0.98 --min-citation-accuracy 1.0 --min-refusal-recall 0.95 \
    --json-out eval-report.json
```

Non-zero exit on threshold failure → drop straight into CI. The harness forces `shadow_mode=True` for its tickets so it never mutates production state. Full docs in [docs/eval.md](docs/eval.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security: [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
