# Enterprise Multi-Document RAG Assistant

A simple, production-shaped **Retrieval-Augmented Generation (RAG)** platform.
Upload documents, organize them into **namespaces**, and ask questions. The
system retrieves the most relevant chunks and generates an answer **with
citations**, keeps **conversational memory** per chat session, and supports
**streaming** responses.

> Built with **free / open-source, production-grade tools**. The datastore is
> **PostgreSQL + pgvector**, and the whole stack (API + database + UI) comes up
> with a single `docker compose up`.

---

## Table of Contents
- [Features](#features)
- [Tech Stack (all free)](#tech-stack-all-free)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [API Documentation](#api-documentation)
- [How RAG Works Here](#how-rag-works-here)
- [Testing](#testing)
- [Diagrams](#diagrams)
- [Design Trade-offs](#design-trade-offs)
- [Project Structure](#project-structure)

---

## Features

| Requirement | How it's implemented |
|---|---|
| Authentication | JWT (register / login), bcrypt password hashing |
| Namespaces | Every document & query is scoped to a `namespace` |
| Citations | Answers include the source chunks + document names |
| Streaming responses | `POST /chat/stream` streams tokens via SSE |
| Conversational memory | Chat sessions + messages stored in PostgreSQL |
| Document lifecycle | Upload / list / delete documents and their chunks |
| Validation | Pydantic schemas on every request |
| Persistence | PostgreSQL + `pgvector` for embeddings |
| Logging | Structured JSON logging + request-id middleware |
| Monitoring | `/health` and `/metrics` endpoints |
| Deployment | Dockerfile + docker-compose (API + DB + UI) |
| Documentation | This README + OpenAPI docs at `/docs` |

---

## Tech Stack (all free / open source)

- **Python 3.11** + **FastAPI** — API framework
- **PostgreSQL 16 + pgvector** — relational store **and** vector search in one
- **sentence-transformers (`all-MiniLM-L6-v2`)** — local embeddings (CPU, free)
- **Groq** (OpenAI-compatible API) — LLM for generation. Falls back to a local
  **Ollama** server if present, then to a free **extractive answerer**, so the
  app always produces a cited answer even if the LLM is unreachable.
- **Streamlit** — web UI
- **python-jose (JWT) + bcrypt** — authentication
- **pytest** — testing
- **Docker Compose** — orchestration

---

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for all diagrams
(high-level architecture, deployment, component, ER, and sequence diagrams).

```
User ──► Streamlit UI ──► FastAPI ──► PostgreSQL (+pgvector)
                               │
                               ├─► Embedding model (sentence-transformers)
                               └─► LLM (Ollama) or extractive fallback
```

---

## Quick Start

### Option A — Docker (recommended, one command)

```bash
docker compose up --build
```

- API:  http://localhost:8000  (Swagger docs at http://localhost:8000/docs)
- UI:   http://localhost:8501

### Option B — Run the services locally (bring your own Postgres)

```bash
# 1. Start PostgreSQL with the pgvector extension
docker run -d --name rag-db -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=ragdb \
  pgvector/pgvector:pg16

# 2. Install deps (first run downloads a ~80MB embedding model)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Point the app at your database and (optionally) set the LLM key
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ragdb
export GROQ_API_KEY=your_key_here     # Windows: $env:GROQ_API_KEY="your_key_here"

# 4. Run the API
uvicorn app.main:app --reload

# 5. Run the UI (separate terminal)
streamlit run ui/streamlit_app.py
```

See [`SETUP.md`](SETUP.md) for a full new-machine guide.

### First steps
1. Open the UI at http://localhost:8501
2. Register a user, then log in.
3. Upload a `.txt` / `.md` document into a namespace (e.g. `space`).
4. Ask a question — you'll get an answer with citations.

---

## Configuration

All config is via environment variables (see [`app/config.py`](app/config.py)).

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@db:5432/ragdb` | PostgreSQL connection string (Docker sets this automatically). |
| `JWT_SECRET` | `change-me-in-prod` | JWT signing secret |
| `JWT_EXPIRE_MINUTES` | `60` | Token lifetime |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | sentence-transformers model |
| `GROQ_API_KEY` | *(empty)* | Groq key. Set it to enable the Groq LLM; blank uses the fallback. |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq model name |
| `OLLAMA_URL` | `http://localhost:11434` | Fallback local LLM (used only if no Groq key) |
| `OLLAMA_MODEL` | `llama3.2` | Model name if Ollama is running |
| `CHUNK_SIZE` | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | `50` | Overlap between chunks |
| `TOP_K` | `4` | Chunks retrieved per query |

---

## API Documentation

Interactive docs are auto-generated at **`/docs`** (Swagger) and **`/redoc`**.
Full endpoint reference: [`docs/api.md`](docs/api.md).

Key endpoints:

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Create a user |
| `POST` | `/auth/login` | Get a JWT token |
| `POST` | `/documents` | Upload a document (multipart) |
| `GET`  | `/documents` | List documents in a namespace |
| `DELETE` | `/documents/{id}` | Delete a document + its chunks |
| `POST` | `/chat` | Ask a question (returns answer + citations) |
| `POST` | `/chat/stream` | Streaming answer (SSE) |
| `GET`  | `/chat/sessions/{id}` | Get conversation history |
| `GET`  | `/health` | Liveness/readiness |
| `GET`  | `/metrics` | Basic app metrics |

---

## How RAG Works Here

1. **Ingest** — on upload, the document text is split into overlapping chunks.
2. **Embed** — each chunk is turned into a vector with sentence-transformers.
3. **Store** — chunks + vectors go into Postgres (`pgvector` column).
4. **Retrieve** — a question is embedded and compared (cosine distance) to find
   the `TOP_K` most similar chunks within the user's namespace.
5. **Generate** — retrieved chunks become context for the LLM (Groq). The model
   is instructed to answer **only** from that context; if nothing relevant is
   found, it returns an explicit "no content" message instead of guessing. If
   the LLM is unreachable, a free extractive answerer is used. Either way,
   **citations** to the source chunks are returned.
6. **Remember** — the question and answer are saved to the chat session, and
   recent history is fed back into the next prompt (conversational memory).

---

## Testing

```bash
pytest -v
```

Tests run against an isolated in-memory database with a fake embedder/LLM, so
they are fast and need **no external services**. They cover auth, chunking,
retrieval ranking, and the full chat flow.

---

## Diagrams

All diagrams live in [`docs/architecture.md`](docs/architecture.md) as Mermaid
(renders on GitHub):
- High-Level Architecture
- Deployment Diagram
- Component Diagram
- Database ER Diagram
- Sequence Diagrams (upload, query)

---

## Design Trade-offs

See [`docs/tradeoffs.md`](docs/tradeoffs.md) for the full write-up. Short version:

- **Postgres + pgvector instead of a dedicated vector DB** — one datastore for
  both relational data and vectors; free and operationally simple. Trade-off: a
  specialized vector DB would scale better at millions of vectors.
- **Local embeddings instead of a paid embedding API** — free and private, no
  rate limits. Trade-off: slightly lower quality than large hosted models.
- **Groq LLM with Ollama + extractive fallback** — fast hosted generation with
  graceful degradation if the LLM is unreachable. Trade-off: Groq needs network
  + a key; the final fallback answer is simpler than a real LLM's.

---

## Project Structure

```
project-sp/
├── app/                 # FastAPI backend
│   ├── main.py          # app entrypoint + middleware
│   ├── config.py        # settings
│   ├── db.py            # SQLAlchemy engine/session
│   ├── models.py        # ORM models (users, docs, chunks, chats)
│   ├── schemas.py       # Pydantic request/response models
│   ├── security.py      # JWT + password hashing
│   ├── logging_conf.py  # structured logging
│   ├── rag/             # embeddings, chunking, retrieval, LLM
│   └── routers/         # auth, documents, chat, health
├── ui/                  # Streamlit UI
├── tests/               # pytest suite
├── docs/                # diagrams (architecture.md), api.md, tradeoffs.md
├── demo_docs/           # sample documents (space/, cooking/)
├── demo.html            # visual flow of how the system works
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
└── SETUP.md             # new-machine setup guide
```
