"""Unit test for user authentication schema migration upgrade and downgrade."""

from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_upgrade_and_downgrade(tmp_path: Path) -> None:
    """Alembic cleanly applies upgrade, downgrade, and re-upgrade on user schema."""
    db_path = tmp_path / "migration_test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    user_cols = {col["name"]: col for col in inspector.get_columns("user")}

    assert "username" in user_cols
    assert "is_active" in user_cols
    assert "failed_login_count" in user_cols
    assert "locked_until" in user_cols
    assert "last_login_at" in user_cols

    # Check unique index on username
    indexes = inspector.get_indexes("user")
    username_idx = [idx for idx in indexes if "username" in idx["column_names"]]
    assert len(username_idx) > 0
    assert bool(username_idx[0]["unique"]) is True

    # Check audit_log.user_id is nullable
    audit_cols = {col["name"]: col for col in inspector.get_columns("audit_log")}
    assert audit_cols["user_id"]["nullable"] is True

    # 2. Downgrade to initial schema (-1)
    engine.dispose()
    command.downgrade(alembic_cfg, "-1")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    downgraded_user_cols = {col["name"]: col for col in inspector.get_columns("user")}

    assert "username" not in downgraded_user_cols
    assert "failed_login_count" not in downgraded_user_cols
    assert "locked_until" not in downgraded_user_cols
    assert "name" in downgraded_user_cols

    # 3. Re-upgrade to head to verify idempotency
    engine.dispose()
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    re_upgraded_cols = {col["name"]: col for col in inspector.get_columns("user")}
    assert "username" in re_upgraded_cols
    engine.dispose()
