"""Integration test for Alembic migration upgrade and downgrade cycles."""

from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_upgrade_and_downgrade_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that Alembic migrations upgrade to head and downgrade to base cleanly."""
    temp_db_path = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{temp_db_path.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", db_url)

    # Initialize Alembic config pointing to the repository's alembic.ini
    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Run upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = {
        "user",
        "farmer",
        "consent",
        "plot",
        "season_observation",
        "assessment",
        "what_if",
        "alert",
        "action_log",
        "audit_log",
        "alembic_version",
    }
    assert expected_tables.issubset(set(tables)), (
        f"Missing tables after upgrade: {expected_tables - set(tables)}"
    )

    # 2. Run downgrade to base
    command.downgrade(alembic_cfg, "base")

    inspector = inspect(engine)
    remaining_tables = set(inspector.get_table_names()) - {"alembic_version"}
    assert len(remaining_tables) == 0, f"Tables still present after downgrade: {remaining_tables}"

    # 3. Re-run upgrade to head to ensure clean re-application
    command.upgrade(alembic_cfg, "head")
    inspector = inspect(engine)
    assert expected_tables.issubset(set(inspector.get_table_names()))
