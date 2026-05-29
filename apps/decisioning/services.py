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
    """Run the decisioning loop for one ticket. Always writes a Decision row."""
    chunks = _retrieve(ticket, top_k=TOP_K)

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
        return _record(
            ticket=ticket,
            outcome=Decision.Outcome.ERROR,
            response=None,
            chunks=chunks,
            error=str(exc),
        )

    # Guard 1: citation present
    if not response.cited_rule_ids:
        return _record(
            ticket=ticket,
            outcome=Decision.Outcome.ESCALATED,
            response=dc_replace(response, reason_text="No rule_ids cited."),
            chunks=chunks,
        )

    # Guard 2: citation verification — every cited id must appear in retrieved chunks.
    retrieved_ids = {c.rule_id for c in chunks}
    unknown = [r for r in response.cited_rule_ids if r not in retrieved_ids]
    if unknown:
        logger.warning("Hallucinated rule_ids in decision for ticket %s: %s", ticket.id, unknown)
        return _record(
            ticket=ticket,
            outcome=Decision.Outcome.ESCALATED,
            response=response,
            chunks=chunks,
            note=f"Hallucinated rule_ids: {unknown}",
        )

    # Guard 3: applicability verification — each cited rule's applies_when
    # conditions must be satisfied by the request payload. Catches cases
    # where the model picks a structurally-valid rule that doesn't cover
    # this request (e.g. citing the PU-finish rule for a Laminate request).
    from superstar.applies_when import applies_to

    chunks_by_id = {c.rule_id: c for c in chunks}
    applicability_failures: list[str] = []
    for cite_id in response.cited_rule_ids:
        rule = chunks_by_id[cite_id]
        conditions = (rule.extra or {}).get("applies_when") if hasattr(rule, "extra") else None
        # RuleChunk stores frontmatter splat in `extra` (everything not pulled
        # into typed columns). If applies_when wasn't captured, the rule has
        # no constraints — pass.
        ok, reasons = applies_to(conditions, ticket.payload)
        if not ok:
            applicability_failures.append(f"{cite_id}: {'; '.join(reasons)}")

    if applicability_failures:
        logger.info("Cited rules failed applies_when check for ticket %s: %s",
                    ticket.id, applicability_failures)
        return _record(
            ticket=ticket,
            outcome=Decision.Outcome.ESCALATED,
            response=response,
            chunks=chunks,
            note=f"Inapplicable citations: {applicability_failures}",
        )

    # Guard 4: confidence threshold
    threshold = float(settings.DECISIONING["CONFIDENCE_THRESHOLD"])
    if response.confidence < threshold:
        return _record(
            ticket=ticket,
            outcome=Decision.Outcome.ESCALATED,
            response=response,
            chunks=chunks,
            note=f"Confidence {response.confidence:.3f} below threshold {threshold}",
        )

    # All guards passed — record the decision.
    outcome_map = {
        "approve": Decision.Outcome.APPROVED,
        "reject": Decision.Outcome.REJECTED,
        "escalate": Decision.Outcome.ESCALATED,
    }
    decision = _record(
        ticket=ticket,
        outcome=outcome_map[response.decision],
        response=response,
        chunks=chunks,
    )

    # Apply to ticket only if not shadow mode.
    if not settings.DECISIONING["SHADOW_MODE"]:
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

    return list(
        RuleChunk.objects
        .filter(org=ticket.org, plugin_identifier=ticket.ticket_type)
        .order_by(RuleChunk.embedding.cosine_distance(query_vec))[:top_k]
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

    On escalate: materializes the approval chain so the human reviewers
    have their stages set up immediately.
    """
    from apps.audit.services import log_event

    if decision.outcome == Decision.Outcome.APPROVED:
        ticket.status = Ticket.Status.DECIDED
        ticket.decision_summary = decision.reason_text
    elif decision.outcome == Decision.Outcome.REJECTED:
        ticket.status = Ticket.Status.DECIDED
        ticket.decision_summary = decision.reason_text
    elif decision.outcome == Decision.Outcome.ESCALATED:
        ticket.status = Ticket.Status.ESCALATED
    ticket.updated_at = timezone.now()
    ticket.save(update_fields=["status", "decision_summary", "updated_at"])

    log_event(
        event_type="decision.applied",
        org=ticket.org,
        subject=ticket,
        data={"decision_id": str(decision.id), "outcome": decision.outcome, "new_status": ticket.status},
    )

    # Materialize the approval chain on escalation so reviewers have something
    # to act on. Idempotent — re-escalation is a no-op.
    if decision.outcome == Decision.Outcome.ESCALATED:
        from apps.tickets.approval import materialize_stages

        materialize_stages(ticket)
