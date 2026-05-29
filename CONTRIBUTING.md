# Contributing to SuperStar

Thanks for the interest. SuperStar is early — feedback on the architecture is as valuable as code right now.

## Ground rules

1. **No customer-specific code in this repo.** SuperStar is a generic platform. HomeLane, your-company, anyone-else's tenant config lives in *their* private directory, read at runtime via `SUPERSTAR_CONFIG_DIR`. PRs that hardcode customer assumptions will be asked to refactor.
2. **No hallucinations.** Anything that touches the decisioning loop must preserve the grounding contract: cite rule_ids, verify citations against retrieved chunks, escalate when uncertain.
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

## Plugin contracts

New ticket types are plugins. See [`docs/plugins.md`](docs/plugins.md) for the contract. PRs that hardcode a ticket type into the core will be redirected to the plugin layer.

## Reporting bugs

GitHub issues. Include: SuperStar version, Python version, the minimal config that reproduces, what you expected vs. what happened.

## Security

Don't open public issues for security bugs. See [SECURITY.md](SECURITY.md).
