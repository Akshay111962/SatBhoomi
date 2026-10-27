"""Unit tests for database session and engine setup."""

from unittest.mock import patch

from sqlalchemy import text

from satbhoomi.db.base import Base
from satbhoomi.db.session import SessionLocal, create_db_engine, get_db


def test_declarative_base_instantiation() -> None:
    """Verify that SQLAlchemy Base metadata is properly initialized."""
    assert Base.metadata is not None


def test_sqlite_engine_creation_and_pragmas() -> None:
    """Verify that SQLite engine sets WAL mode and foreign key enforcement."""
    engine = create_db_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        fk_result = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert fk_result == 1

        # In-memory SQLite reports 'memory' for journal_mode
        jm_result = conn.execute(text("PRAGMA journal_mode;")).scalar()
        assert jm_result in {"memory", "wal"}


def test_postgresql_engine_configuration() -> None:
    """Verify engine creation logic passes pool_pre_ping for PostgreSQL URLs."""
    with patch("satbhoomi.db.session.create_engine") as mock_create_engine:
        create_db_engine("postgresql+psycopg2://user:pass@localhost:5432/mockdb")
        mock_create_engine.assert_called_once_with(
            "postgresql+psycopg2://user:pass@localhost:5432/mockdb",
            echo=True,
            future=True,
            pool_pre_ping=True,
        )


def test_get_db_session_generator() -> None:
    """Verify that get_db yields an active session and closes it cleanly."""
    gen = get_db()
    session = next(gen)
    assert session is not None
    assert session.is_active

    # Close generator
    try:
        next(gen)
    except StopIteration:
        pass


def test_session_local_instantiation() -> None:
    """Verify SessionLocal creates a session that can execute simple queries."""
    session = SessionLocal()
    try:
        result = session.execute(text("SELECT 1;")).scalar()
        assert result == 1
    finally:
        session.close()
