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

SuperStar is a generic platform. Any workflow where requests come in, a rule-book decides most of them, and the rest escalate to humans — SuperStar handles the loop. Ticket types are pluggable: each one declares its schema, workflow, AI policy, and integrations.

## Why SuperStar

- **Grounded decisions only.** Every auto-decision cites the rule_ids it used. Citations are mechanically verified against retrieved chunks — no hallucinated rule references.
- **Open-weight LLM by default.** Self-host Qwen 2.5 via Ollama or vLLM. Swap any backend via the `LLMClient` interface.
- **Multi-tenant from v1.** One platform, many orgs. Postgres RLS isolates tenants. Path-routed (`/o/{org-slug}/...`) or subdomain.
- **Ticket types as plugins.** Declarative JSONB specs for the common case, optional Python hooks for imperative logic.
- **MIT licensed.** Fork, deploy, customize — no overlay repo needed. Your tenant config lives outside the SuperStar clone.

## Status

**Phase 0 — repo scaffold.** Not yet runnable end-to-end. See [docs/roadmap.md](docs/roadmap.md) for phasing.

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

Bring up a demo tenant + ingest the IT Access KB:

```bash
python manage.py shell -c "from apps.tenants.models import Org; Org.objects.create(slug='demo', name='Demo Org')"
python manage.py kb_ingest --org demo --plugin itaccess.access-request
```

Then hit the API:

```bash
curl -u admin:<your-pw> -H "X-Org-Slug: demo" http://localhost:8000/api/tickets/plugins/
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    SuperStar (this repo)                      │
│                                                                │
│   ┌────────────┐   ┌─────────────┐   ┌─────────────────────┐ │
│   │  Tickets   │   │ Decisioning │   │  Knowledge Base     │ │
│   │  (Django)  │──►│ (RAG + cite │◄──│  (markdown + KB     │ │
│   │            │   │  verifier)  │   │   ingest → pgvector)│ │
│   └────────────┘   └──────┬──────┘   └─────────────────────┘ │
│         ▲                 │                                   │
│         │                 ▼                                   │
│   ┌────────────┐   ┌─────────────┐                            │
│   │  Approval  │   │ LLMClient   │ ─► Ollama (dev)            │
│   │  Chains    │   │ (interface) │ ─► vLLM   (prod)           │
│   └────────────┘   └─────────────┘                            │
│         ▲                                                     │
│         │                                                     │
│   ┌────────────┐                                              │
│   │   Plugins  │ ◄── ticket types as plugins                  │
│   └────────────┘                                              │
└──────────────────────────────────────────────────────────────┘
            ▲
            │ reads at runtime
            │
   SUPERSTAR_CONFIG_DIR=/path/to/customer-config
   (lives outside this repo)
```

## Tenant config

SuperStar reads tenant config (KB markdown, form schema, approval chains, branding) from a directory set by `SUPERSTAR_CONFIG_DIR`. This is **not** part of the SuperStar repo — customers maintain their own config in their own private Git remote.

The discipline: *tweak settings, never edit SuperStar's code*. If you need a code change, send a PR upstream.

See [`examples/kb-it-access/`](examples/kb-it-access/) for the demo config layout.

## Stack

- **Backend:** Django 5 + DRF, Python 3.11+
- **Frontend:** React + Vite + TypeScript
- **DB:** Postgres + pgvector
- **Queue:** Celery + Redis
- **Embeddings:** BGE-M3 via sentence-transformers (local, OSS, multilingual)
- **LLM:** Open-weight via `LLMClient` interface (Qwen 2.5 7B dev / 32B prod recommended)

See [docs/stack.md](docs/stack.md) for rationale.

## Hallucination controls

Non-negotiable:

1. **Grounding-only prompt** — model decides only from retrieved chunks.
2. **Citation required** — every decision names rule_ids, or it auto-escalates.
3. **Citation verification** — after the model answers, each cited rule_id is checked against the retrieved chunks. Hallucinated IDs → auto-escalate.
4. **Confidence threshold** — defaults to 0.85; configurable per-deployment.
5. **Shadow mode** — toggle write-back off, log decisions side-by-side with human outcomes, measure precision before going live.
6. **Full audit log** — retrieved chunks + prompt + raw output, per decision.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security disclosures: [SECURITY.md](SECURITY.md).

## License

MIT — see [LICENSE](LICENSE).
