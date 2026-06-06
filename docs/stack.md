# Stack — rationale

The choices that took some debate during architecture, with the reasoning that
survived.

## Backend: Django 5 + DRF

- Django's built-in admin is a huge win for Superstar's primary operator UX
  (org management, KB inspection, plugin spec review). Building this in
  FastAPI would mean re-implementing the admin or building a separate React
  admin app.
- Django ORM + JSONB plays well with the declarative plugin model — schemas
  live in JSONB columns and we use Postgres operators directly when needed.
- `ATOMIC_REQUESTS=True` semantics fit `SET LOCAL app.org_id = '...'` for
  Postgres RLS — every request is naturally a transaction, every transaction
  gets its tenant binding.
- FastAPI's async story is real but the decisioning pipeline is IO-bound on
  the LLM call, which we delegate to Celery anyway. Sync Django is fine.

## Frontend: React + Vite + TypeScript

- Portal-only v1 — no SSR requirement, so Next.js's server-rendering surface
  is wasted complexity.
- Vite's dev server is fast. With the proxy config we ship, the frontend
  hot-reloads while Django runs alongside.
- shadcn-style component patterns can be layered on top later without
  committing to a framework now.

## Database: Postgres + pgvector

- One database for relational data and vectors. The alternative (Postgres
  for app, separate Milvus/Qdrant for vectors) doubles the ops surface for a
  use case where the vector table is small (~thousands of rules per tenant).
- `pgvector` is mature enough by 2026; `cosine_distance` is fast enough for
  the scale Superstar targets.

## Queue: Celery + Redis

- Celery is the most battle-tested option in Django land. Dramatiq is cleaner
  in some ways but its community is smaller.
- Decisioning calls go async via Celery so the request handler returns
  immediately and the user sees the result poll/SSE-stream in seconds.

## Embeddings: BGE-M3 via sentence-transformers

- OSS, runs locally, no API dependency.
- Multilingual — Hindi and regional Indian languages work out of the box,
  which matters for HomeLane's eventual non-English content.
- 1024-dim native; we pin this in `pgvector` schema. Switching models means
  a migration, which is fine for a deliberate change.

## LLM: open-weight only, via LLMClient

- **Why open-weight at all:** Superstar is open-source; users self-hosting
  it can run the full stack without an API account.
- **Why behind an interface:** the LLM is the single component most likely
  to change (new Qwen versions, switching to Llama, adopting reasoning
  models). `LLMClient` lets us swap backends without touching decisioning code.
- **Dev default — Ollama with Qwen 2.5 7B Q4_K_M:** ~4.5 GB, runs on a 16GB
  Mac. Sufficient for Superstar's grounded-RAG task type given the inputs are
  structured dropdowns.
- **Prod default — vLLM with Qwen 2.5 32B AWQ:** ~24-28 GB on one L40S or
  H100. Better refusal/grounding than 7B; cheaper than 72B for the task.
  72B is over-spec'd for structured rule-matching.
- **Why not Claude/GPT:** they'd give the best quality, but a Superstar
  deployment would then depend on a closed-API provider. Conscious tradeoff:
  10-15 points of quality for full self-hostability.

## Auth: local email+password v1, Authentik later

- Don't over-build auth. v1 deployments are small orgs that can use
  password+session.
- Authentik (OSS) for SSO when needed — wires into Django via OAuth.

## Email: deferred to Phase 4

- Email parity (reply-to-approve, mirror every event) is ~3-4 weeks of work.
  Deferring it to Phase 4 lets us prove the auto-decisioning loop in
  production sooner. Portal-only v1 is a deliberate scope cut.
- When email lands: outbound SMTP first, then Postal (OSS) for inbound.

## What we said no to

- **Langflow as runtime.** Great for sketching new flows; wrong shape as a
  library you embed. The decisioning loop is ~150 lines of Python.
- **LangChain as the framework.** Too much surface area for what we need.
  Direct retriever → LLM → citation verifier is clearer to read and audit.
- **Multi-DB sharding.** RLS in one Postgres is enough for Superstar's scale.
- **GraphQL.** REST is enough; one consumer (our own frontend) doesn't
  need GraphQL flexibility.
