"""Database engine and session management.

Supports SQLite for rapid PoC and local development, configured so switching
to PostgreSQL via DATABASE_URL requires zero codebase modifications.
"""

from collections.abc import Generator
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from satbhoomi.config.settings import get_settings


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create and configure a SQLAlchemy Engine.

    Enables WAL mode and foreign key constraints for SQLite to mirror PostgreSQL
    relational semantics.
    """
    settings = get_settings()
    url = database_url or settings.database_url

    engine_kwargs: dict[str, Any] = {
        "echo": settings.debug and settings.app_env == "development",
        "future": True,
    }

    if url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        engine = create_engine(url, **engine_kwargs)

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
            """Enable foreign key constraints and Write-Ahead Logging in SQLite."""
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.close()

        return engine

    # PostgreSQL / production RDBMS connection configuration
    engine_kwargs["pool_pre_ping"] = True
    return create_engine(url, **engine_kwargs)


# Module-level default engine and sessionmaker
engine = create_db_engine()
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session and guarantees closure upon exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
