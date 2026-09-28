"""SQLAlchemy engine and session management.

SQLite is the default; PostgreSQL is used when ``DATABASE_URL`` is set.
A single model set serves both databases — there is no per-database ORM code.

SQLite specifics handled here:
- the database file's parent directory is created on demand,
- ``check_same_thread=False`` for the in-process job runner,
- ``PRAGMA foreign_keys=ON`` so foreign-key constraints are actually enforced.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .config import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    """Build a SQLAlchemy engine for SQLite (default) or PostgreSQL."""
    url = database_url or get_settings().sqlalchemy_url
    if url.startswith("sqlite"):
        path = url.split("sqlite:///", 1)[-1]
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enforce_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    else:
        engine = create_engine(url)
    return engine


_engine: Engine | None = None


def get_engine() -> Engine:
    """Lazily-created process-wide engine."""
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker:
    """Session factory bound to the given (or default) engine."""
    return sessionmaker(bind=engine or get_engine(), autoflush=False, expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Clean session lifecycle: commit on success, rollback on error, always close."""
    session = get_session_factory(engine)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(engine: Engine | None = None) -> None:
    """Create all tables: research_jobs, companies, lead_results, rejected_records."""
    from . import models  # noqa: F401  (import registers the models)

    eng = engine or get_engine()
    models.Base.metadata.create_all(eng)
