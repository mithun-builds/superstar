"""Run the decisioning loop against a golden JSONL file and report metrics.

    python manage.py eval_decisioning <golden.jsonl> --org demo
    python manage.py eval_decisioning <golden.jsonl> --org demo --json-out out.json
    python manage.py eval_decisioning <golden.jsonl> --org demo --cleanup
    python manage.py eval_decisioning <golden.jsonl> --org demo \\
        --min-precision 0.98 --min-refusal-recall 0.95

JSONL example (one row per line):

    {"ticket_type": "homelane.nonstandard",
     "payload": {"request_type": "additional_lock", "type_of_shutter": "1-shutter"},
     "expected_decision": "escalate",
     "expected_rule_ids": ["NSD-LOCK-001"],
     "notes": "1-shutter lock — escalates per NSD-LOCK-001"}

Exit code is non-zero when any --min-* threshold isn't met, so this is
CI-friendly.
"""
from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.audit.models import AuditEvent
from apps.decisioning.eval import (
    GoldenExample,
    Result,
    compute_metrics,
    format_per_example,
    format_summary,
    parse_jsonl,
    to_jsonable_metrics,
)
from apps.decisioning.models import Decision
from apps.decisioning.services import decide
from apps.tenants.models import Org
from apps.tickets.models import ApprovalStage, Ticket, TicketType
from apps.tickets.services import TicketTypeNotFound, get_ticket_type


EVAL_TITLE_PREFIX = "[EVAL] "


class Command(BaseCommand):
    help = "Run the decisioning loop against a JSONL golden file and report metrics."

    def add_arguments(self, parser) -> None:
        parser.add_argument("golden", help="Path to a JSONL golden file.")
        parser.add_argument("--org", required=True, help="Org slug to run against.")
        parser.add_argument(
            "--json-out",
            default=None,
            help="Optional path to write the metrics dict + per-example results as JSON.",
        )
        parser.add_argument(
            "--cleanup",
            action="store_true",
            help="Delete the eval tickets + their decisions afterwards.",
        )
        parser.add_argument(
            "--min-precision",
            type=float,
            default=None,
            help="Fail the run (exit 1) if precision is below this fraction (0-1).",
        )
        parser.add_argument(
            "--min-citation-accuracy",
            type=float,
            default=None,
            help="Fail the run if citation accuracy is below this fraction.",
        )
        parser.add_argument(
            "--min-refusal-recall",
            type=float,
            default=None,
            help="Fail the run if refusal recall is below this fraction.",
        )

    def handle(self, *args, **opts) -> None:
        org_slug = opts["org"]
        try:
            org = Org.objects.get(slug=org_slug)
        except Org.DoesNotExist as exc:
            raise CommandError(f"No org with slug {org_slug!r}") from exc

        # Parse the golden file.
        examples = parse_jsonl(opts["golden"])
        if not examples:
            raise CommandError(f"No examples in {opts['golden']}")

        self.stdout.write(
            self.style.NOTICE(f"Evaluating {len(examples)} examples against org={org.slug}")
        )

        # Bind tenant context so RLS lets us read TicketType rows.
        from django.db import connection
        with connection.cursor() as cur:
            cur.execute("SELECT set_config('app.org_id', %s, true)", [str(org.id)])

        results: list[Result] = []
        eval_ticket_ids: list[str] = []
        requester = _get_or_create_eval_requester()

        for i, ex in enumerate(examples, start=1):
            self.stdout.write(f"  [{i:>3}/{len(examples)}] {ex.example_id}: {ex.ticket_type}")
            r = _run_one(org, ex, requester)
            results.append(r)
            if r.error:
                self.stdout.write(self.style.WARNING(f"      error: {r.error}"))
            # Track ticket IDs for optional cleanup.
            eval_ticket_ids.extend([t.id for t in Ticket.objects.filter(
                org=org, title__startswith=f"{EVAL_TITLE_PREFIX}{ex.example_id}"
            )])

        # Metrics + report.
        metrics = compute_metrics(results)
        self.stdout.write("")
        self.stdout.write("─" * 60)
        self.stdout.write(format_summary(metrics))
        self.stdout.write("")
        self.stdout.write("Per-example:")
        self.stdout.write(format_per_example(results))

        # Optional JSON output for diffing across runs.
        if opts["json_out"]:
            payload = {
                "metrics": metrics,
                "results": [
                    {
                        "example_id": r.example.example_id,
                        "expected_decision": r.example.expected_decision,
                        "expected_rule_ids": r.example.expected_rule_ids,
                        "actual_outcome": r.actual_outcome,
                        "actual_cited_rule_ids": r.actual_cited_rule_ids,
                        "actual_confidence": r.actual_confidence,
                        "latency_ms": r.latency_ms,
                        "decision_matches": r.decision_matches,
                        "citation_matches": r.citation_matches,
                        "error": r.error,
                    }
                    for r in results
                ],
            }
            with open(opts["json_out"], "w", encoding="utf-8") as f:
                f.write(to_jsonable_metrics(payload))
            self.stdout.write(self.style.NOTICE(f"Wrote {opts['json_out']}"))

        # Cleanup.
        if opts["cleanup"]:
            with transaction.atomic():
                ApprovalStage.objects.filter(ticket__id__in=eval_ticket_ids).delete()
                Decision.objects.filter(ticket__id__in=eval_ticket_ids).delete()
                AuditEvent.objects.filter(subject_id__in=[str(i) for i in eval_ticket_ids]).delete()
                Ticket.objects.filter(id__in=eval_ticket_ids).delete()
            self.stdout.write(self.style.NOTICE(f"Cleaned up {len(eval_ticket_ids)} eval tickets."))

        # Gate on thresholds (CI-friendly).
        thresholds = {
            "precision": opts["min_precision"],
            "citation_accuracy": opts["min_citation_accuracy"],
            "refusal_recall": opts["min_refusal_recall"],
        }
        failed = []
        for name, threshold in thresholds.items():
            if threshold is None:
                continue
            value = metrics.get(name)
            if value is None or value < threshold:
                failed.append(
                    f"{name}={value if value is not None else 'n/a'} < required {threshold}"
                )
        if failed:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("FAIL: threshold check"))
            for f_msg in failed:
                self.stdout.write(self.style.ERROR(f"  {f_msg}"))
            raise CommandError("Eval thresholds not met.")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Eval complete."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_or_create_eval_requester():
    """Tickets need a requester FK. Use a dedicated eval account so the
    real ticket-creation audit trail isn't polluted by these runs."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        email="eval-harness@superstar.internal",
        defaults={"full_name": "Eval Harness (internal)"},
    )
    return user


def _run_one(org, example: GoldenExample, requester) -> Result:
    """Create a temporary ticket, run decisioning synchronously, capture
    the result. Decision row is recorded with shadow_mode forced TRUE so
    the eval never mutates real tickets (no chain materialization, no
    ticket state transition)."""
    try:
        tt = get_ticket_type(org=org, identifier=example.ticket_type)
    except TicketTypeNotFound as exc:
        return Result(
            example=example,
            actual_outcome="error",
            actual_cited_rule_ids=[],
            actual_confidence=0.0,
            latency_ms=0,
            error=str(exc),
        )

    # Force shadow mode for the duration of this eval call by saving the
    # bit and flipping it temporarily. (Could also pass a shadow_mode
    # override into services.decide() — that's a cleaner v2.)
    original_shadow = tt.shadow_mode
    tt.shadow_mode = True
    tt.save(update_fields=["shadow_mode"])

    try:
        ticket = Ticket.objects.create(
            org=org,
            requester=requester,
            ticket_type=example.ticket_type,
            title=f"{EVAL_TITLE_PREFIX}{example.example_id}",
            payload=dict(example.payload),  # avoid mutation through reference
        )
        t0 = time.monotonic()
        decision = decide(ticket=ticket, system_prompt=tt.system_prompt)
        latency_ms = int((time.monotonic() - t0) * 1000)

        return Result(
            example=example,
            actual_outcome=decision.outcome,
            actual_cited_rule_ids=list(decision.cited_rule_ids or []),
            actual_confidence=float(decision.confidence),
            latency_ms=latency_ms,
        )
    finally:
        tt.shadow_mode = original_shadow
        tt.save(update_fields=["shadow_mode"])
