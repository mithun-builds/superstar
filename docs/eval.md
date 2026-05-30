# Eval harness

The decisioning loop's claim — "auto-decide most requests, never hallucinate
a rule" — is only credible if there's an eval set proving it. The harness
runs a golden JSONL through the loop, reports the three metrics that matter,
and exits non-zero when a threshold isn't met so CI can gate promotions.

```
manage.py eval_decisioning  ───►  parse JSONL  ───►  for each row:
                                                          create [EVAL] ticket
                                                          run services.decide()
                                                          capture outcome + citations
                                                          ───►  compute_metrics()
                                                                ───►  format report
                                                                ───►  gate on --min-*
```

## Quickstart

```bash
python manage.py eval_decisioning examples/eval/sample.jsonl --org demo \
    --min-precision 0.98 \
    --min-citation-accuracy 1.0 \
    --min-refusal-recall 0.95 \
    --cleanup \
    --json-out eval-report.json
```

What this does:
- Creates one temporary ticket per row, tagged `[EVAL] <example_id>` in the title
- Forces `shadow_mode=True` on the TicketType for the duration (restoring it after) so the eval never mutates production state
- Runs `services.decide()` synchronously (no Celery, no polling) so timing is predictable
- Prints a summary block + per-example pass/fail report
- Writes a machine-readable JSON report for diffing across runs
- Deletes the eval tickets + their Decision rows when `--cleanup` is passed
- Exits non-zero if any threshold isn't met

## Golden file format

JSONL — one object per line. Lines starting with `#` and blank lines are
skipped, so you can section the file by use case.

```jsonl
# section header
{"example_id": "lock-001", "ticket_type": "homelane.nonstandard", "payload": {"request_type": "additional_lock", "type_of_shutter": "1-shutter"}, "expected_decision": "escalate", "expected_rule_ids": ["NSD-LOCK-001"], "notes": "1-shutter lock — escalates per NSD-LOCK-001"}
```

| Field | Required | Description |
|---|---|---|
| `ticket_type` | yes | Identifier of a TicketType configured on the target org |
| `payload` | yes | Request fields the requester would submit |
| `expected_decision` | yes | One of `approve`, `reject`, `escalate` |
| `expected_rule_ids` | no | List (or single string via `expected_rule_id`) of rule_ids the loop SHOULD cite. Citation accuracy = at-least-one-match against the actual citations |
| `example_id` | no | Short label for the per-example report. Defaults to `line-<n>` |
| `notes` | no | Free text; ignored by the harness, used by humans |

See [examples/eval/sample.jsonl](../examples/eval/sample.jsonl) for a copy-paste starting point.

## The three metrics

```
precision         = (correct auto-decisions) / (expected-auto examples)
citation_accuracy = (correct citations on auto-decisions) / (expected-auto examples with rule_ids)
refusal_recall    = (correctly escalated) / (expected-escalate examples)
```

- **Precision** counts only auto-decisions (`approve` / `reject`). An expected-escalate example doesn't count against precision.
- **Citation accuracy** uses OR-semantics: as long as one of the expected rule_ids appears in the actual citations, the row passes. Cites with extra rule_ids beyond what was expected still pass.
- **Refusal recall** is the safety metric. An expected-escalate that got auto-approved is the most dangerous failure mode — this catches it.
- An LLM error (the decisioning service writes outcome=`error`) maps to `escalate` for metric purposes: same observable behavior for the requester.

Any of the three returns `n/a` (not 0) when its denominator is zero — caller can decide whether to treat that as a hard fail or skip.

## Threshold gates

For HomeLane NSD.AI go-live, the recommended floors are:

| Metric | Floor | Why |
|---|---|---|
| `--min-precision` | 0.98 | Auto-approvals must be near-perfect; a wrong approval is a financial / reputational mistake |
| `--min-citation-accuracy` | 1.0 | Any hallucinated rule_id is a hard fail — `applies_when` is the only thing that catches misapplied rules, so the citation must be the correct rule |
| `--min-refusal-recall` | 0.95 | The remaining 5% are "borderline" cases where escalation is debatable |

The harness raises `CommandError` (non-zero exit) when any `--min-*` isn't met,
which is what CI tooling consumes.

## CI integration

A GitHub Actions job that gates merges to `main`:

```yaml
- name: Eval against golden set
  run: |
    python manage.py eval_decisioning eval/nsd-golden.jsonl --org homelane \
      --min-precision 0.98 --min-citation-accuracy 1.0 --min-refusal-recall 0.95 \
      --json-out eval-report.json
- uses: actions/upload-artifact@v4
  with:
    name: eval-report
    path: eval-report.json
```

The JSON report has the full per-example breakdown — useful for diffing across
PRs ("which examples regressed after the prompt change?").

## Seeding a real golden set

For NSD.AI: pull 30-50 historical non-standard tickets from HomeLane's current
FreshService instance, anonymize, and pair each with the rule it should have
matched against. Mix:

- ~20 happy paths (clearly approve / clearly reject) → drives precision
- ~10 escalation triggers (no rule applies / multiple rules conflict) → drives refusal recall
- ~10 adversarial cases (subtly invalid combinations the model might miss) → catches the misapplied-real-rule failure mode

The harness is decoupled from the data — you can build the golden file
incrementally and re-run any time.

## Internals

- Pure-logic pieces (parser, metric computer, formatters) live in [`apps/decisioning/eval.py`](../apps/decisioning/eval.py) — no Django imports, fully unit-testable
- The Django integration (creating tickets, running the loop, cleanup) lives in [`apps/decisioning/management/commands/eval_decisioning.py`](../apps/decisioning/management/commands/eval_decisioning.py)
- Tests are in [`apps/decisioning/test_eval_harness.py`](../apps/decisioning/test_eval_harness.py) — 34 cases covering the math + the command end-to-end with a scripted LLM stub
