"""LLMClient interface — the only contract the decisioning layer depends on.

Design rules:
- Backends emit `DecisionResponse` (structured), never raw text. The grounding
  contract is enforced by the schema, not by prompt engineering alone.
- `decide()` is the only method the decisioning service calls. Everything else
  (chat completion, embeddings) goes via separate interfaces if/when needed.
- `cited_rule_ids` is what the citation verifier checks against retrieved
  chunks. Hallucinated IDs are caught mechanically, not heuristically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol


class LLMError(Exception):
    """Raised by backends on transport / parsing failures."""


Decision = Literal["approve", "reject", "escalate"]


@dataclass(frozen=True)
class RetrievedChunk:
    """One chunk handed to the LLM for grounding."""
    rule_id: str
    text: str
    score: float
    source_path: str  # human-readable identifier (e.g. "kb_rulechunk:<id>")


@dataclass(frozen=True)
class DecisionResponse:
    """Structured output the model must produce.

    The decisioning service refuses any response that doesn't fit this shape.
    Confidence is the model's self-report; calibrate against eval data — never
    trust raw confidence to gate auto-write-back without a precision check.
    """
    decision: Decision
    cited_rule_ids: tuple[str, ...]
    confidence: float
    reason_text: str
    price_delta: float = 0.0
    post_actions: tuple[str, ...] = field(default_factory=tuple)
    raw_model_output: str = ""  # kept for audit log


class LLMClient(Protocol):
    """All backends implement this. `decide()` is the load-bearing method."""

    def decide(
        self,
        *,
        request_payload: dict,
        retrieved_chunks: list[RetrievedChunk],
        system_prompt: str,
    ) -> DecisionResponse:
        """Issue a grounded decision.

        Implementations must:
        1. Pass `retrieved_chunks` as the only ground-truth context.
        2. Request structured JSON output matching `DecisionResponse`.
        3. Raise `LLMError` on transport or parsing failure (caller decides
           whether to escalate).
        """
        ...


def get_llm_client() -> LLMClient:
    """Factory — returns the backend configured in Django settings.

    Late import of django.conf so this module stays importable without Django
    (useful for tests / standalone tooling).
    """
    from django.conf import settings

    provider = settings.LLM["PROVIDER"]
    if provider == "ollama":
        from .ollama import OllamaClient
        return OllamaClient(
            base_url=settings.LLM["BASE_URL"],
            model=settings.LLM["MODEL"],
            timeout=settings.LLM["TIMEOUT"],
        )
    if provider == "vllm":
        from .vllm import VLLMClient
        return VLLMClient(
            base_url=settings.LLM["BASE_URL"],
            model=settings.LLM["MODEL"],
            api_key=settings.LLM["API_KEY"],
            timeout=settings.LLM["TIMEOUT"],
        )
    if provider == "noop":
        from .noop import NoOpClient
        return NoOpClient()
    raise LLMError(f"Unknown LLM provider: {provider}")
