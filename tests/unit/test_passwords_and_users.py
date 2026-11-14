"""Unit tests for Argon2id password hashing, user management, and security guards."""

import os
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from satbhoomi.api.auth.passwords import (
    dummy_hash,
    get_hasher,
    hash_password,
    needs_rehash,
    verify_password,
)
from satbhoomi.config.settings import get_settings
from satbhoomi.db.base import Base
from satbhoomi.db.models.user import User
from scripts.create_user import create_user
from scripts.seed_synthetic import seed_synthetic_data


@pytest.fixture(autouse=True)
def clean_env_settings():
    """Ensure cached settings are cleared before and after each test."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_db_session() -> Session:
    """Provide an isolated in-memory SQLite database session with Base tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


def test_hash_then_verify_works() -> None:
    """Argon2id hashes a password and successfully verifies the cleartext."""
    plain = "V3rySecureP@ssw0rd!"
    pwd_hash = hash_password(plain)

    assert pwd_hash.startswith("$argon2id$")
    assert verify_password(plain, pwd_hash) is True


def test_wrong_password_fails() -> None:
    """Argon2id rejects mismatched, empty, or corrupted password hashes."""
    pwd_hash = hash_password("CorrectHorseBatteryStaple123!")

    assert verify_password("WrongPassword123!", pwd_hash) is False
    assert verify_password("", pwd_hash) is False
    assert verify_password("CorrectHorseBatteryStaple123!", "not_a_valid_argon2_hash") is False


def test_two_hashes_of_same_password_differ() -> None:
    """Argon2id generates unique cryptographic salts for each hashing invocation."""
    plain = "IdenticalCleartextPassword123!"
    h1 = hash_password(plain)
    h2 = hash_password(plain)

    assert h1 != h2
    assert verify_password(plain, h1) is True
    assert verify_password(plain, h2) is True


def test_needs_rehash_behaves() -> None:
    """needs_rehash accurately flags outdated or corrupted hashes."""
    pwd_hash = hash_password("StandardPassword123!")
    assert needs_rehash(pwd_hash) is False
    assert needs_rehash("corrupted_hash") is True


def test_production_mode_settings_reject_low_cost() -> None:
    """Lower-cost test parameters are strictly forbidden outside ENVIRONMENT=test."""
    try:
        # 1. Reject when ENVIRONMENT=production
        with patch.dict(
            os.environ, {"ENVIRONMENT": "production", "ARGON2_LOW_COST_FOR_TEST": "true"}
        ):
            get_settings.cache_clear()
            cfg_prod = get_settings()
            with pytest.raises(RuntimeError, match="forbidden outside ENVIRONMENT=test"):
                get_hasher(cfg_prod)

        # 2. Reject when ENVIRONMENT=development
        with patch.dict(
            os.environ, {"ENVIRONMENT": "development", "ARGON2_LOW_COST_FOR_TEST": "true"}
        ):
            get_settings.cache_clear()
            cfg_dev = get_settings()
            with pytest.raises(RuntimeError, match="forbidden outside ENVIRONMENT=test"):
                get_hasher(cfg_dev)
    finally:
        get_settings.cache_clear()


def test_dummy_hash_timing_mitigation() -> None:
    """dummy_hash generates a verifiable Argon2id hash for constant-time rejection."""
    dh = dummy_hash()
    assert dh.startswith("$argon2id$")
    assert verify_password("nonexistent_user_attempt", dh) is False


def test_create_user_script_creates_user(test_db_session: Session) -> None:
    """create_user script creates user with hashed password and default security attributes."""
    prompter = lambda prompt: "ValidPassword123!"  # noqa: E731

    exit_code = create_user(
        username="anand_officer",
        name="Loan Officer Anand",
        role="officer",
        session=test_db_session,
        prompt_fn=prompter,
    )

    assert exit_code == 0
    created = test_db_session.execute(
        select(User).where(User.username == "anand_officer")
    ).scalar_one_or_none()

    assert created is not None
    assert created.name == "Loan Officer Anand"
    assert created.role == "officer"
    assert created.is_active is True
    assert created.failed_login_count == 0
    assert created.locked_until is None
    assert verify_password("ValidPassword123!", created.password_hash) is True


def test_create_user_refuses_short_password(test_db_session: Session) -> None:
    """create_user refuses passwords shorter than 12 characters."""
    short_prompter = lambda prompt: "short_pwd"  # noqa: E731

    exit_code = create_user(
        username="short_pwd_user",
        name="Short Password User",
        role="officer",
        session=test_db_session,
        prompt_fn=short_prompter,
    )

    assert exit_code == 1
    existing = test_db_session.execute(
        select(User).where(User.username == "short_pwd_user")
    ).scalar_one_or_none()
    assert existing is None


def test_create_user_refuses_duplicate_username(test_db_session: Session) -> None:
    """create_user refuses to register an already existing username."""
    prompter = lambda prompt: "ValidPassword123!"  # noqa: E731

    code1 = create_user(
        username="unique_admin",
        name="Admin One",
        role="admin",
        session=test_db_session,
        prompt_fn=prompter,
    )
    assert code1 == 0

    code2 = create_user(
        username="unique_admin",
        name="Admin Two",
        role="admin",
        session=test_db_session,
        prompt_fn=prompter,
    )
    assert code2 == 1


def test_seed_synthetic_creates_no_user_outside_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """seed_synthetic.py strictly refuses to seed default users outside ENVIRONMENT=test."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with patch("satbhoomi.db.session.SessionLocal", lambda: Session(engine)):
        users_added, farmers_added, plots_added, obs_added = seed_synthetic_data()

    assert users_added == 0
    session = Session(engine)
    user_count = len(session.execute(select(User)).scalars().all())
    assert user_count == 0
    session.close()
    get_settings.cache_clear()
