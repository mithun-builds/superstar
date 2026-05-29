# Contributing to SuperStar

Thanks for the interest. SuperStar is early — feedback on the architecture is as valuable as code right now.

## Ground rules

1. **No customer-specific code in this repo.** SuperStar is a generic platform. Tenants — HomeLane, your-company, anyone else — configure themselves entirely through the SuperStar admin UI. Their data lives in their deployment's Postgres, not in YAML files. PRs that hardcode customer assumptions or add per-customer code paths will be asked to refactor.
2. **No hallucinations.** Anything that touches the decisioning loop must preserve the four-guard contract: cite rule_ids, verify citations against retrieved chunks, check `applies_when` against the payload, respect the confidence threshold.
3. **Multi-tenant or it doesn't ship.** Every user-facing model has an `org_id`. RLS policies are part of the migration, not a follow-up.

## Dev setup

```bash
git clone https://github.com/mithun-builds/superstar.git
cd superstar
cp .env.example .env
docker compose up -d
pip install -e ".[dev]"
python manage.py migrate
python manage.py test
```

## Code style

- Python: `ruff` for lint + format. Run `ruff check . && ruff format .` before opening a PR.
- TypeScript: `eslint` + `prettier`. Run `npm run lint` in `frontend/`.
- Commits: short imperative subject ("add tenant middleware"), reference an issue if there is one.

## Tests

Every PR needs tests. RAG/decisioning changes need eval harness updates — see [`docs/eval.md`](docs/eval.md).

## Adding a ticket type

You don't. Ticket types are runtime configuration, not code. Create them via the admin UI inside a deployed SuperStar instance. If a *new capability* is needed for ticket types in general (e.g. a new field type, a new approval mode, a new `applies_when` operator), that's a PR — extend the model / DSL evaluator / serializer.

## Reporting bugs

GitHub issues. Include: SuperStar version, Python version, the minimal repro, what you expected vs. what happened.

## Security

Don't open public issues for security bugs. See [SECURITY.md](SECURITY.md).
