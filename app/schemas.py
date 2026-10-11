"""Pydantic schemas = request validation + response shaping.

FastAPI uses these to validate incoming JSON and to document the API.
"""
from pydantic import BaseModel, EmailStr, Field


# --- Auth ---
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    email: EmailStr


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Documents ---
class DocumentOut(BaseModel):
    id: int
    namespace: str
    filename: str
    chunk_count: int


# --- Chat ---
class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    namespace: str = "default"
    session_id: int | None = None  # continue an existing conversation


class Citation(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    snippet: str


class ChatResponse(BaseModel):
    session_id: int
    answer: str
    citations: list[Citation]


class MessageOut(BaseModel):
    role: str
    content: str


class SessionOut(BaseModel):
    session_id: int
    messages: list[MessageOut]
