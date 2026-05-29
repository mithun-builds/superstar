"""Ollama backend — dev default. Talks to a local Ollama daemon.

Notes:
- Uses Ollama's /api/chat with format=json for structured output. Qwen 2.5
  follows JSON format well; we additionally validate via dataclass parsing.
- Ollama is single-threaded and not designed for prod multi-user throughput.
  For prod, switch LLM_PROVIDER=vllm. The two backends are wire-compatible at
  the LLMClient level.
"""
from __future__ import annotations

import json

import httpx

from .base import DecisionResponse, LLMError, RetrievedChunk


class OllamaClient:
    def __init__(self, *, base_url: str, model: str, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def decide(
        self,
        *,
        request_payload: dict,
        retrieved_chunks: list[RetrievedChunk],
        system_prompt: str,
    ) -> DecisionResponse:
        user_msg = _build_user_message(request_payload, retrieved_chunks)
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.0},
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(f"{self.base_url}/api/chat", json=body)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama transport error: {exc}") from exc

        raw = data.get("message", {}).get("content", "")
        return _parse_decision(raw)


def _build_user_message(payload: dict, chunks: list[RetrievedChunk]) -> str:
    chunks_block = "\n\n".join(
        f"[{c.rule_id}] (score={c.score:.3f}, source={c.source_path})\n{c.text}"
        for c in chunks
    )
    return (
        "REQUEST PAYLOAD:\n"
        f"{json.dumps(payload, indent=2, default=str)}\n\n"
        "RETRIEVED RULE CHUNKS:\n"
        f"{chunks_block}\n\n"
        "Respond with a JSON object matching the schema in the system prompt."
    )


def _parse_decision(raw: str) -> DecisionResponse:
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMError(f"Model returned non-JSON output: {raw[:200]!r}") from exc

    decision = obj.get("decision")
    if decision not in ("approve", "reject", "escalate"):
        raise LLMError(f"Invalid decision value: {decision!r}")

    return DecisionResponse(
        decision=decision,
        cited_rule_ids=tuple(obj.get("cited_rule_ids", [])),
        confidence=float(obj.get("confidence", 0.0)),
        reason_text=str(obj.get("reason_text", "")),
        price_delta=float(obj.get("price_delta", 0.0)),
        post_actions=tuple(obj.get("post_actions", [])),
        raw_model_output=raw,
    )
