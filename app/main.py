"""FastAPI application entrypoint.

Wires up logging, middleware (request id + timing), the database schema, and all
routers. For an intern-sized project we create tables on startup instead of
running a separate migration tool.
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.db import Base, engine
from app.logging_conf import setup_logging
from app.routers import auth, chat, documents, health

setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """On startup: enable pgvector (Postgres only) and create all tables."""
    if engine.dialect.name == "postgresql":
        from sqlalchemy import text

        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)

    # Warm up the embedding model now, so the first upload/chat doesn't pay the
    # one-time ~10s model-load cost and feel slow.
    try:
        from app.rag.embeddings import embed_one

        embed_one("warmup")
        logger.info("Embedding model warmed up.")
    except Exception as exc:
        logger.warning("Embedding warm-up skipped: %s", exc)

    logger.info("Startup complete; tables ready.")
    yield


app = FastAPI(
    title="Enterprise Multi-Document RAG Assistant",
    description="Upload documents, ask questions, get answers with citations.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS so the Streamlit UI (different port) can call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    """Attach a request id and log timing for every request (observability)."""
    request_id = str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "%s %s -> %s (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        extra={"request_id": request_id},
    )
    return response


app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(health.router)


@app.get("/", tags=["monitoring"])
def root() -> dict:
    return {"service": "rag-assistant", "docs": "/docs"}
