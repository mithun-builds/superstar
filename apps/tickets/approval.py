"""Approval chain execution — materializes plugin WorkflowSpec into rows,
advances stages on decisions, transitions the parent Ticket.

Design choices baked in here:

- **Eager materialization.** When a ticket escalates, every stage from the
  plugin's WorkflowSpec gets an ApprovalStage row up front. Pending stages
  are visible immediately ("you'll see this go to ops next"). Cheaper to
  reason about than lazy creation.

- **The "active stage" is derived.** It's the lowest-order stage with
  `status = PENDING`. No separate FK on Ticket. Saves a migration; the
  query is indexed by (ticket, order).

- **One-strike-out on reject.** Any stage rejecting → ticket REJECTED.
  Phase 2 could add a "retry from this stage" workflow; not v0.

- **Mode `any_member` is fully implemented.** Other modes (unanimous_team,
  majority, specific_user) are accepted by the loader but treated as
  any_member at runtime with a TODO. Real implementation needs per-stage
  approver tracking — bigger lift.

- **Audit log.** Every state transition writes one AuditEvent.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import transaction
from django.utils import timezone

from .models import ApprovalStage, Ticket
from .services import get_ticket_type

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

logger = logging.getLogger(__name__)


class ApprovalError(Exception):
    """Raised on illegal stage decisions (out-of-order, already-decided, etc)."""


@transaction.atomic
def materialize_stages(ticket: Ticket) -> list[ApprovalStage]:
    """Create ApprovalStage rows from the plugin's WorkflowSpec.

    Idempotent: if stages already exist for this ticket, returns them
    untouched. Re-running is safe (e.g. on a retried escalation).
    """
    existing = list(ticket.stages.order_by("order"))
    if existing:
        return existing

    tt = get_ticket_type(org=ticket.org, identifier=ticket.ticket_type)

    stages: list[ApprovalStage] = []
    for spec in tt.workflow_stages.order_by("order"):
        stages.append(
            ApprovalStage.objects.create(
                org=ticket.org,
                ticket=ticket,
                order=spec.order or (len(stages) + 1),
                name=spec.name,
                mode=spec.mode,
                status=ApprovalStage.Status.PENDING,
            )
        )

    # Audit — late import to avoid app-loading order issues.
    from apps.audit.services import log_event

    log_event(
        event_type="ticket.escalated",
        org=ticket.org,
        subject=ticket,
        data={"stage_count": len(stages), "stage_names": [s.name for s in stages]},
    )
    return stages


def current_stage(ticket: Ticket) -> ApprovalStage | None:
    """The lowest-order pending stage, or None if the chain is done.

    "Done" includes both natural completion (all stages decided) and
    early termination (the ticket transitioned to APPROVED, REJECTED, or
    CLOSED — meaning a rejection stopped the chain or the final stage
    closed it). In those cases later pending stages exist as historical
    placeholders but aren't actionable.
    """
    terminal = {Ticket.Status.APPROVED, Ticket.Status.REJECTED, Ticket.Status.CLOSED}
    if ticket.status in terminal:
        return None
    return ticket.stages.filter(status=ApprovalStage.Status.PENDING).order_by("order").first()


@transaction.atomic
def decide_stage(
    *,
    stage: ApprovalStage,
    user: "AbstractBaseUser",
    decision: str,
    note: str = "",
) -> Ticket:
    """Apply a human decision to a stage. Advances the chain or closes the ticket.

    `decision` must be `"approved"` or `"rejected"`. Returns the parent
    ticket with its updated status. Raises ApprovalError on:
    - stage already decided
    - stage not the current (lowest-order pending) stage — out-of-order decisions
      are forbidden in v0 sequential mode
    - invalid `decision` value
    """
    if decision not in (ApprovalStage.Status.APPROVED, ApprovalStage.Status.REJECTED):
        raise ApprovalError(f"Invalid stage decision: {decision!r}")
    if stage.status != ApprovalStage.Status.PENDING:
        raise ApprovalError(f"Stage {stage.name} already decided ({stage.status})")

    ticket = stage.ticket
    # In sequential workflows, only the current stage may be decided.
    tt = get_ticket_type(org=ticket.org, identifier=ticket.ticket_type)
    if tt.sequential:
        cur = current_stage(ticket)
        if cur is None or cur.id != stage.id:
            raise ApprovalError(
                f"Out-of-order decision on stage {stage.name}; current active stage is "
                f"{cur.name if cur else 'none'}"
            )

    stage.status = decision
    stage.decided_by = user
    stage.decided_at = timezone.now()
    stage.note = note
    stage.save(update_fields=["status", "decided_by", "decided_at", "note"])

    from apps.audit.services import log_event

    log_event(
        event_type="stage.decided",
        actor=user,
        org=ticket.org,
        subject=ticket,
        data={"stage": stage.name, "stage_id": str(stage.id), "decision": decision, "note": note},
    )

    # Advance the ticket.
    if decision == ApprovalStage.Status.REJECTED:
        _close_ticket(ticket, Ticket.Status.REJECTED, summary=f"Rejected at stage: {stage.name}")
    else:
        # Approved — is there a next stage?
        next_stage = current_stage(ticket)
        if next_stage is None:
            _close_ticket(ticket, Ticket.Status.APPROVED, summary="All approval stages passed.")

    return ticket


def _close_ticket(ticket: Ticket, status: str, summary: str) -> None:
    ticket.status = status
    ticket.decision_summary = summary
    ticket.closed_at = timezone.now()
    ticket.save(update_fields=["status", "decision_summary", "closed_at", "updated_at"])

    from apps.audit.services import log_event

    log_event(
        event_type="ticket.closed",
        org=ticket.org,
        subject=ticket,
        data={"final_status": status, "summary": summary},
    )
