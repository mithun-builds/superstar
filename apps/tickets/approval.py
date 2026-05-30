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

from apps.tenants.models import OrgMembership, Team, TeamMembership

from .models import ApprovalStage, StageVote, Ticket
from .services import get_ticket_type

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

logger = logging.getLogger(__name__)


class ApprovalError(Exception):
    """Raised on illegal stage decisions (out-of-order, already-decided, etc)."""


class StageAuthError(ApprovalError):
    """User isn't authorized to decide this stage — not a member of any
    of the stage's approver teams (and not an org owner/admin/superuser
    that bypasses team membership)."""


def can_decide_stage(*, user, stage: ApprovalStage, org) -> bool:
    """Whether `user` is allowed to act on this stage.

    Bypass rules — for "configure-the-platform" personas:
        - Platform superusers
        - Org owners (`OrgMembership.role = owner`)
        - Org admins (`OrgMembership.role = admin`)

    Mode-dependent rules otherwise:
        - `specific_user`: stage.approvers is interpreted as a list of
          user emails. The user is allowed iff their email is in that list.
        - All other modes: stage.approvers is a list of team slugs. The
          user is allowed iff they're a TeamMembership of any of them.

    Empty `stage.approvers` → fall back to "any org member can decide".
    Mis-configured stages stay actionable rather than silently un-actionable.
    """
    if getattr(user, "is_superuser", False):
        return True
    if OrgMembership.objects.filter(
        org=org,
        user=user,
        role__in=(OrgMembership.Role.OWNER, OrgMembership.Role.ADMIN),
    ).exists():
        return True
    if not stage.approvers:
        return OrgMembership.objects.filter(org=org, user=user).exists()
    if stage.mode == "specific_user":
        return getattr(user, "email", None) in stage.approvers
    return TeamMembership.objects.filter(
        user=user,
        team__org=org,
        team__slug__in=stage.approvers,
    ).exists()


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
                approvers=list(spec.approvers or []),  # snapshot at escalation time
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
    """Record one user's vote on a stage; close the stage if the mode threshold is met.

    Per-mode close logic (see `_evaluate_stage_outcome`):
    - `any_member`     — first vote (approve or reject) closes the stage
    - `unanimous_team` — any reject closes as REJECTED; else closes APPROVED
                         when every required voter has voted approve
    - `majority`       — closes APPROVED when >50% of required voters approved,
                         REJECTED when >50% rejected
    - `specific_user`  — that user's single vote closes the stage

    Raises:
      ApprovalError    — out-of-order, stage already decided, bad decision string
      StageAuthError   — user can't act on this stage
      (a vote re-submission by the same user is a no-op and returns the ticket)
    """
    if decision not in (StageVote.Decision.APPROVED, StageVote.Decision.REJECTED):
        raise ApprovalError(f"Invalid stage decision: {decision!r}")
    if stage.status != ApprovalStage.Status.PENDING:
        raise ApprovalError(f"Stage {stage.name} already decided ({stage.status})")

    ticket = stage.ticket
    if not can_decide_stage(user=user, stage=stage, org=ticket.org):
        raise StageAuthError(
            f"Not authorized to decide stage {stage.name!r} "
            f"(approvers: {list(stage.approvers)})"
        )

    # In sequential workflows, only the current stage may be decided.
    tt = get_ticket_type(org=ticket.org, identifier=ticket.ticket_type)
    if tt.sequential:
        cur = current_stage(ticket)
        if cur is None or cur.id != stage.id:
            raise ApprovalError(
                f"Out-of-order decision on stage {stage.name}; current active stage is "
                f"{cur.name if cur else 'none'}"
            )

    # Record the vote (idempotent — duplicate vote raises a clear error).
    if StageVote.objects.filter(stage=stage, user=user).exists():
        raise ApprovalError(
            f"You've already voted on stage {stage.name!r}. Votes are not editable in v0."
        )
    vote = StageVote.objects.create(stage=stage, user=user, decision=decision, note=note)

    from apps.audit.services import log_event

    log_event(
        event_type="stage.decided",  # event_type kept for back-compat with audit consumers
        actor=user,
        org=ticket.org,
        subject=ticket,
        data={
            "stage": stage.name,
            "stage_id": str(stage.id),
            "decision": decision,
            "note": note,
            "mode": stage.mode,
            "vote_id": str(vote.id),
        },
    )

    # Evaluate whether the stage should close given the current vote set.
    outcome = _evaluate_stage_outcome(stage, ticket.org)
    if outcome is None:
        # Stage stays open — more votes needed under this mode. Ticket stays escalated.
        return ticket

    # Stage closes. Stamp the deciding vote onto the stage for back-compat
    # with the existing serializer/audit shape.
    stage.status = outcome
    stage.decided_by = vote.user
    stage.decided_at = vote.decided_at
    stage.note = vote.note
    stage.save(update_fields=["status", "decided_by", "decided_at", "note"])

    # Advance the chain or close the ticket.
    if outcome == ApprovalStage.Status.REJECTED:
        _close_ticket(ticket, Ticket.Status.REJECTED, summary=f"Rejected at stage: {stage.name}")
    else:
        next_stage = current_stage(ticket)
        if next_stage is None:
            _close_ticket(ticket, Ticket.Status.APPROVED, summary="All approval stages passed.")

    return ticket


def _required_voter_count(stage: ApprovalStage, org) -> int:
    """How many users are in the universe that can decide this stage.

    Used by unanimous_team + majority to know when the threshold is hit.
    For specific_user it's len(approvers). For team-based modes it's the
    distinct count of TeamMembership.user across the named teams. For
    empty approvers (fallback "any org member") it's the OrgMembership count.
    """
    if stage.mode == "specific_user":
        return len(stage.approvers or [])
    if not stage.approvers:
        return OrgMembership.objects.filter(org=org).count()
    # Team-based: distinct user count across the named teams.
    return (
        TeamMembership.objects
        .filter(team__org=org, team__slug__in=stage.approvers)
        .values("user_id")
        .distinct()
        .count()
    )


def _evaluate_stage_outcome(stage: ApprovalStage, org) -> str | None:
    """Inspect the votes on a stage and return its new status, or None if the
    stage should remain PENDING (more votes needed).

    Returns:
      "approved" / "rejected" — close the stage with this status
      None — leave PENDING
    """
    approves = stage.votes.filter(decision=StageVote.Decision.APPROVED).count()
    rejects = stage.votes.filter(decision=StageVote.Decision.REJECTED).count()
    needed = _required_voter_count(stage, org)

    mode = stage.mode or "any_member"

    if mode == "any_member":
        # First vote closes the stage.
        if rejects > 0:
            return ApprovalStage.Status.REJECTED
        if approves > 0:
            return ApprovalStage.Status.APPROVED
        return None

    if mode == "specific_user":
        # The designated user's vote IS the stage decision.
        if rejects > 0:
            return ApprovalStage.Status.REJECTED
        if approves > 0:
            return ApprovalStage.Status.APPROVED
        return None

    if mode == "unanimous_team":
        # Any reject short-circuits to rejected; approve requires every required voter.
        if rejects > 0:
            return ApprovalStage.Status.REJECTED
        if needed > 0 and approves >= needed:
            return ApprovalStage.Status.APPROVED
        # Edge case: 0 required voters (empty universe). Treat first approve as
        # closing, same as any_member — safer than leaving forever-pending.
        if needed == 0 and approves > 0:
            return ApprovalStage.Status.APPROVED
        return None

    if mode == "majority":
        if needed <= 0:
            return ApprovalStage.Status.APPROVED if approves > 0 else None
        # Strict majority — >50%. Half-and-half stays open.
        threshold = needed // 2 + 1
        if approves >= threshold:
            return ApprovalStage.Status.APPROVED
        if rejects >= threshold:
            return ApprovalStage.Status.REJECTED
        return None

    # Unknown mode: fall back to any_member to keep things actionable.
    logger.warning("Unknown stage mode %r on stage %s; falling back to any_member", mode, stage.id)
    if rejects > 0:
        return ApprovalStage.Status.REJECTED
    if approves > 0:
        return ApprovalStage.Status.APPROVED
    return None


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
