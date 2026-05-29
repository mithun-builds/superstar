"""The decisioning service — the loop SuperStar exists to run.

```
ticket ──► retrieve_chunks ──► LLMClient.decide ──► 4 guards ──► apply or escalate
```

Four guards run *after* the model answers:
1. **Citation present?** Empty `cited_rule_ids` → escalate.
2. **Citations real?** Each id must appear in the retrieved chunks. Catches
   hallucinated ids (model invented an id that doesn't exist).
3. **Citations applicable?** Each cited rule's `applies_when` conditions must
   be satisfied by the request payload. Catches the subtler failure where the
   model cites a real, retrieved rule that doesn't actually cover the request
   (the failure mode the NSD smoke surfaced repeatedly on small models).
4. **Confidence threshold?** Below floor → escalate.

Shadow mode (default true in dev): the Decision row is written and visible
in admin, but Ticket.status is NOT mutated. Flip `DECISIONING.SHADOW_MODE`
to False to enable write-back.
"""
from __future__ import annotations

import logging
from dataclasses import replace as dc_replace
from typing import Iterable

from django.conf import settings
from django.utils import timezone

from apps.kb.models import RuleChunk
from apps.tickets.models import Ticket
from superstar.llm import DecisionResponse, LLMError, get_llm_client
from superstar.llm.base import RetrievedChunk

from .models import Decision

logger = logging.getLogger(__name__)

# Bump retrieval count when rules get richer / more numerous. 8 is a starting
# point for a small KB like NSD.AI (~20 scenarios). For larger KBs, tune via
# eval harness.
TOP_K = 8


def decide(*, ticket: Ticket, system_prompt: str) -> Decision:
    """Run the decisioning loop for one ticket. Always writes a Decision row.

    Reads `shadow_mode` and `confidence_threshold` from the TicketType row
    (DB-native config). Settings-level DECISIONING defaults remain as
    fallbacks for tests or deployments without a configured TicketType.
    """
    from apps.tickets.services import TicketTypeNotFound, get_ticket_type

    try:
        tt = get_ticket_type(org=ticket.org, identifier=ticket.ticket_type)
        confidence_threshold = tt.confidence_threshold
        shadow_mode = tt.shadow_mode
    except TicketTypeNotFound:
        # Should not happen — viewset validates before calling — but fall back
        # to settings defaults so the function is callable from contexts that
        # don't go through the viewset (tests, background jobs).
        confidence_threshold = float(settings.DECISIONING["CONFIDENCE_THRESHOLD"])
        shadow_mode = bool(settings.DECISIONING["SHADOW_MODE"])

    chunks = _retrieve(ticket, top_k=TOP_K)

    # ----- single pass to compute (outcome, response, guard_note) -----
    outcome: str
    guard_note: str = ""
    response: DecisionResponse | None
    try:
        client = get_llm_client()
        response = client.decide(
            request_payload=ticket.payload,
            retrieved_chunks=[
                RetrievedChunk(
                    rule_id=c.rule_id,
                    text=c.body,
                    score=getattr(c, "_distance", 0.0),
                    source_path=c.source_path,
                )
                for c in chunks
            ],
            system_prompt=system_prompt,
        )
    except LLMError as exc:
        logger.exception("LLM call failed for ticket %s", ticket.id)
        outcome = Decision.Outcome.ERROR
        guard_note = f"LLM error: {exc}"
        response = None

    if response is not None:
        # Guard 1: citation present
        if not response.cited_rule_ids:
            outcome = Decision.Outcome.ESCALATED
            response = dc_replace(response, reason_text="No rule_ids cited.")
            guard_note = "No rule_ids cited."
        else:
            # Guard 2: citation verification — every cited id must appear in retrieved chunks.
            retrieved_ids = {c.rule_id for c in chunks}
            unknown = [r for r in response.cited_rule_ids if r not in retrieved_ids]
            if unknown:
                logger.warning(
                    "Hallucinated rule_ids in decision for ticket %s: %s", ticket.id, unknown
                )
                outcome = Decision.Outcome.ESCALATED
                guard_note = f"Hallucinated rule_ids: {unknown}"
            else:
                # Guard 3: applicability — each cited rule's applies_when must match the payload.
                from superstar.applies_when import applies_to

                chunks_by_id = {c.rule_id: c for c in chunks}
                failures: list[str] = []
                for cite_id in response.cited_rule_ids:
                    rule = chunks_by_id[cite_id]
                    conditions = (rule.extra or {}).get("applies_when") if hasattr(rule, "extra") else None
                    ok, reasons = applies_to(conditions, ticket.payload)
                    if not ok:
                        failures.append(f"{cite_id}: {'; '.join(reasons)}")

                if failures:
                    logger.info(
                        "Cited rules failed applies_when for ticket %s: %s", ticket.id, failures
                    )
                    outcome = Decision.Outcome.ESCALATED
                    guard_note = f"Inapplicable citations: {failures}"
                elif response.confidence < confidence_threshold:
                    # Guard 4: confidence threshold
                    outcome = Decision.Outcome.ESCALATED
                    guard_note = (
                        f"Confidence {response.confidence:.3f} below threshold {confidence_threshold}"
                    )
                else:
                    # All guards passed — honor the model's decision.
                    outcome = {
                        "approve": Decision.Outcome.APPROVED,
                        "reject": Decision.Outcome.REJECTED,
                        "escalate": Decision.Outcome.ESCALATED,
                    }[response.decision]

    # ----- single record + conditional apply -----
    decision = _record(
        ticket=ticket,
        outcome=outcome,
        response=response,
        chunks=chunks,
        note=guard_note,
    )
    if decision.shadow_mode != shadow_mode:
        decision.shadow_mode = shadow_mode
        decision.save(update_fields=["shadow_mode"])

    if not shadow_mode:
        _apply_to_ticket(ticket, decision)

    return decision


def _retrieve(ticket: Ticket, *, top_k: int) -> list[RuleChunk]:
    """Vector search over the org's KB for this ticket's plugin.

    The query is built from the ticket's payload — stringify dropdowns and
    free-text fields. Phase 2 will tune this (hybrid BM25+vector, field-aware).
    """
    from django.db import connection

    query_text = _payload_to_query(ticket.payload)
    # Embed query — wrapper imported lazily to avoid loading the model at app startup.
    from .embedding import embed

    query_vec = embed(query_text)

    from pgvector.django import CosineDistance

    return list(
        RuleChunk.objects
        .filter(org=ticket.org, plugin_identifier=ticket.ticket_type)
        .order_by(CosineDistance("embedding", query_vec))[:top_k]
    )


def _payload_to_query(payload: dict) -> str:
    """Flatten the structured payload into a single string for embedding.

    Naive in v0: just join "<key>: <value>" pairs. Phase 2 can use the plugin
    schema to weight fields, but the current rulebook is structured enough
    that naive concatenation works.
    """
    parts = []
    for k, v in payload.items():
        if v is None or v == "":
            continue
        parts.append(f"{k}: {v}")
    return ". ".join(parts)


def _record(
    *,
    ticket: Ticket,
    outcome: str,
    response: DecisionResponse | None,
    chunks: Iterable[RuleChunk],
    note: str = "",
    error: str = "",
) -> Decision:
    chunk_ids = [str(c.id) for c in chunks]
    extra_reason = f"{note}\n{error}".strip()

    decision = Decision.objects.create(
        org=ticket.org,
        ticket=ticket,
        outcome=outcome,
        cited_rule_ids=list(response.cited_rule_ids) if response else [],
        confidence=response.confidence if response else 0.0,
        reason_text=(response.reason_text if response else "") + ("\n" + extra_reason if extra_reason else ""),
        price_delta=response.price_delta if response else 0,
        post_actions=list(response.post_actions) if response else [],
        retrieved_chunk_ids=chunk_ids,
        raw_model_output=response.raw_model_output if response else "",
        model_name=settings.LLM["MODEL"],
        shadow_mode=settings.DECISIONING["SHADOW_MODE"],
    )

    # Audit — every decision attempt is logged (auto-decide, escalate, or error).
    from apps.audit.services import log_event

    log_event(
        event_type="decision.emitted",
        org=ticket.org,
        subject=ticket,
        data={
            "decision_id": str(decision.id),
            "outcome": outcome,
            "cited_rule_ids": decision.cited_rule_ids,
            "confidence": decision.confidence,
            "shadow_mode": decision.shadow_mode,
            "guard_note": extra_reason or None,
        },
    )

    return decision


def _apply_to_ticket(ticket: Ticket, decision: Decision) -> None:
    """Mutate ticket status based on a decision. Only called when not in shadow.

    Outcomes:
    - APPROVED / REJECTED → ticket moves to DECIDED with a summary, no chain.
    - ESCALATED → ticket moves to ESCALATED, approval chain materialized.
    - ERROR → treated identically to ESCALATED. A failed LLM call should
      send the ticket to humans, not leave it stuck in OPEN. The Decision
      row's reason_text carries the error detail for the audit trail.
    """
    from apps.audit.services import log_event

    if decision.outcome == Decision.Outcome.APPROVED:
        ticket.status = Ticket.Status.DECIDED
        ticket.decision_summary = decision.reason_text
    elif decision.outcome == Decision.Outcome.REJECTED:
        ticket.status = Ticket.Status.DECIDED
        ticket.decision_summary = decision.reason_text
    elif decision.outcome in (Decision.Outcome.ESCALATED, Decision.Outcome.ERROR):
        ticket.status = Ticket.Status.ESCALATED
    ticket.updated_at = timezone.now()
    ticket.save(update_fields=["status", "decision_summary", "updated_at"])

    log_event(
        event_type="decision.applied",
        org=ticket.org,
        subject=ticket,
        data={"decision_id": str(decision.id), "outcome": decision.outcome, "new_status": ticket.status},
    )

    # Materialize the approval chain on escalation AND on error so reviewers
    # always have stages to act on. Idempotent — re-escalation is a no-op.
    if decision.outcome in (Decision.Outcome.ESCALATED, Decision.Outcome.ERROR):
        from apps.tickets.approval import materialize_stages

        materialize_stages(ticket)
