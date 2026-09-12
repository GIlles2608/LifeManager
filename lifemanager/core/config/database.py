"""
SQLAlchemy engine and session management.

Usage:
    from lifemanager.core.config.database import get_session

    with get_session() as session:
        session.add(obj)
        session.commit()
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from lifemanager.core.config.settings import settings

# ── Engine ────────────────────────────────────────────────────────────────────
_engine = create_engine(
    settings.db.url,
    echo=settings.app.is_dev,       # SQL logging in dev mode
    pool_pre_ping=True,             # verify connection health before use
    pool_size=5,
    max_overflow=10,
)

# ── Session factory ───────────────────────────────────────────────────────────
_SessionLocal = sessionmaker(
    bind=_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,         # avoid lazy-load issues after commit
)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session: Session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_engine():
    """Expose engine for Alembic migrations."""
    return _engine
