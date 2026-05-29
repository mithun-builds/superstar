# Eval harness

The decisioning loop's claim — "auto-decide most requests, never hallucinate
a rule" — is only credible if there's an eval set proving it.

This doc is a placeholder. Phase 2 will:

1. Define the eval set format (JSONL of `{payload, expected_decision, expected_rule_ids, notes}`).
2. Add a `python manage.py eval_decisioning <path-to-eval.jsonl>` command that
   runs each example through `apps.decisioning.services.decide` and reports:
   - Precision (auto-decisions that matched expected outcome / all auto-decisions)
   - Citation accuracy (cited rule_ids that match expected / all cited)
   - Escalation recall (escalations on examples where escalation was expected / all expected escalations)
   - Calibration curve (model self-reported confidence vs actual correctness)
3. Wire the harness into CI so changes to prompts, retrieval, or the model
   can't silently regress quality.

## Acceptance bar for HomeLane go-live

- Precision ≥ 98% on the eval set before any production write-back.
- Citation accuracy = 100% (any hallucinated rule_id is a hard fail).
- Escalation recall ≥ 95% on the "should-escalate" subset.

## How to seed the eval set

For NSD.AI: pull 30-50 historical non-standard tickets from HomeLane's current
FreshService instance, anonymize, and pair each with the rule it should have
matched against. This is parked as a dependency on Mithun's TODO.
