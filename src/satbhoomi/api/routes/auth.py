"""Authentication routes (blueprint section 8)."""

from __future__ import annotations

from datetime import UTC, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from satbhoomi.api.auth.clock import get_current_time
from satbhoomi.api.auth.passwords import dummy_hash, hash_password, needs_rehash, verify_password
from satbhoomi.api.auth.rate_limit import login_rate_limiter
from satbhoomi.api.auth.tokens import create_access_token
from satbhoomi.api.mock_data import FAKE_MOCK_TOKEN, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    standard_error_response,
)
from satbhoomi.api.schemas.auth import LoginRequest, TokenResponse
from satbhoomi.api.schemas.common import ErrorResponse, ResponseMeta
from satbhoomi.config.settings import get_settings
from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _generic_invalid_credentials_response() -> JSONResponse:
    """Return identical 401 response body across all authentication failure modes."""
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": {
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid username or password",
                "field": "password",
            }
        },
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Authenticate officer and issue session token."""
    if get_mock_status():
        # Check mock error triggers
        err = check_mock_error_triggers(x_mock_error)
        if err:
            return err

        # Simulate invalid credentials if password is "wrong_password"
        if payload.password == "wrong_password":
            return standard_error_response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="INVALID_CREDENTIALS",
                message="Invalid username or password",
                field="password",
            )

        # Return synthetic token in mock mode
        return TokenResponse(
            access_token=FAKE_MOCK_TOKEN,
            token_type="bearer",
            expires_in=3600,
            role="admin" if "admin" in payload.username.lower() else "officer",
            user_id=1,
            display_name=f"Officer {payload.username}",
            meta=SYNTHETIC_META,
        )

    # Real mode authentication
    now = get_current_time()
    settings = get_settings()

    # Per-IP rate limiting (direct client IP only; never trust X-Forwarded-For)
    client_ip = request.client.host if request.client else "127.0.0.1"
    is_allowed, retry_after = login_rate_limiter.check_attempt(
        client_ip=client_ip,
        now=now.timestamp(),
    )
    if not is_allowed:
        write_audit_log(
            db,
            user_id=None,
            event="rate_limit_exceeded",
            entity="auth",
            entity_id=0,
            at=now,
        )
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": {
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": (
                        f"Too many login attempts. Please retry after {retry_after} seconds."
                    ),
                    "field": None,
                }
            },
        )

    # User lookup
    user = db.query(User).filter(User.username == payload.username).first()

    if not user:
        # Unknown user: run dummy hash verification to equalize execution time
        verify_password(payload.password, dummy_hash())
        write_audit_log(
            db,
            user_id=None,
            event="login_failure",
            entity="auth",
            entity_id=0,
            at=now,
        )
        db.commit()
        return _generic_invalid_credentials_response()

    if not user.is_active:
        # Inactive user: verify against dummy hash
        verify_password(payload.password, dummy_hash())
        write_audit_log(
            db,
            user_id=user.id,
            event="login_failure",
            entity="user",
            entity_id=user.id,
            at=now,
        )
        db.commit()
        return _generic_invalid_credentials_response()

    # Lockout check
    locked_until = (
        user.locked_until.replace(tzinfo=UTC)
        if user.locked_until and user.locked_until.tzinfo is None
        else user.locked_until
    )

    if locked_until and locked_until > now:
        # Currently locked: do not increment counter, do not extend lock
        verify_password(payload.password, dummy_hash())
        write_audit_log(
            db,
            user_id=user.id,
            event="login_failure",
            entity="user",
            entity_id=user.id,
            at=now,
        )
        db.commit()
        return _generic_invalid_credentials_response()

    # If lock duration expired, reset lock state for fresh attempt
    if locked_until and locked_until <= now:
        user.locked_until = None
        user.failed_login_count = 0

    # Verify password against stored hash
    is_valid = verify_password(payload.password, user.password_hash)

    if not is_valid:
        user.failed_login_count += 1
        if user.failed_login_count >= settings.lockout_threshold:
            user.locked_until = now + timedelta(minutes=settings.lockout_duration_minutes)
            write_audit_log(
                db,
                user_id=user.id,
                event="lockout",
                entity="user",
                entity_id=user.id,
                at=now,
            )
        else:
            write_audit_log(
                db,
                user_id=user.id,
                event="login_failure",
                entity="user",
                entity_id=user.id,
                at=now,
            )
        db.commit()
        return _generic_invalid_credentials_response()

    # Successful login: reset failed attempts and lockout
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    write_audit_log(
        db,
        user_id=user.id,
        event="login_success",
        entity="user",
        entity_id=user.id,
        at=now,
    )
    db.commit()

    token = create_access_token(user_id=user.id, role=user.role, now=now)
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_token_lifetime_minutes * 60,
        role=user.role,
        user_id=user.id,
        display_name=user.name,
        meta=ResponseMeta(synthetic=False, version="0.1.0"),
    )
