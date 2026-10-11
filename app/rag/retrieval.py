"""Retrieve the most relevant chunks for a question.

On Postgres we use pgvector's cosine-distance operator for a fast index-backed
search. On other databases (SQLite in tests) we fall back to computing cosine
similarity in Python. Either way the result is the TOP_K closest chunks, scoped
to the user's namespace so documents never leak across namespaces.
"""
from __future__ import annotations

import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk
from app.rag.embeddings import embed_one


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def retrieve(db: Session, question: str, namespace: str, top_k: int | None = None) -> list[Chunk]:
    top_k = top_k or settings.top_k
    query_vec = embed_one(question)

    if db.bind.dialect.name == "postgresql":
        # Order by cosine distance using the pgvector operator (<=>).
        stmt = (
            select(Chunk)
            .where(Chunk.namespace == namespace)
            .order_by(Chunk.embedding.cosine_distance(query_vec))
            .limit(top_k)
        )
        return list(db.scalars(stmt))

    # Fallback: score every chunk in the namespace in Python.
    chunks = list(db.scalars(select(Chunk).where(Chunk.namespace == namespace)))
    scored = [
        (chunk, _cosine_similarity(query_vec, chunk.embedding or []))
        for chunk in chunks
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [chunk for chunk, _ in scored[:top_k]]
