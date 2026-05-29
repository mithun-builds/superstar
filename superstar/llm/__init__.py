"""LLM client abstraction.

The rest of SuperStar depends on `LLMClient` — never on a specific backend.
Swapping Ollama for vLLM (or vice versa) is a settings change, not a code
change. New backends register themselves via `get_llm_client()`.
"""
from .base import DecisionResponse, LLMClient, LLMError, get_llm_client

__all__ = ["LLMClient", "DecisionResponse", "LLMError", "get_llm_client"]
