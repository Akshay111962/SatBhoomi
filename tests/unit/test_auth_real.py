"""Unit tests for real authentication, token verification, and role enforcement."""

import logging
import os
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from satbhoomi.api.auth.clock import set_test_clock
from satbhoomi.api.auth.passwords import hash_password
from satbhoomi.api.auth.rate_limit import login_rate_limiter
from satbhoomi.api.auth.tokens import create_access_token, decode_access_token
from satbhoomi.api.main import app
from satbhoomi.api.mock_data import FAKE_MOCK_TOKEN
from satbhoomi.api.routes.deps import get_current_user, require_admin, require_officer
from satbhoomi.api.schemas.auth import TokenResponse
from satbhoomi.config.settings import Settings, get_settings, reset_ephemeral_jwt_secret
from satbhoomi.db.base import Base
from satbhoomi.db.models.audit_log import AuditLog
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db


@pytest.fixture(autouse=True)
def auth_test_setup():
    """Reset clock, rate limiter, and settings cache for clean test isolation."""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["ARGON2_LOW_COST_FOR_TEST"] = "true"
    os.environ["MOCK_API"] = "false"
    os.environ["JWT_SECRET_KEY"] = "test-jwt-secret-key-that-is-at-least-32-chars-long"
    set_test_clock(None)
    login_rate_limiter.reset()
    get_settings.cache_clear()
    yield
    set_test_clock(None)
    login_rate_limiter.reset()
    get_settings.cache_clear()


@pytest.fixture
def auth_db_session() -> Session:
    """Create an isolated in-memory SQLite database session."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_client(auth_db_session: Session) -> TestClient:
    """Provide a FastAPI TestClient with DB dependency overridden."""
    app.dependency_overrides[get_db] = lambda: auth_db_session
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def create_user_record(
    db: Session,
    username: str = "officer_test",
    password: str = "ValidPassword123!",
    role: str = "officer",
    is_active: bool = True,
    failed_login_count: int = 0,
    locked_until: datetime | None = None,
) -> User:
    """Helper to insert a test user into the database."""
    user = User(
        username=username,
        name=f"Test {username}",
        role=role,
        password_hash=hash_password(password),
        is_active=is_active,
        failed_login_count=failed_login_count,
        locked_until=locked_until,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ==============================================================================
# TC-001: Lockout Cycle, Byte-for-Byte 401 Parity, and Lock Expiration
# ==============================================================================


def test_tc001_lockout_cycle_and_byte_parity(test_client: TestClient, auth_db_session: Session):
    """TC-001: 5 failures lock account; 401 bodies are byte-identical; lock does not re-extend."""
    t0 = datetime(2026, 11, 15, 10, 0, 0, tzinfo=UTC)
    set_test_clock(t0)

    # Setup active user and inactive user
    create_user_record(auth_db_session, username="farmer_officer", password="CorrectPassword123!")
    create_user_record(
        auth_db_session,
        username="inactive_officer",
        password="CorrectPassword123!",
        is_active=False,
    )

    # 1. First wrong password
    res_wrong = test_client.post(
        "/api/v1/auth/login",
        json={"username": "farmer_officer", "password": "WrongPassword1"},
    )
    assert res_wrong.status_code == 401

    # 2. Unknown user
    res_unknown = test_client.post(
        "/api/v1/auth/login",
        json={"username": "ghost_user", "password": "AnyPassword123"},
    )
    assert res_unknown.status_code == 401

    # 3. Inactive user
    res_inactive = test_client.post(
        "/api/v1/auth/login",
        json={"username": "inactive_officer", "password": "CorrectPassword123!"},
    )
    assert res_inactive.status_code == 401

    # Accumulate 5 wrong attempts on farmer_officer (already had 1)
    for i in range(2, 6):
        res = test_client.post(
            "/api/v1/auth/login",
            json={"username": "farmer_officer", "password": f"WrongPassword{i}"},
        )
        assert res.status_code == 401

    # User must now be locked until t0 + 15 min
    user = auth_db_session.query(User).filter(User.username == "farmer_officer").first()
    assert user.failed_login_count == 5
    locked_until_utc = (
        user.locked_until.replace(tzinfo=UTC)
        if user.locked_until.tzinfo is None
        else user.locked_until
    )
    assert locked_until_utc == t0 + timedelta(minutes=15)

    # 4. Attempt while locked (both with wrong password and correct password)
    res_locked_wrong = test_client.post(
        "/api/v1/auth/login",
        json={"username": "farmer_officer", "password": "WrongPassword6"},
    )
    assert res_locked_wrong.status_code == 401

    res_locked_correct = test_client.post(
        "/api/v1/auth/login",
        json={"username": "farmer_officer", "password": "CorrectPassword123!"},
    )
    assert res_locked_correct.status_code == 401

    # Invariant: Lock must NOT extend and count must NOT increment during lockout
    auth_db_session.refresh(user)
    assert user.failed_login_count == 5
    locked_until_utc = (
        user.locked_until.replace(tzinfo=UTC)
        if user.locked_until.tzinfo is None
        else user.locked_until
    )
    assert locked_until_utc == t0 + timedelta(minutes=15)

    # Invariant: Byte-for-byte identical 401 responses across all failure modes
    assert res_wrong.content == res_unknown.content
    assert res_unknown.content == res_inactive.content
    assert res_inactive.content == res_locked_wrong.content
    assert res_locked_wrong.content == res_locked_correct.content

    # 5. Advance clock past 15 minutes: login succeeds and resets counter
    t_after_lock = t0 + timedelta(minutes=16)
    set_test_clock(t_after_lock)

    res_success = test_client.post(
        "/api/v1/auth/login",
        json={"username": "farmer_officer", "password": "CorrectPassword123!"},
    )
    assert res_success.status_code == 200
    token_data = res_success.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    assert token_data["role"] == "officer"

    # Verify reset in database
    auth_db_session.refresh(user)
    assert user.failed_login_count == 0
    assert user.locked_until is None
    last_login_utc = (
        user.last_login_at.replace(tzinfo=UTC)
        if user.last_login_at.tzinfo is None
        else user.last_login_at
    )
    assert last_login_utc == t_after_lock


def test_failed_login_state_committed_across_401(test_client: TestClient, auth_db_session: Session):
    """Failed login counter and audit record must survive the 401 HTTP response."""
    create_user_record(auth_db_session, username="target_user", password="ValidPassword123!")

    res = test_client.post(
        "/api/v1/auth/login",
        json={"username": "target_user", "password": "BadPassword123"},
    )
    assert res.status_code == 401

    # Verify committed state in fresh query
    user = auth_db_session.query(User).filter(User.username == "target_user").first()
    assert user.failed_login_count == 1

    audit_entry = (
        auth_db_session.query(AuditLog)
        .filter(AuditLog.user_id == user.id, AuditLog.event == "login_failure")
        .first()
    )
    assert audit_entry is not None
    assert audit_entry.entity == "user"
    assert audit_entry.entity_id == user.id


# ==============================================================================
# Token Validation, Algorithms, and RBAC Dependencies
# ==============================================================================


def test_token_lifecycle_and_security(auth_db_session: Session):
    """Test token validity, expiration, signature tampering, and alg=none rejection."""
    t0 = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)
    set_test_clock(t0)

    user = create_user_record(auth_db_session, username="token_user", role="officer")
    token = create_access_token(user.id, role=user.role, now=t0)

    # 1. Valid token decodes cleanly
    payload = decode_access_token(token, now=t0)
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "officer"

    # 2. Expired token is rejected
    t_expired = t0 + timedelta(minutes=61)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, now=t_expired)

    # 3. Tampered signature is rejected
    tampered_sig_char = "a" if token[-1] != "a" else "b"
    tampered_token = token[:-1] + tampered_sig_char
    with pytest.raises((jwt.InvalidSignatureError, jwt.DecodeError)):
        decode_access_token(tampered_token, now=t0)

    # 4. Token signed with wrong algorithm is rejected
    wrong_alg_token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": int(t0.timestamp()),
            "exp": int((t0 + timedelta(hours=1)).timestamp()),
        },
        get_settings().jwt_secret_key,
        algorithm="HS384",
    )
    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_access_token(wrong_alg_token, now=t0)

    # 5. Alg=none token is unconditionally rejected
    none_token = jwt.encode(
        {
            "sub": str(user.id),
            "iat": int(t0.timestamp()),
            "exp": int((t0 + timedelta(hours=1)).timestamp()),
        },
        key="",
        algorithm="none",
    )
    with pytest.raises(jwt.InvalidAlgorithmError):
        decode_access_token(none_token, now=t0)


def test_rbac_dependencies_and_immediate_database_lookup(auth_db_session: Session):
    """Role changes and deactivations must take immediate effect via database lookup."""
    t0 = datetime(2026, 11, 15, 12, 0, 0, tzinfo=UTC)
    set_test_clock(t0)

    admin = create_user_record(auth_db_session, username="admin_user", role="admin")
    admin_token = create_access_token(admin.id, role="admin", now=t0)
    auth_header = f"Bearer {admin_token}"

    # Verify admin access succeeds
    current = get_current_user(authorization=auth_header, db=auth_db_session)
    assert current.id == admin.id
    assert require_officer(current).role == "admin"
    assert require_admin(current).role == "admin"

    # 1. Demote admin to officer in DB: admin access must immediately fail (403)
    admin.role = "officer"
    auth_db_session.commit()

    current_demoted = get_current_user(authorization=auth_header, db=auth_db_session)
    assert require_officer(current_demoted).role == "officer"
    with pytest.raises(HTTPException) as exc_info:
        require_admin(current_demoted)
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "FORBIDDEN"

    # 2. Deactivate user in DB: token must be rejected (401)
    admin.is_active = False
    auth_db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(authorization=auth_header, db=auth_db_session)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["code"] == "UNAUTHORIZED"

    # 3. Missing authorization header returns 401
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(authorization=None, db=auth_db_session)
    assert exc_info.value.status_code == 401


# ==============================================================================
# Production Startup Refusals & Ephemeral Dev Secret
# ==============================================================================


def test_production_refuses_to_start_with_invalid_secrets(monkeypatch):
    """Production mode must refuse to start if secret is missing, short, or default."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    # Missing secret
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="FATAL: JWT_SECRET_KEY must be provided"):
        Settings()

    # Short secret (<32 chars)
    monkeypatch.setenv("JWT_SECRET_KEY", "too-short-secret-key")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="FATAL: JWT_SECRET_KEY must be at least 32 characters"):
        Settings()

    # Example template secret from .env.example
    monkeypatch.setenv("JWT_SECRET_KEY", "change-this-to-a-secure-random-secret-key-in-production")
    get_settings.cache_clear()
    with pytest.raises(
        RuntimeError, match="FATAL: JWT_SECRET_KEY cannot be set to a template/example"
    ):
        Settings()


def test_development_generates_ephemeral_secret_and_warns(monkeypatch, caplog):
    """Development environment generates random per-process secret without printing it."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    reset_ephemeral_jwt_secret()
    get_settings.cache_clear()

    with caplog.at_level(logging.WARNING):
        s = Settings()

    assert s.jwt_secret_key is not None
    assert len(s.jwt_secret_key) >= 32
    # Verify warning logged and secret is never printed in logs
    assert "JWT_SECRET_KEY is not set. Generated ephemeral" in caplog.text
    assert s.jwt_secret_key not in caplog.text


# ==============================================================================
# Mock vs Real Token Isolation
# ==============================================================================


def test_mock_token_rejected_in_real_mode(test_client: TestClient, auth_db_session: Session):
    """Real mode (MOCK_API=false) strictly rejects FAKE_MOCK_TOKEN."""
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(authorization=f"Bearer {FAKE_MOCK_TOKEN}", db=auth_db_session)
    assert exc_info.value.status_code == 401
    assert "Mock tokens are not accepted in real mode" in exc_info.value.detail["message"]


def test_real_token_rejected_in_mock_mode(monkeypatch, auth_db_session: Session):
    """Mock mode (MOCK_API=true) strictly rejects real signed tokens."""
    monkeypatch.setenv("MOCK_API", "true")
    get_settings.cache_clear()

    real_token = create_access_token(user_id=1, role="officer")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(authorization=f"Bearer {real_token}", db=auth_db_session)
    assert exc_info.value.status_code == 401
    assert "Mock mode accepts token" in exc_info.value.detail["message"]


# ==============================================================================
# Rate Limiting & X-Forwarded-For Bypass Prevention
# ==============================================================================


def test_rate_limiting_returns_429_and_ignores_x_forwarded_for(
    test_client: TestClient, auth_db_session: Session
):
    """Rate limiter returns 429 with Retry-After and ignores spoofed X-Forwarded-For."""
    create_user_record(auth_db_session, username="ratelimit_user")

    # Send 10 attempts from the same direct client
    for i in range(10):
        res = test_client.post(
            "/api/v1/auth/login",
            json={"username": "ratelimit_user", "password": "WrongPassword"},
            headers={"X-Forwarded-For": f"198.51.100.{i}"},  # Spoofed IP header
        )
        assert res.status_code == 401

    # 11th attempt must be rate-limited (429) regardless of new X-Forwarded-For
    res_limited = test_client.post(
        "/api/v1/auth/login",
        json={"username": "ratelimit_user", "password": "WrongPassword"},
        headers={"X-Forwarded-For": "203.0.113.99"},
    )
    assert res_limited.status_code == 429
    assert "Retry-After" in res_limited.headers
    assert res_limited.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"

    # Audit record for rate limit must be logged
    audit_row = (
        auth_db_session.query(AuditLog).filter(AuditLog.event == "rate_limit_exceeded").first()
    )
    assert audit_row is not None
    assert audit_row.user_id is None
    assert audit_row.entity == "auth"


# ==============================================================================
# Audit Trail Privacy and No Secret Leakage
# ==============================================================================


def test_audit_logs_and_privacy_guarantees(
    test_client: TestClient, auth_db_session: Session, caplog
):
    """Audit rows must exist without passwords, hashes, tokens, or unknown usernames."""
    user = create_user_record(
        auth_db_session, username="audit_officer", password="CorrectSecretPassword!"
    )

    with caplog.at_level(logging.DEBUG):
        # 1. Success login
        res_success = test_client.post(
            "/api/v1/auth/login",
            json={"username": "audit_officer", "password": "CorrectSecretPassword!"},
        )
        assert res_success.status_code == 200
        token = res_success.json()["access_token"]

        # 2. Failed login on existing user
        test_client.post(
            "/api/v1/auth/login",
            json={"username": "audit_officer", "password": "BadPassword!"},
        )

        # 3. Failed login on non-existent user
        test_client.post(
            "/api/v1/auth/login",
            json={"username": "non_existent_user_999", "password": "UnknownSecret!"},
        )

    # Verify audit log rows
    logs = auth_db_session.query(AuditLog).all()
    events = [entry.event for entry in logs]
    assert "login_success" in events
    assert "login_failure" in events

    # Unknown user row must have user_id=None
    unknown_audit = [
        entry for entry in logs if entry.user_id is None and entry.event == "login_failure"
    ]
    assert len(unknown_audit) >= 1

    # Invariant: No passwords, hashes, or unknown usernames in DB audit entries
    for log_item in logs:
        assert "CorrectSecretPassword!" not in log_item.event
        assert "BadPassword!" not in log_item.event
        assert "UnknownSecret!" not in log_item.event
        assert "non_existent_user_999" not in log_item.event

    # Invariant: No passwords, hashes, or tokens in logs
    assert "CorrectSecretPassword!" not in caplog.text
    assert "BadPassword!" not in caplog.text
    assert "UnknownSecret!" not in caplog.text
    assert user.password_hash not in caplog.text
    assert token not in caplog.text


def test_mock_mode_login_unchanged(monkeypatch, test_client: TestClient):
    """Mock mode (MOCK_API=true) continues returning mock tokens and checking wrong_password."""
    monkeypatch.setenv("MOCK_API", "true")
    get_settings.cache_clear()

    # Wrong password in mock mode
    res_wrong = test_client.post(
        "/api/v1/auth/login",
        json={"username": "officer_mock", "password": "wrong_password"},
    )
    assert res_wrong.status_code == 401
    assert res_wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"

    # Success in mock mode
    res_ok = test_client.post(
        "/api/v1/auth/login",
        json={"username": "officer_mock", "password": "any_mock_password"},
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["access_token"] == FAKE_MOCK_TOKEN
    assert TokenResponse.model_validate(data)
