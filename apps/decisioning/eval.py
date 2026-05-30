"""Evaluation harness — runs a golden set through the decisioning loop,
reports precision / citation accuracy / refusal recall.

The management command lives at apps/decisioning/management/commands/
eval_decisioning.py. This module holds the pure-logic pieces (sample
parser, metric computer, result formatter) so they can be tested
without setting up a full management-command + DB integration.

Decisions:
- We force shadow_mode=True regardless of the TicketType's setting so
  the eval doesn't actually transition any tickets or materialize
  approval chains. The Decision row IS written for inspection (useful
  for diffing across runs).
- We never enqueue a Celery task — call `services.decide()` directly.
  Eval needs predictable timing and immediate results.
- Tickets created for the eval are tagged in `title` with an `[EVAL]`
  prefix and can be deleted in bulk after the run with `--cleanup`.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class GoldenExample:
    """One row of the golden JSONL file.

    `expected_decision` must be one of approve / reject / escalate (mapped
    to "escalate" in the eval since "error" is a runtime concept, not a
    ground-truth target).

    `expected_rule_ids` accepts a single string OR a list — supports either
    "exactly this rule" or "one of these is fine".
    """
    ticket_type: str
    payload: dict
    expected_decision: str
    expected_rule_ids: list[str] = field(default_factory=list)
    notes: str = ""
    example_id: str = ""  # filled in from line number if missing

    @classmethod
    def from_dict(cls, d: dict, *, default_id: str = "") -> "GoldenExample":
        rule_ids = d.get("expected_rule_ids") or d.get("expected_rule_id")
        if rule_ids is None:
            rule_ids = []
        elif isinstance(rule_ids, str):
            rule_ids = [rule_ids]
        return cls(
            ticket_type=d["ticket_type"],
            payload=d.get("payload", {}),
            expected_decision=d["expected_decision"],
            expected_rule_ids=list(rule_ids),
            notes=d.get("notes", ""),
            example_id=d.get("example_id") or default_id,
        )


@dataclass
class Result:
    example: GoldenExample
    actual_outcome: str
    actual_cited_rule_ids: list[str]
    actual_confidence: float
    latency_ms: int
    error: str = ""

    @property
    def expected_was_auto(self) -> bool:
        """Was the golden expectation an auto-decision (approve/reject)?"""
        return self.example.expected_decision in ("approve", "reject")

    @property
    def expected_was_escalate(self) -> bool:
        return self.example.expected_decision == "escalate"

    @property
    def decision_matches(self) -> bool:
        """Outcome matches ground truth. "error" maps to "escalate" because
        any LLM failure causes the system to escalate to humans — same
        observable behavior for the requester."""
        actual = "escalate" if self.actual_outcome == "error" else self.actual_outcome
        return actual == self.example.expected_decision

    @property
    def citation_matches(self) -> bool:
        """At least one of the expected rule_ids appears in actual citations.
        Only meaningful when expected_decision is auto (approve/reject)."""
        if not self.example.expected_rule_ids:
            return True  # nothing to match against
        return any(r in self.actual_cited_rule_ids for r in self.example.expected_rule_ids)


def parse_jsonl(path: str) -> list[GoldenExample]:
    """Read a JSONL golden file. Lines starting with `#` and blank lines
    are skipped — lets users add inline comments to their golden set."""
    out: list[GoldenExample] = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Line {i}: not valid JSON: {exc}") from exc
            out.append(GoldenExample.from_dict(row, default_id=f"line-{i}"))
    return out


def compute_metrics(results: Iterable[Result]) -> dict:
    """Aggregate the three eval metrics + outcome distribution.

    precision         = (correct auto-decisions) / (expected-auto examples)
    citation_accuracy = (correct citations on auto-decisions) / (expected-auto examples with rule_ids)
    refusal_recall    = (correctly escalated) / (expected-escalate examples)

    All three are None when their denominator is zero — caller decides
    whether to display that as "n/a" or a hard 0.
    """
    results = list(results)
    total = len(results)

    expected_auto = [r for r in results if r.expected_was_auto]
    expected_esc = [r for r in results if r.expected_was_escalate]

    auto_correct = [r for r in expected_auto if r.decision_matches]
    citation_evaluable = [r for r in expected_auto if r.example.expected_rule_ids]
    citation_correct = [r for r in citation_evaluable if r.citation_matches]
    refusal_correct = [r for r in expected_esc if r.decision_matches]

    return {
        "total": total,
        "outcome_distribution": dict(Counter(r.actual_outcome for r in results)),
        "expected_auto_count": len(expected_auto),
        "expected_escalate_count": len(expected_esc),
        "precision": (len(auto_correct) / len(expected_auto)) if expected_auto else None,
        "citation_accuracy": (
            (len(citation_correct) / len(citation_evaluable)) if citation_evaluable else None
        ),
        "refusal_recall": (
            (len(refusal_correct) / len(expected_esc)) if expected_esc else None
        ),
        "latency_p50_ms": _percentile([r.latency_ms for r in results], 0.5),
        "latency_p95_ms": _percentile([r.latency_ms for r in results], 0.95),
    }


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round(p * (len(s) - 1)))))
    return s[k]


def format_summary(metrics: dict) -> str:
    """Render the metrics dict as a human-readable block. Used by the
    management command and by anyone wanting a quick text report."""
    lines: list[str] = []
    lines.append(f"Examples evaluated:  {metrics['total']}")
    lines.append(f"  expected auto-decide: {metrics['expected_auto_count']}")
    lines.append(f"  expected escalate:    {metrics['expected_escalate_count']}")
    lines.append("")
    lines.append("Outcome distribution:")
    for k, v in sorted(metrics["outcome_distribution"].items()):
        lines.append(f"  {k:<10} {v}")
    lines.append("")

    def fmt_pct(v):
        return "n/a" if v is None else f"{100 * v:.1f}%"

    lines.append(f"Precision (auto-decisions matching expected):   {fmt_pct(metrics['precision'])}")
    lines.append(f"Citation accuracy:                              {fmt_pct(metrics['citation_accuracy'])}")
    lines.append(f"Refusal recall (escalates that should escalate): {fmt_pct(metrics['refusal_recall'])}")
    lines.append("")
    lines.append(f"Latency p50: {metrics['latency_p50_ms']} ms")
    lines.append(f"Latency p95: {metrics['latency_p95_ms']} ms")
    return "\n".join(lines)


def format_per_example(results: list[Result]) -> str:
    """One line per example — useful for spotting regressions across runs."""
    out = []
    for r in results:
        ok = "✓" if r.decision_matches and r.citation_matches else "✗"
        cited = ",".join(r.actual_cited_rule_ids) or "—"
        expected_rules = ",".join(r.example.expected_rule_ids) or "—"
        out.append(
            f"  {ok} {r.example.example_id:<14} "
            f"actual={r.actual_outcome:<8} cite={cited:<25} "
            f"expected={r.example.expected_decision:<8} expected_cite={expected_rules}"
        )
    return "\n".join(out)


# ---------------------------------------------------------------------------
# The runner is intentionally kept out of this module — it imports Django
# models. Tests can construct Result objects directly to exercise metrics
# math without touching the DB.
# ---------------------------------------------------------------------------
__all__ = [
    "GoldenExample",
    "Result",
    "parse_jsonl",
    "compute_metrics",
    "format_summary",
    "format_per_example",
]


def to_jsonable_metrics(metrics: dict) -> str:
    """Convenience for writing metrics to a JSON file for diffing across runs."""
    return json.dumps(metrics, indent=2, default=str)
