"""Celery task for async decisioning.

The HTTP /decide/ endpoint dispatches this task and returns 202 with the
Celery task UUID. The worker calls services.decide(), which writes a
Decision row stamped with the task_id. The polling endpoint
(GET /api/decisions/by-task/<task_id>/) returns 202 until the row appears,
then 200 with the decision payload.

Why a task, not just a thread:
- LLM calls block for 1-10s. Tying up an HTTP worker for that long is
  fine in dev but exhausts the worker pool under any real load.
- Celery gives us retry semantics, structured logging, and a clean
  separation of LLM ops from the HTTP transaction.
- Workers can scale independently — when HomeLane volume is high, add
  more workers without touching the API tier.

Tests run with CELERY_TASK_ALWAYS_EAGER=True so the task executes inline.
"""
from __future__ import annotations

import logging
import uuid

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def run_decisioning(self, *, ticket_id: str) -> str:
    """Run the decisioning loop for a ticket. Returns the resulting Decision id.

    Retries twice on transient failures (Ollama hiccup, network blip).
    After max retries, the wrapping decisioning service writes a Decision
    with outcome=ERROR which causes the ticket to escalate — same as if
    the LLM had returned malformed output.
    """
    # Late imports — avoid loading app models at task-module import time.
    from apps.tickets.models import Ticket
    from apps.tickets.services import TicketTypeNotFound, get_ticket_type

    from .services import decide

    ticket = Ticket.objects.get(id=ticket_id)
    started = timezone.now()

    try:
        tt = get_ticket_type(org=ticket.org, identifier=ticket.ticket_type)
    except TicketTypeNotFound:
        logger.exception("ticket_type missing at task time: ticket=%s", ticket_id)
        # Bail with an ERROR decision so the ticket escalates rather than vanish.
        from .models import Decision

        d = Decision.objects.create(
            org=ticket.org,
            ticket=ticket,
            outcome=Decision.Outcome.ERROR,
            confidence=0.0,
            reason_text="Ticket type configuration not found at decision time.",
            task_id=uuid.UUID(self.request.id),
            started_at=started,
        )
        return str(d.id)

    decision = decide(
        ticket=ticket,
        system_prompt=tt.system_prompt,
        task_id=uuid.UUID(self.request.id),
        started_at=started,
    )
    return str(decision.id)
