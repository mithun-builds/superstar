"""No-op LLM client — for CI and unit tests.

Returns a deterministic 'escalate' decision so tests that exercise the
decisioning loop don't require a running LLM.
"""
from __future__ import annotations

from .base import DecisionResponse, RetrievedChunk


class NoOpClient:
    def decide(
        self,
        *,
        request_payload: dict,
        retrieved_chunks: list[RetrievedChunk],
        system_prompt: str,
    ) -> DecisionResponse:
        return DecisionResponse(
            decision="escalate",
            cited_rule_ids=(),
            confidence=0.0,
            reason_text="LLM_PROVIDER=noop — escalating by default.",
            raw_model_output="",
        )
