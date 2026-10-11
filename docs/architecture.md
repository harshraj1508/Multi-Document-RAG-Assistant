# Architecture & Diagrams

All diagrams are written in [Mermaid](https://mermaid.js.org/) so they render
directly on GitHub and in most Markdown viewers.

> **Datastore:** the system uses **PostgreSQL** with the **pgvector** extension
> as a single store for relational data and vector embeddings. Vector search is
> index-backed using pgvector's cosine-distance operator, scoped per namespace.
> The full stack is brought up with `docker compose up`.

---

## 1. High-Level Architecture

```mermaid
flowchart LR
    User([User])
    UI[Streamlit UI]
    API[FastAPI Service]
    EMB[Embedding Model<br/>sentence-transformers · local]
    LLM[LLM: Groq<br/>→ Ollama → extractive fallback]
    DB[(PostgreSQL + pgvector)]

    User --> UI
    UI -->|REST / JWT| API
    API --> EMB
    API --> LLM
    API --> DB
```

The API is the single brain: it authenticates users, embeds text, runs
namespace-scoped vector search, and calls the LLM to compose cited answers. The
LLM layer tries **Groq** first, then a local **Ollama**, then a built-in
**extractive** answerer — so it degrades gracefully and always responds.

---

## 2. Deployment Diagram

```mermaid
flowchart TB
    subgraph Host["Docker Host (one machine)"]
        subgraph net["docker-compose network"]
            C1[api container<br/>uvicorn:8000]
            C2[ui container<br/>streamlit:8501]
            C3[(db container<br/>postgres+pgvector:5432)]
        end
    end
    GROQ[Groq LLM API<br/>hosted · HTTPS]
    OLL[Ollama on host<br/>:11434 · optional fallback]

    C2 --> C1
    C1 --> C3
    C1 -->|primary| GROQ
    C1 -.fallback.-> OLL
```

One `docker compose up` starts three containers (API, UI, PostgreSQL+pgvector)
on a private network. The API calls the hosted **Groq** LLM over HTTPS; if Groq
is unavailable it tries a local **Ollama**, then its built-in extractive
answerer, so generation never hard-fails.

---

## 3. Component Diagram

```mermaid
flowchart TB
    subgraph app["FastAPI app"]
        MW[Middleware<br/>request-id + timing + CORS]
        R1[auth router]
        R2[documents router]
        R3[chat router]
        R4[health router]
        SEC[security<br/>JWT + bcrypt]
        subgraph rag["rag package"]
            CH[chunking]
            EM[embeddings]
            RE[retrieval]
            GE[llm generation]
        end
        ORM[models + db<br/>SQLAlchemy]
    end

    MW --> R1 & R2 & R3 & R4
    R1 --> SEC
    R2 --> CH --> EM
    R2 --> ORM
    R3 --> RE --> EM
    R3 --> GE
    R3 --> ORM
    R4 --> ORM
```

---

## 4. Database ER Diagram

```mermaid
erDiagram
    USERS ||--o{ DOCUMENTS : owns
    USERS ||--o{ CHAT_SESSIONS : has
    DOCUMENTS ||--o{ CHUNKS : "split into"
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : contains

    USERS {
        int id PK
        string email UK
        string hashed_password
        datetime created_at
    }
    DOCUMENTS {
        int id PK
        int user_id FK
        string namespace
        string filename
        datetime created_at
    }
    CHUNKS {
        int id PK
        int document_id FK
        string namespace
        int chunk_index
        text content
        vector embedding
    }
    CHAT_SESSIONS {
        int id PK
        int user_id FK
        string namespace
        datetime created_at
    }
    CHAT_MESSAGES {
        int id PK
        int session_id FK
        string role
        text content
        datetime created_at
    }
```

---

## 5. Sequence Diagram — Document Upload (Ingestion)

```mermaid
sequenceDiagram
    actor U as User
    participant UI as Streamlit
    participant API as FastAPI
    participant E as Embedder
    participant DB as Postgres

    U->>UI: choose file + namespace
    UI->>API: POST /documents (JWT, file)
    API->>API: validate token + decode text
    API->>API: chunk_text()
    API->>E: embed(chunks)
    E-->>API: vectors
    API->>DB: insert document + chunks(+vectors)
    DB-->>API: ok
    API-->>UI: {id, chunk_count}
```

---

## 6. Sequence Diagram — Ask a Question (Query/RAG)

```mermaid
sequenceDiagram
    actor U as User
    participant UI as Streamlit
    participant API as FastAPI
    participant E as Embedder
    participant DB as Postgres
    participant L as LLM (Groq)

    U->>UI: type question
    UI->>API: POST /chat (JWT, question, namespace)
    API->>DB: get/create chat session + recent history
    API->>E: embed(question)
    E-->>API: query vector
    API->>DB: vector search (top_k, scoped to namespace)
    DB-->>API: relevant chunks
    alt no chunks in namespace
        API-->>UI: "no relevant content" (no citations)
    else chunks found
        API->>L: generate(question, context, history)
        L-->>API: answer (grounded in context)
        API->>DB: save user + assistant messages (memory)
        API-->>UI: {answer, citations, session_id}
    end
    UI-->>U: show answer + citations
```
