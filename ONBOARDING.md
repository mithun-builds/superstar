# Onboarding — clone to first decided ticket

A 30-minute walkthrough that gets you from `git clone` to watching the
decisioning loop fire on a real test ticket in your dev environment.

If you only have time for one verification at the end, it's
**[Step 10 — full-loop smoke](#step-10--full-loop-smoke)**.

---

## What you'll have when you're done

- Superstar backend running on `http://localhost:8000`
- Frontend running on `http://localhost:5173`
- A `demo` tenant with one ticket type configured through the admin UI
- One KB rule embedded with BGE-M3
- A test ticket that goes through the four-guard pipeline and either auto-decides or escalates
- All 266 tests passing locally (196 backend + 70 frontend)

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Python | 3.11 or 3.12 | Django 5 minimum |
| Node | 18+ | Vite + Vitest |
| Docker Desktop | recent | Postgres + Redis containers |
| Ollama | latest | local LLM serving (dev default — Qwen 2.5 7B Q4_K_M) |
| ~6 GB free disk | — | Postgres data dir + Ollama model |

**Why Ollama natively, not in Docker:** On macOS, Docker can't pass Metal
through to the container — Ollama-in-Docker would run CPU-only and be 10×
slower. The `docker-compose.yml` deliberately skips it.

---

## Step 1 — clone and set up the env file

```bash
git clone https://github.com/mithun-builds/superstar.git
cd superstar
cp .env.example .env
```

Open `.env` and **change one thing** for the first run: set
`LLM_PROVIDER=noop`. This makes the decisioning loop deterministic
(always returns "escalate") so you can verify the plumbing before
involving the model. Switch back to `ollama` once Step 7 passes.

```bash
# in .env
LLM_PROVIDER=noop          # change back to "ollama" once tests pass
```

---

## Step 2 — bring up Postgres + Redis

```bash
docker compose up -d
```

Verify both are healthy (takes ~10 seconds):

```bash
docker compose ps
# both services should show "healthy"
```

If `superstar-postgres` won't start, you probably have something else on
port 5432 already (a local Postgres install). Either stop the other one
or edit `docker-compose.yml` to map 5432 → 5433 and update `.env`'s
`DATABASE_URL` accordingly.

---

## Step 3 — Python env + backend deps

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The `.[dev]` extras pull in pytest, ruff, and the django-stubs you'll
want for type-checking.

---

## Step 4 — migrate the database

```bash
python manage.py migrate
```

You should see ~30 migrations apply. They include the RLS policies for
every tenant-scoped table (`tickets_ticket`, `kb_rulechunk`, etc.) and
the `vector(1024)` columns powered by pgvector. If you see
`extension "vector" is not available`, you brought up the wrong Postgres
image — `docker-compose.yml` uses `pgvector/pgvector:pg16` for a reason.

Create a platform superuser so you can sign into the Django admin:

```bash
python manage.py createsuperuser
# email: you@local.test
# password: anything
```

---

## Step 5 — provision a tenant

The platform is generic; everything tenant-specific is created through
the UI. Bootstrap an org first:

```bash
python manage.py create_tenant --slug demo --name "Demo Org" \
    --owner-email owner@demo.test --owner-password 'pw12345!'
```

This creates the `Org`, a new `User`, and an `OrgMembership` with
role=owner. You'll log into the Superstar UI as this user.

---

## Step 6 — start the backend

```bash
python manage.py runserver
```

In a separate terminal, start a Celery worker (decisioning runs async):

```bash
source .venv/bin/activate
celery -A config worker --loglevel=info
```

> **Shortcut:** if you want to skip the Celery worker for now, set
> `CELERY_TASK_ALWAYS_EAGER=true` in `.env` and tasks run inline. Use
> this only in dev — it's slower per request and doesn't catch
> worker-side bugs.

---

## Step 7 — run the test suite

Before touching the UI, verify the install is sound:

```bash
# Backend (196 tests, ~30s)
pytest

# Frontend (70 tests, ~1s)
cd frontend
npm install
npm test
cd ..
```

Both should pass. If `pytest` fails with `ImproperlyConfigured: Set the
DATABASE_URL environment variable`, your `.env` didn't load — make sure
you're running from the repo root and the file is named exactly `.env`
(not `.env.local` or similar).

---

## Step 8 — start the frontend and create a ticket type via the UI

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. You should see the org picker — pick
**Demo Org**. (If you don't see it, sign in at
`http://localhost:8000/admin/login/` as your superuser first to set the
session cookie.)

Then navigate **Admin → Ticket types → New** and fill in:

| Field | Value |
|---|---|
| Identifier | `demo.access-request` |
| Display name | Access Request |
| AI enabled | yes |
| Shadow mode | yes (default) |
| Confidence threshold | 0.85 |
| System prompt | `Decide based on retrieved rules. Cite rule_ids. Output JSON.` |

Add **one field** under Schema:

| Name | Type | Label | Required | Choices |
|---|---|---|---|---|
| `role` | enum | Role | yes | `engineer,intern` |

Add **one workflow stage** (you can leave approvers empty for the smoke):

| Order | Name | Mode |
|---|---|---|
| 1 | Manager review | any_member |

Save.

---

## Step 9 — add a KB rule

Click into your new ticket type → **Rules → New**. Fill in:

- **rule_id:** `R-ENG-OK`
- **title:** `Engineer access approved`
- **body:** `Engineers are approved for default access.`
- **decision_hint:** `approve`
- **applies_when:** use the visual builder to add `role = engineer`

Save. The save handler runs the BGE-M3 embedding pipeline — the first
save is slow (~15 seconds to download the model the first time). After
that, embeds take ~50ms.

---

## Step 10 — full-loop smoke

The fast path that proves everything works end-to-end without clicking
through the UI:

```bash
python scripts/e2e_full_loop.py
```

This script (already in the repo) creates a ticket type, fields, stages,
a rule, then submits a ticket, runs decisioning, checks the approval
chain materialized, votes on stage 1, and dumps the audit trail. It
exits non-zero on any failure.

If you want to do it through the UI instead:

1. Navigate to **New ticket** → pick "Access Request"
2. Pick role = `engineer` → submit
3. On the ticket detail page, click **Run decisioning**
4. Wait ~2-5 seconds for the polling to resolve (Ollama is doing real work now)
5. You should see a Decision card with `outcome=approve` and
   `cited_rule_ids=["R-ENG-OK"]`

If `outcome=escalate` with reason "No rule_ids cited.", that's the
no-op LLM running — flip `.env` back to `LLM_PROVIDER=ollama` and pull
the model:

```bash
ollama pull qwen2.5:7b-instruct-q4_K_M    # ~4.5 GB
```

Restart `runserver` so it re-reads `.env`.

---

## Troubleshooting (real failure modes I hit)

**`psycopg.OperationalError: connection refused`** — Postgres container
isn't up. `docker compose ps` and re-check Step 2.

**`extension "vector" is not available`** — wrong Postgres image. Make
sure `docker-compose.yml` is using `pgvector/pgvector:pg16`, not stock
`postgres:16`.

**Tests work but `runserver` 500s on every request** — your `.env`
loaded for pytest (via `BASE_DIR / .env`) but not for runserver. Make
sure you're starting it from the repo root, not from `/apps/...`.

**LLM call hangs forever** — Ollama isn't running. `ollama serve` in
another terminal, or `brew services start ollama` on macOS.

**Frontend can't reach the backend** — check the proxy config in
`frontend/vite.config.ts`. It maps `/api` → `localhost:8000`. If you
changed the backend port, change it here too.

**RLS test failures only (`apps/tenants/test_rls.py`)** — those need a
non-superuser Postgres role. The `_setup_rls_test_role` fixture creates
it idempotently, but if your local Postgres user lacks `CREATEROLE`,
those will fail. Easiest fix: just use the Docker Postgres in
`docker-compose.yml`, which runs as the superuser-ish `superstar` role.

---

## What to read next

- `docs/roadmap.md` — what's done vs. what's coming
- `docs/plugins.md` — the data model for ticket types, fields, stages, teams
- `docs/applies_when.md` — the DSL used for rule frontmatter, `show_if`, and `choices_if`
- `docs/eval.md` — running `manage.py eval_decisioning` and gating shadow → live
- `docs/stack.md` — why this stack (and what was deliberately ruled out)

## Where things live

```
apps/tickets/         # Ticket + TicketType + WorkflowStage + StageVote + serializers + approval logic
apps/decisioning/     # The 4-guard pipeline + Celery task + eval harness
apps/kb/              # RuleChunk + BGE-M3 embedding pipeline + admin API
apps/tenants/         # Org + OrgMembership + Team + RLS verification tests
apps/audit/           # AuditEvent — every state transition lands here
apps/accounts/        # Custom user model (email-as-username)

config/               # Django settings, urls, celery, asgi/wsgi
superstar/            # Framework-agnostic libs (LLMClient + applies_when DSL)
frontend/src/         # React + Vite + TS app
scripts/              # e2e_full_loop.py, smoke_nsd.py — manual smokes
examples/eval/        # Sample golden file for the eval harness
```
