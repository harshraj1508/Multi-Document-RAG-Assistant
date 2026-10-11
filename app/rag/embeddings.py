"""Turn text into embedding vectors using a free, local model.

We use sentence-transformers (`all-MiniLM-L6-v2`). The model is loaded lazily
and cached, so it is downloaded/loaded only once.

Tests can swap in a fake embedder by calling `set_embedder`, so they never need
to download the real model.
"""
from __future__ import annotations

from collections.abc import Sequence

from app.config import settings

_model = None  # cached real model
_embedder = None  # optional override (used in tests)


def set_embedder(fn) -> None:
    """Override the embedder with a callable `list[str] -> list[list[float]]`."""
    global _embedder
    _embedder = fn


def _load_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed(texts: Sequence[str]) -> list[list[float]]:
    if _embedder is not None:
        return _embedder(list(texts))
    model = _load_model()
    vectors = model.encode(list(texts), normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]
