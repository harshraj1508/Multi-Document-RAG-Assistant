"""Database engine and session management.

We use SQLAlchemy. The engine is created from DATABASE_URL. `get_db` is a
FastAPI dependency that hands out a session per request and always closes it.
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all ORM models."""


# SQLite needs check_same_thread=False so the threaded web server can share the
# connection. For Postgres we enable pool_pre_ping to recover dead connections.
if settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    engine = create_engine(settings.database_url, future=True, connect_args=_connect_args)
else:
    engine = create_engine(settings.database_url, future=True, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
