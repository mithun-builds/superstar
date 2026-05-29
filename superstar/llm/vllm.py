"""vLLM backend — prod target. Talks to vLLM's OpenAI-compatible /v1/chat/completions.

Use this when you've stood up vLLM on a GPU box serving Qwen 2.5 32B AWQ
(or similar). Configure via LLM_PROVIDER=vllm and LLM_BASE_URL pointing at
the vLLM endpoint.

vLLM supports `guided_json` for grammar-constrained JSON output — meaningfully
more reliable than relying on format="json" hints. We use it when available.
"""
from __future__ import annotations

import json
from typing import Any

import httpx

from .base import DecisionResponse, LLMError, RetrievedChunk
from .ollama import _build_user_message, _parse_decision

# JSON schema enforced server-side by vLLM's guided decoding.
DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["approve", "reject", "escalate"]},
        "cited_rule_ids": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        "reason_text": {"type": "string"},
        "price_delta": {"type": "number"},
        "post_actions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["decision", "cited_rule_ids", "confidence", "reason_text"],
    "additionalProperties": False,
}


class VLLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str = "",
        timeout: int = 120,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def decide(
        self,
        *,
        request_payload: dict,
        retrieved_chunks: list[RetrievedChunk],
        system_prompt: str,
    ) -> DecisionResponse:
        user_msg = _build_user_message(request_payload, retrieved_chunks)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.0,
            "extra_body": {"guided_json": DECISION_SCHEMA},
        }
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions", json=body, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"vLLM transport error: {exc}") from exc

        try:
            raw = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMError(f"Unexpected vLLM response shape: {json.dumps(data)[:200]}") from exc

        return _parse_decision(raw)
