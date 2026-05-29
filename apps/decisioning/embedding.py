"""BGE-M3 embedding wrapper. Lazy-loads the model on first use.

Runs on CPU by default — fine for small KBs (~hundreds of rules). For larger
KBs, set EMBEDDING_DEVICE=cuda in env.
"""
from __future__ import annotations

import threading

from django.conf import settings

_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(
                    settings.EMBEDDINGS["MODEL"],
                    device=settings.EMBEDDINGS["DEVICE"],
                )
    return _model


def embed(text: str) -> list[float]:
    """Embed a single string. Returns a Python list (pgvector accepts list/ndarray)."""
    model = _get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return [v.tolist() for v in model.encode(texts, normalize_embeddings=True, batch_size=32)]
