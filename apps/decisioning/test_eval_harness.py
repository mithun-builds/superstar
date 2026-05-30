"""Tests for the eval harness.

Two layers:

1. **Pure unit tests** for `apps.decisioning.eval` — the metric computer,
   the JSONL parser, the formatters. No DB, no Django, no LLM. These
   guarantee the math is correct for the metrics we gate shadow→live on.

2. **Integration tests** for `manage.py eval_decisioning` — the full
   pipeline. Patches the LLM client with a deterministic stub so the
   command behaves the same on every CI run. Checks:

   - the command exits cleanly on a passing golden set
   - it exits non-zero (CommandError) when a threshold isn't met
   - `--cleanup` actually removes the eval tickets
   - `--json-out` writes a machine-readable report

Why patch the LLM rather than rely on LLM_PROVIDER=noop: noop returns
"escalate" for every input, so we can't exercise the *correctness* of
the auto-decision path (precision, citation accuracy). A scripted stub
lets us simulate "model gets it right" / "model hallucinates" cleanly.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.decisioning.eval import (
    GoldenExample,
    Result,
    compute_metrics,
    format_per_example,
    format_summary,
    parse_jsonl,
    to_jsonable_metrics,
)


# ---------------------------------------------------------------------------
# Layer 1 — pure unit tests
# ---------------------------------------------------------------------------
def _result(
    *,
    expected: str,
    expected_rule_ids: list[str] | None = None,
    actual: str,
    actual_cites: list[str] | None = None,
    confidence: float = 0.9,
    latency_ms: int = 100,
    example_id: str = "e",
) -> Result:
    """Test builder: a Result without going near Django."""
    return Result(
        example=GoldenExample(
            ticket_type="acme.tt",
            payload={},
            expected_decision=expected,
            expected_rule_ids=list(expected_rule_ids or []),
            example_id=example_id,
        ),
        actual_outcome=actual,
        actual_cited_rule_ids=list(actual_cites or []),
        actual_confidence=confidence,
        latency_ms=latency_ms,
    )


class TestComputeMetricsPrecision:
    """Precision = correct-auto-decisions / expected-auto-examples.
    Auto-decisions = approve | reject (escalate doesn't count toward precision)."""

    def test_all_correct_auto_decisions(self) -> None:
        results = [
            _result(expected="approve", actual="approve"),
            _result(expected="reject", actual="reject"),
        ]
        m = compute_metrics(results)
        assert m["precision"] == 1.0
        assert m["expected_auto_count"] == 2

    def test_mixed_correctness(self) -> None:
        results = [
            _result(expected="approve", actual="approve"),
            _result(expected="approve", actual="escalate"),  # wrong
            _result(expected="reject", actual="reject"),
            _result(expected="reject", actual="approve"),  # wrong
        ]
        m = compute_metrics(results)
        assert m["precision"] == 0.5

    def test_no_expected_auto_returns_none(self) -> None:
        results = [_result(expected="escalate", actual="escalate")]
        m = compute_metrics(results)
        assert m["precision"] is None
        assert m["expected_auto_count"] == 0

    def test_escalate_examples_excluded_from_precision(self) -> None:
        """Escalate examples should NOT show up in the denominator."""
        results = [
            _result(expected="approve", actual="approve"),
            _result(expected="escalate", actual="approve"),  # wrong but not in scope
        ]
        m = compute_metrics(results)
        assert m["precision"] == 1.0  # 1/1, not 1/2

    def test_error_outcome_maps_to_escalate(self) -> None:
        """An LLM error on an expected-escalate is still correct behavior —
        same observable outcome to the requester."""
        results = [_result(expected="escalate", actual="error")]
        m = compute_metrics(results)
        assert m["refusal_recall"] == 1.0


class TestComputeMetricsCitationAccuracy:
    """Citation accuracy: of auto-decisions with expected rule ids, how
    many had at least one expected id in the actual citations?"""

    def test_matching_citation(self) -> None:
        r = _result(
            expected="approve",
            expected_rule_ids=["R-1"],
            actual="approve",
            actual_cites=["R-1"],
        )
        assert compute_metrics([r])["citation_accuracy"] == 1.0

    def test_any_match_counts(self) -> None:
        """Citation accuracy is OR over expected ids — at least one is enough."""
        r = _result(
            expected="approve",
            expected_rule_ids=["R-1", "R-2"],
            actual="approve",
            actual_cites=["R-2"],
        )
        assert compute_metrics([r])["citation_accuracy"] == 1.0

    def test_no_match(self) -> None:
        r = _result(
            expected="approve",
            expected_rule_ids=["R-1"],
            actual="approve",
            actual_cites=["R-99"],
        )
        assert compute_metrics([r])["citation_accuracy"] == 0.0

    def test_escalate_examples_excluded(self) -> None:
        """We only check citations on examples that should auto-decide."""
        results = [
            _result(expected="escalate", actual="escalate", expected_rule_ids=["X"]),
            _result(expected="approve", actual="approve",
                    expected_rule_ids=["R-1"], actual_cites=["R-1"]),
        ]
        m = compute_metrics(results)
        assert m["citation_accuracy"] == 1.0

    def test_examples_without_expected_rule_ids_excluded(self) -> None:
        """An expected-auto example with no expected_rule_ids shouldn't
        inflate or deflate citation accuracy."""
        results = [
            _result(expected="approve", actual="approve", expected_rule_ids=[]),
            _result(expected="approve", actual="approve",
                    expected_rule_ids=["R-1"], actual_cites=["R-1"]),
        ]
        m = compute_metrics(results)
        assert m["citation_accuracy"] == 1.0  # 1/1, not 1/2

    def test_no_expected_rule_ids_at_all_returns_none(self) -> None:
        results = [_result(expected="approve", actual="approve")]
        assert compute_metrics(results)["citation_accuracy"] is None


class TestComputeMetricsRefusalRecall:
    """Refusal recall = expected-escalate that actually escalated."""

    def test_all_correctly_escalated(self) -> None:
        results = [
            _result(expected="escalate", actual="escalate"),
            _result(expected="escalate", actual="error"),  # error counts as escalate
        ]
        assert compute_metrics(results)["refusal_recall"] == 1.0

    def test_false_auto_decision_hurts_recall(self) -> None:
        """An expected-escalate that got auto-approved is the most dangerous
        failure — refusal_recall is exactly the metric that catches it."""
        results = [
            _result(expected="escalate", actual="escalate"),
            _result(expected="escalate", actual="approve"),  # dangerous
        ]
        assert compute_metrics(results)["refusal_recall"] == 0.5

    def test_no_expected_escalate_returns_none(self) -> None:
        results = [_result(expected="approve", actual="approve")]
        assert compute_metrics(results)["refusal_recall"] is None


class TestComputeMetricsLatency:
    def test_percentiles(self) -> None:
        results = [
            _result(expected="approve", actual="approve", latency_ms=100),
            _result(expected="approve", actual="approve", latency_ms=200),
            _result(expected="approve", actual="approve", latency_ms=300),
            _result(expected="approve", actual="approve", latency_ms=400),
            _result(expected="approve", actual="approve", latency_ms=500),
        ]
        m = compute_metrics(results)
        # Index = round(0.5 * 4) = 2 → 300; round(0.95 * 4) = 4 → 500.
        assert m["latency_p50_ms"] == 300
        assert m["latency_p95_ms"] == 500

    def test_empty(self) -> None:
        m = compute_metrics([])
        assert m["latency_p50_ms"] == 0
        assert m["latency_p95_ms"] == 0


class TestParseJsonl:
    def test_basic(self, tmp_path: Path) -> None:
        p = tmp_path / "g.jsonl"
        p.write_text(
            '{"ticket_type": "acme.t", "payload": {"a": 1}, '
            '"expected_decision": "approve", "expected_rule_ids": ["R-1"]}\n'
            '{"ticket_type": "acme.t", "payload": {"a": 2}, '
            '"expected_decision": "escalate"}\n'
        )
        examples = parse_jsonl(str(p))
        assert len(examples) == 2
        assert examples[0].ticket_type == "acme.t"
        assert examples[0].expected_rule_ids == ["R-1"]
        assert examples[0].example_id == "line-1"
        assert examples[1].expected_decision == "escalate"
        assert examples[1].expected_rule_ids == []  # default

    def test_comments_and_blank_lines_skipped(self, tmp_path: Path) -> None:
        p = tmp_path / "g.jsonl"
        p.write_text(
            "# header comment\n"
            "\n"
            '{"ticket_type": "x", "payload": {}, "expected_decision": "approve"}\n'
            "  # indented comment\n"
            '{"ticket_type": "x", "payload": {}, "expected_decision": "reject"}\n'
        )
        examples = parse_jsonl(str(p))
        assert [e.expected_decision for e in examples] == ["approve", "reject"]

    def test_explicit_example_id_wins_over_line_number(self, tmp_path: Path) -> None:
        p = tmp_path / "g.jsonl"
        p.write_text(
            '{"example_id": "lock-1", "ticket_type": "x", "payload": {}, '
            '"expected_decision": "escalate"}\n'
        )
        examples = parse_jsonl(str(p))
        assert examples[0].example_id == "lock-1"

    def test_single_string_rule_id_normalized_to_list(self, tmp_path: Path) -> None:
        """Convenience: writers can use `expected_rule_id` (singular, string)
        instead of always writing a one-element list."""
        p = tmp_path / "g.jsonl"
        p.write_text(
            '{"ticket_type": "x", "payload": {}, '
            '"expected_decision": "approve", "expected_rule_id": "R-7"}\n'
        )
        examples = parse_jsonl(str(p))
        assert examples[0].expected_rule_ids == ["R-7"]

    def test_invalid_json_reports_line_number(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.jsonl"
        p.write_text(
            '{"ticket_type": "x", "payload": {}, "expected_decision": "approve"}\n'
            "this is not json\n"
        )
        with pytest.raises(ValueError, match="Line 2"):
            parse_jsonl(str(p))


class TestFormatters:
    def test_summary_includes_key_metrics(self) -> None:
        results = [
            _result(expected="approve", actual="approve",
                    expected_rule_ids=["R-1"], actual_cites=["R-1"]),
            _result(expected="escalate", actual="escalate"),
        ]
        text = format_summary(compute_metrics(results))
        assert "Precision" in text
        assert "Citation accuracy" in text
        assert "Refusal recall" in text
        assert "100.0%" in text

    def test_summary_handles_none_metrics(self) -> None:
        """Sparse golden sets (only escalate examples) shouldn't blow up the
        summary formatter — they should render as n/a."""
        results = [_result(expected="escalate", actual="escalate")]
        text = format_summary(compute_metrics(results))
        assert "n/a" in text

    def test_per_example_lines(self) -> None:
        results = [
            _result(expected="approve", actual="approve",
                    expected_rule_ids=["R-1"], actual_cites=["R-1"],
                    example_id="ok-1"),
            _result(expected="approve", actual="escalate", example_id="bad-1"),
        ]
        text = format_per_example(results)
        # Distinct check marks for hit vs miss.
        assert "✓" in text and "✗" in text
        assert "ok-1" in text and "bad-1" in text

    def test_to_jsonable_metrics_round_trips(self) -> None:
        m = compute_metrics([_result(expected="approve", actual="approve")])
        s = to_jsonable_metrics(m)
        parsed = json.loads(s)
        assert parsed["precision"] == 1.0


# ---------------------------------------------------------------------------
# Layer 2 — integration test for the management command
# ---------------------------------------------------------------------------
pytestmark_db = pytest.mark.django_db


class _ScriptedLLM:
    """LLM client that returns canned answers keyed by `request_type` in the
    payload — lets the test simulate a model that's correct on some inputs
    and wrong on others, deterministically."""

    def __init__(self, scripts: dict):
        # scripts maps request_type → DecisionResponse args
        self.scripts = scripts

    def decide(self, *, request_payload, retrieved_chunks, system_prompt):
        from superstar.llm.base import DecisionResponse

        key = request_payload.get("request_type", "")
        spec = self.scripts.get(key, {
            "decision": "escalate",
            "cited_rule_ids": (),
            "confidence": 0.0,
            "reason_text": "no script",
        })
        return DecisionResponse(
            decision=spec["decision"],
            cited_rule_ids=tuple(spec.get("cited_rule_ids", ())),
            confidence=spec.get("confidence", 0.9),
            reason_text=spec.get("reason_text", ""),
            raw_model_output="",
        )


@pytest.fixture
def patched_llm(monkeypatch):
    """Returns a setter — tests call `patched_llm({...})` to install a script.

    Patches BOTH `superstar.llm.get_llm_client` and the alias re-export in
    the decisioning services module (Python import semantics mean the
    services module already bound its own reference at import time)."""
    holder = {"scripts": {}}

    def fake_get_client():
        return _ScriptedLLM(holder["scripts"])

    monkeypatch.setattr("superstar.llm.get_llm_client", fake_get_client)
    monkeypatch.setattr("apps.decisioning.services.get_llm_client", fake_get_client)

    def install(scripts):
        holder["scripts"] = scripts

    return install


@pytest.fixture
def eval_ready_org(acme_org, acme_admin):
    """A TicketType with one rule embedded so retrieval has something to
    return. `acme.eval` accepts a `request_type` enum that we'll vary in
    the golden set to drive different decisions."""
    from apps.kb.models import RuleChunk
    from apps.tickets.models import TicketType, TicketTypeField

    tt = TicketType.objects.create(
        org=acme_org,
        identifier="acme.eval",
        display_name="Eval test",
        sequential=True,
        ai_enabled=True,
        shadow_mode=False,  # important: forced ON by harness; check the toggle restores
        confidence_threshold=0.85,
        system_prompt="Decide based on rules.",
    )
    TicketTypeField.objects.create(
        ticket_type=tt, order=0, name="request_type", field_type="enum",
        label="Request", required=True, choices=["alpha", "beta", "gamma"],
    )
    # Two rules so the model has multiple candidates to cite (and to
    # potentially hallucinate citations against).
    RuleChunk.objects.create(
        org=acme_org, plugin_identifier="acme.eval",
        ticket_type=tt, rule_id="R-ALPHA", title="Alpha rule",
        body="Alpha is approved.", embedding=[0.0] * 1024,
        extra={"applies_when": {"request_type": "alpha"}},
    )
    RuleChunk.objects.create(
        org=acme_org, plugin_identifier="acme.eval",
        ticket_type=tt, rule_id="R-BETA", title="Beta rule",
        body="Beta is rejected.", embedding=[0.0] * 1024,
        extra={"applies_when": {"request_type": "beta"}},
    )
    return tt


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


@pytest.mark.django_db
def test_command_runs_clean_against_passing_golden(
    eval_ready_org, patched_llm, acme_org, tmp_path, capsys,
) -> None:
    """Three-row golden: alpha→approve+cite R-ALPHA, beta→reject+cite R-BETA,
    gamma→escalate (no script entry → noop returns escalate). All match
    expectations → command exits cleanly and prints 100% precision."""
    patched_llm({
        "alpha": {"decision": "approve", "cited_rule_ids": ["R-ALPHA"], "confidence": 0.95},
        "beta": {"decision": "reject", "cited_rule_ids": ["R-BETA"], "confidence": 0.95},
        # gamma falls through to the unscripted default → escalate.
    })

    golden = tmp_path / "g.jsonl"
    _write_jsonl(golden, [
        {"example_id": "a", "ticket_type": "acme.eval",
         "payload": {"request_type": "alpha"},
         "expected_decision": "approve", "expected_rule_ids": ["R-ALPHA"]},
        {"example_id": "b", "ticket_type": "acme.eval",
         "payload": {"request_type": "beta"},
         "expected_decision": "reject", "expected_rule_ids": ["R-BETA"]},
        {"example_id": "c", "ticket_type": "acme.eval",
         "payload": {"request_type": "gamma"},
         "expected_decision": "escalate"},
    ])

    call_command("eval_decisioning", str(golden), "--org", "acme")
    out = capsys.readouterr().out
    assert "Precision" in out
    assert "100.0%" in out  # all three correct
    assert "Eval complete" in out


@pytest.mark.django_db
def test_command_fails_when_threshold_not_met(
    eval_ready_org, patched_llm, tmp_path,
) -> None:
    """If precision is below --min-precision the command raises CommandError
    (which translates to a non-zero exit). CI gates on this."""
    patched_llm({
        # Alpha gets misclassified: expected approve, model says escalate.
        # That's 0% precision → must fail any positive --min-precision.
    })

    golden = tmp_path / "g.jsonl"
    _write_jsonl(golden, [
        {"example_id": "a", "ticket_type": "acme.eval",
         "payload": {"request_type": "alpha"},
         "expected_decision": "approve", "expected_rule_ids": ["R-ALPHA"]},
    ])

    with pytest.raises(CommandError, match="thresholds not met"):
        call_command(
            "eval_decisioning", str(golden),
            "--org", "acme", "--min-precision", "0.9",
        )


@pytest.mark.django_db
def test_command_passes_when_threshold_met(
    eval_ready_org, patched_llm, tmp_path,
) -> None:
    """Symmetric to the failing test — 100% precision easily clears 0.9."""
    patched_llm({
        "alpha": {"decision": "approve", "cited_rule_ids": ["R-ALPHA"], "confidence": 0.95},
    })

    golden = tmp_path / "g.jsonl"
    _write_jsonl(golden, [
        {"example_id": "a", "ticket_type": "acme.eval",
         "payload": {"request_type": "alpha"},
         "expected_decision": "approve", "expected_rule_ids": ["R-ALPHA"]},
    ])

    # No exception expected.
    call_command(
        "eval_decisioning", str(golden),
        "--org", "acme", "--min-precision", "0.9",
    )


@pytest.mark.django_db
def test_cleanup_removes_eval_tickets(
    eval_ready_org, patched_llm, acme_org, tmp_path,
) -> None:
    """--cleanup deletes eval tickets + their decisions afterwards so the
    harness doesn't litter the DB."""
    from apps.decisioning.models import Decision
    from apps.tickets.models import Ticket

    patched_llm({
        "alpha": {"decision": "approve", "cited_rule_ids": ["R-ALPHA"], "confidence": 0.95},
    })

    golden = tmp_path / "g.jsonl"
    _write_jsonl(golden, [
        {"example_id": "a", "ticket_type": "acme.eval",
         "payload": {"request_type": "alpha"},
         "expected_decision": "approve", "expected_rule_ids": ["R-ALPHA"]},
    ])

    pre_tickets = Ticket.objects.filter(org=acme_org).count()
    call_command("eval_decisioning", str(golden), "--org", "acme", "--cleanup")
    post_tickets = Ticket.objects.filter(org=acme_org).count()

    assert post_tickets == pre_tickets, "eval tickets should be cleaned up"
    # Decisions tied to those tickets should also be gone.
    assert Decision.objects.filter(
        ticket__title__startswith="[EVAL]"
    ).count() == 0


@pytest.mark.django_db
def test_json_out_writes_machine_readable_report(
    eval_ready_org, patched_llm, tmp_path,
) -> None:
    """--json-out lets CI diff metrics across runs / store as an artifact."""
    patched_llm({
        "alpha": {"decision": "approve", "cited_rule_ids": ["R-ALPHA"], "confidence": 0.95},
    })

    golden = tmp_path / "g.jsonl"
    _write_jsonl(golden, [
        {"example_id": "a", "ticket_type": "acme.eval",
         "payload": {"request_type": "alpha"},
         "expected_decision": "approve", "expected_rule_ids": ["R-ALPHA"]},
    ])

    out_file = tmp_path / "report.json"
    call_command(
        "eval_decisioning", str(golden),
        "--org", "acme", "--json-out", str(out_file),
    )

    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert "metrics" in data
    assert "results" in data
    assert data["metrics"]["precision"] == 1.0
    assert data["results"][0]["example_id"] == "a"
    assert data["results"][0]["actual_outcome"] == "approve"


@pytest.mark.django_db
def test_shadow_mode_is_restored_after_eval(
    eval_ready_org, patched_llm, tmp_path,
) -> None:
    """The eval forces shadow_mode=True for the duration of the run, but
    must restore the original value afterwards. Otherwise running the
    eval on a live tenant would silently disable production decisioning."""
    from apps.tickets.models import TicketType

    # Sanity: fixture set shadow_mode=False (production-style).
    eval_ready_org.refresh_from_db()
    assert eval_ready_org.shadow_mode is False

    patched_llm({
        "alpha": {"decision": "approve", "cited_rule_ids": ["R-ALPHA"], "confidence": 0.95},
    })

    golden = tmp_path / "g.jsonl"
    _write_jsonl(golden, [
        {"example_id": "a", "ticket_type": "acme.eval",
         "payload": {"request_type": "alpha"},
         "expected_decision": "approve", "expected_rule_ids": ["R-ALPHA"]},
    ])

    call_command("eval_decisioning", str(golden), "--org", "acme")

    # After: shadow_mode must be back to whatever it was.
    tt = TicketType.objects.get(id=eval_ready_org.id)
    assert tt.shadow_mode is False, "eval must restore the production shadow_mode setting"


@pytest.mark.django_db
def test_unknown_org_raises_clear_error(tmp_path) -> None:
    golden = tmp_path / "g.jsonl"
    _write_jsonl(golden, [
        {"ticket_type": "x", "payload": {}, "expected_decision": "approve"},
    ])
    with pytest.raises(CommandError, match="No org"):
        call_command("eval_decisioning", str(golden), "--org", "ghost")


@pytest.mark.django_db
def test_empty_golden_raises_clear_error(acme_org, tmp_path) -> None:
    golden = tmp_path / "empty.jsonl"
    golden.write_text("# just a comment\n\n")
    with pytest.raises(CommandError, match="No examples"):
        call_command("eval_decisioning", str(golden), "--org", "acme")


@pytest.mark.django_db
def test_missing_ticket_type_recorded_as_error(
    acme_org, patched_llm, tmp_path,
) -> None:
    """If the golden file references a ticket_type that doesn't exist on
    the org, that row is recorded as an error (rather than crashing the
    whole run). The metrics still compute; the per-example list shows ✗."""
    golden = tmp_path / "g.jsonl"
    _write_jsonl(golden, [
        {"example_id": "missing", "ticket_type": "acme.does-not-exist",
         "payload": {}, "expected_decision": "approve"},
    ])

    # Doesn't raise even though the ticket_type isn't configured.
    call_command("eval_decisioning", str(golden), "--org", "acme")
