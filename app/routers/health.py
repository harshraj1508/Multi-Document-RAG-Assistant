"""Health and metrics endpoints for monitoring/observability."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ChatSession, Chunk, Document, User

router = APIRouter(tags=["monitoring"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """Liveness + readiness: confirms the DB is reachable."""
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> dict:
    """Simple counts so a dashboard can track usage."""
    return {
        "users": db.scalar(select(func.count(User.id))),
        "documents": db.scalar(select(func.count(Document.id))),
        "chunks": db.scalar(select(func.count(Chunk.id))),
        "chat_sessions": db.scalar(select(func.count(ChatSession.id))),
    }
