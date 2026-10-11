"""Shared pytest fixtures.

Tests run against an in-memory SQLite database and use a fake embedder + LLM, so
they need no Postgres, no model download, and no Ollama. This makes the suite
fast and fully offline.

The fake embedder turns text into a small deterministic "bag of words" vector,
which is enough for cosine similarity to rank relevant chunks sensibly.
"""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.rag import embeddings, llm

VECTOR_SIZE = 16


def fake_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic hashing embedder: each word bumps a bucket."""
    vectors = []
    for text in texts:
        vec = [0.0] * VECTOR_SIZE
        for word in text.lower().split():
            h = int(hashlib.md5(word.encode()).hexdigest(), 16)
            vec[h % VECTOR_SIZE] += 1.0
        vectors.append(vec)
    return vectors


def fake_llm(question: str, context: str) -> str:
    # Echo the context back so tests can assert on retrieval behaviour.
    return f"Based on the documents: {context[:120]}"


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    embeddings.set_embedder(fake_embed)
    llm.set_llm(fake_llm)

    # Note: we intentionally do NOT use `with TestClient(app)` here, because the
    # `with` block fires the app's startup event, which tries to connect to the
    # real Postgres engine. The fixture already created the schema on the test
    # SQLite engine above, so we just use the client directly.
    c = TestClient(app)
    yield c

    app.dependency_overrides.clear()
    embeddings.set_embedder(None)
    llm.set_llm(None)


@pytest.fixture
def auth_client(client):
    """A client already registered + logged in, with the token applied."""
    client.post("/auth/register", json={"email": "a@b.com", "password": "secret1"})
    resp = client.post("/auth/login", data={"username": "a@b.com", "password": "secret1"})
    token = resp.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
