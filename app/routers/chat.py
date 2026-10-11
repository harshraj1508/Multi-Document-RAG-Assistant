"""Chat routes: ask a question (with citations), stream, and read history.

The flow is the RAG loop:
  retrieve relevant chunks -> build context -> generate answer -> save to memory
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ChatMessage, ChatSession, User
from app.rag import llm
from app.rag.retrieval import retrieve
from app.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    MessageOut,
    SessionOut,
)
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


def _get_or_create_session(
    db: Session, user: User, namespace: str, session_id: int | None
) -> ChatSession:
    if session_id is not None:
        session = db.scalar(
            select(ChatSession).where(
                ChatSession.id == session_id, ChatSession.user_id == user.id
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    session = ChatSession(user_id=user.id, namespace=namespace)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _history_text(session: ChatSession, limit: int = 6) -> str:
    """Last few messages, so the LLM has conversational memory."""
    recent = session.messages[-limit:]
    return "\n".join(f"{m.role}: {m.content}" for m in recent)


def _build_context(chunks) -> tuple[str, list[Citation]]:
    context_parts = []
    citations = []
    for chunk in chunks:
        context_parts.append(chunk.content)
        citations.append(
            Citation(
                document_id=chunk.document_id,
                filename=chunk.document.filename,
                chunk_index=chunk.chunk_index,
                snippet=chunk.content[:200],
            )
        )
    return "\n\n".join(context_parts), citations


@router.post("", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    session = _get_or_create_session(db, user, payload.namespace, payload.session_id)
    history = _history_text(session)

    chunks = retrieve(db, payload.question, payload.namespace)

    if not chunks:
        # Nothing in this namespace to ground an answer on. Don't call the LLM
        # and don't invent citations — return the explicit "no content" message.
        answer = llm.NO_CONTEXT_MESSAGE
        citations: list[Citation] = []
    else:
        context, citations = _build_context(chunks)
        answer = "".join(llm.generate_stream(payload.question, context, history))
        # If the model judged the context irrelevant and returned the explicit
        # no-content message, drop the citations so we don't show misleading
        # sources for an answer that isn't grounded in them.
        if answer.strip() == llm.NO_CONTEXT_MESSAGE:
            citations = []

    db.add(ChatMessage(session_id=session.id, role="user", content=payload.question))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=answer))
    db.commit()

    logger.info("Chat answered: session=%d, citations=%d", session.id, len(citations))
    return ChatResponse(session_id=session.id, answer=answer, citations=citations)


@router.post("/stream")
def chat_stream(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    session = _get_or_create_session(db, user, payload.namespace, payload.session_id)
    history = _history_text(session)
    chunks = retrieve(db, payload.question, payload.namespace)
    context, _ = _build_context(chunks)

    def event_stream():
        collected = []
        for token in llm.generate_stream(payload.question, context, history):
            collected.append(token)
            # Server-Sent Events format: "data: <text>\n\n"
            yield f"data: {token}\n\n"
        # Persist the full answer once streaming completes.
        answer = "".join(collected)
        db.add(ChatMessage(session_id=session.id, role="user", content=payload.question))
        db.add(ChatMessage(session_id=session.id, role="assistant", content=answer))
        db.commit()
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionOut:
    session = db.scalar(
        select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user.id
        )
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut(
        session_id=session.id,
        messages=[MessageOut(role=m.role, content=m.content) for m in session.messages],
    )
