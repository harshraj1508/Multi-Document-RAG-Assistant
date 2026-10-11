# Design Trade-off Analysis

This document explains the key decisions, why they were made, and what we gave
up. The brief required explaining design decisions, so each choice is justified
against the non-functional needs (scalability, security, resilience,
maintainability, performance).

---

## 1. PostgreSQL + pgvector vs. a dedicated vector database

**Decision:** store relational data *and* embeddings in one Postgres instance
using the `pgvector` extension.

**Why:**
- One datastore to run, back up, and reason about — ideal for an intern-scale
  project and a 2-hour build.
- Free and open source; no vendor lock-in.
- Transactions keep documents, chunks, and vectors consistent.

**Trade-off:** a specialist vector DB (Milvus, Qdrant) scales better past
millions of vectors and offers richer index tuning. For this scale, pgvector's
cosine-distance index is more than enough, and we can migrate later because the
retrieval logic is isolated in `app/rag/retrieval.py`.

---

## 2. Local embeddings (sentence-transformers) vs. a hosted embedding API

**Decision:** run `all-MiniLM-L6-v2` locally on CPU.

**Why:** free, private (no data leaves the machine), no rate limits, works
offline. It's small (~80 MB) and fast enough for a demo.

**Trade-off:** large hosted models produce higher-quality embeddings. We
accept slightly lower retrieval quality in exchange for zero cost and privacy.
The embedder is swappable via `set_embedder`, so upgrading is a one-line change.

---

## 3. Ollama with an extractive fallback vs. requiring a paid LLM

**Decision:** generate answers with a local Ollama model if present, otherwise
fall back to an extractive answerer (returns the most relevant sentences).

**Why:** the app must work with only free tools and even without internet. The
fallback guarantees a useful, cited answer in every environment, which also
makes tests deterministic and fast.

**Trade-off:** the fallback is simpler than a real LLM — it extracts rather than
truly composes. Point it at any Ollama model for full generative quality with no
code change.

---

## 4. Create-tables-on-startup vs. a migration tool (Alembic)

**Decision:** call `Base.metadata.create_all()` on startup.

**Why:** fewer moving parts for a small project; the schema is created
automatically on first run.

**Trade-off:** no versioned migrations, so schema changes in production would
need care. Alembic is the natural next step for a real deployment.

---

## 5. JWT in the Authorization header vs. server-side sessions

**Decision:** stateless JWTs signed with a server secret.

**Why:** stateless auth scales horizontally (any API replica can validate a
token) and is simple to use from the UI and `curl`.

**Trade-off:** tokens can't be revoked before expiry without extra machinery
(a denylist). We keep token lifetime short (60 min) to limit exposure.

---

## How the non-functional needs are met

| Need | How |
|---|---|
| **Scalability** | Stateless API (JWT) can run multiple replicas behind a load balancer; retrieval is index-backed in Postgres. |
| **Security** | bcrypt-hashed passwords, JWT auth on all data routes, namespace isolation, Pydantic validation on every input. |
| **Resilience / fault tolerance** | LLM failure degrades gracefully to the extractive fallback; `/health` reports DB connectivity; `pool_pre_ping` recovers dead DB connections. |
| **Observability / monitoring** | Structured JSON logs, per-request id + timing, `/health` and `/metrics` endpoints. |
| **Maintainability / auditability** | Clear package layout (`rag/`, `routers/`), typed models and schemas, tests, and this trade-off doc. Chat history provides an audit trail. |
| **Performance** | Chunk overlap tuned for recall; `TOP_K` limits context size; normalized embeddings make cosine distance cheap; vector index in Postgres. |
