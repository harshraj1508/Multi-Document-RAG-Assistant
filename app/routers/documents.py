"""Document lifecycle: upload, list, delete.

On upload we read the file text, chunk it, embed each chunk, and store
everything scoped to the user + namespace.
"""
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Chunk, Document, User
from app.rag.chunking import chunk_text
from app.rag.embeddings import embed
from app.schemas import DocumentOut
from app.security import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    namespace: str = Form("default"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DocumentOut:
    raw = await file.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 text")

    chunks = chunk_text(text, settings.chunk_size, settings.chunk_overlap)
    if not chunks:
        raise HTTPException(status_code=400, detail="Document is empty")

    doc = Document(user_id=user.id, namespace=namespace, filename=file.filename)
    db.add(doc)
    db.flush()  # get doc.id before adding chunks

    vectors = embed(chunks)
    for i, (content, vector) in enumerate(zip(chunks, vectors)):
        db.add(
            Chunk(
                document_id=doc.id,
                namespace=namespace,
                chunk_index=i,
                content=content,
                embedding=vector,
            )
        )
    db.commit()
    db.refresh(doc)
    logger.info("Document uploaded: %s (%d chunks)", doc.filename, len(chunks))
    return DocumentOut(
        id=doc.id, namespace=doc.namespace, filename=doc.filename, chunk_count=len(chunks)
    )


@router.get("", response_model=list[DocumentOut])
def list_documents(
    namespace: str = "default",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DocumentOut]:
    docs = db.scalars(
        select(Document)
        .where(Document.user_id == user.id, Document.namespace == namespace)
        .order_by(Document.id)
    ).all()

    result = []
    for doc in docs:
        count = db.scalar(
            select(func.count(Chunk.id)).where(Chunk.document_id == doc.id)
        )
        result.append(
            DocumentOut(
                id=doc.id, namespace=doc.namespace, filename=doc.filename, chunk_count=count
            )
        )
    return result


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> None:
    doc = db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == user.id)
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    db.delete(doc)  # cascades to chunks
    db.commit()
    logger.info("Document deleted: id=%d", document_id)
