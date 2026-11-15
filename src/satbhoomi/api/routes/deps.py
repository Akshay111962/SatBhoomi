"""Common route dependencies, mock authentication, and error builders."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from satbhoomi.api.auth.tokens import decode_access_token
from satbhoomi.api.mock_data import FAKE_MOCK_TOKEN
from satbhoomi.config.settings import get_settings
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db


def get_mock_status() -> bool:
    """Return True if MOCK_API mode is active."""
    return bool(get_settings().mock_api)


def not_implemented_response() -> JSONResponse:
    """Return standard 501 Not Implemented response envelope."""
    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={
            "error": {
                "code": "NOT_IMPLEMENTED",
                "message": (
                    "Endpoint not implemented. Enable mock mode with "
                    "MOCK_API=true for frontend development."
                ),
                "field": None,
            }
        },
    )


def standard_error_response(
    status_code: int,
    code: str,
    message: str,
    field: str | None = None,
) -> JSONResponse:
    """Construct a JSONResponse conforming to standard error envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "field": field,
            }
        },
    )


def verify_mock_auth(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    """Validate mock bearer token when running in mock mode.

    Documented as FAKE mock authentication. Strictly non-reusable in production.
    """
    settings = get_settings()
    if not settings.mock_api:
        # In non-mock mode, will return 501 at route handler
        return "not_implemented"

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Authorization header is required (use Bearer mock-officer-token-xyz)",
                "field": "authorization",
            },
        )

    token = authorization.replace("Bearer ", "").strip()
    if token != FAKE_MOCK_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": (
                    "Invalid session token. Mock mode accepts token 'mock-officer-token-xyz'"
                ),
                "field": "authorization",
            },
        )

    return token


def check_mock_error_triggers(
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
    resource_id: int | None = None,
) -> JSONResponse | None:
    """Check explicit mock error simulation headers or sentinel IDs."""
    target_code = None
    if x_mock_error:
        try:
            target_code = int(x_mock_error)
        except ValueError:
            pass
    elif resource_id in (400, 401, 403, 404, 429, 500, 999):
        target_code = 404 if resource_id == 999 else resource_id

    if target_code == 400:
        return standard_error_response(
            400, "VALIDATION_ERROR", "Invalid request parameters provided", "id"
        )
    if target_code == 401:
        return standard_error_response(
            401, "UNAUTHORIZED", "Invalid or expired session token", "authorization"
        )
    if target_code == 403:
        return standard_error_response(
            403, "FORBIDDEN", "Insufficient permissions to access this resource", None
        )
    if target_code == 404:
        return standard_error_response(404, "NOT_FOUND", "Requested resource not found", "id")
    if target_code == 429:
        return standard_error_response(
            429,
            "RATE_LIMIT_EXCEEDED",
            "Rate limit exceeded. Please retry after 60 seconds.",
            None,
        )
    if target_code == 500:
        return standard_error_response(
            500,
            "INTERNAL_SERVER_ERROR",
            "An unexpected internal server error occurred",
            None,
        )

    return None


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> User:
    """Validate Bearer access token and load the active user from the database.

    Enforces:
    - Real mode rejects FAKE_MOCK_TOKEN.
    - Mock mode accepts FAKE_MOCK_TOKEN and rejects real signed tokens.
    - Token validity, signature, expiration, and mandatory claims.
    - Immediate database lookup ensuring deactivation or demotion takes immediate effect.
    """
    settings = get_settings()

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Authorization header is required",
                "field": "authorization",
            },
        )

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Invalid authorization header format. Expected 'Bearer <token>'",
                "field": "authorization",
            },
        )
    token = parts[1]

    if settings.mock_api:
        if token != FAKE_MOCK_TOKEN:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "UNAUTHORIZED",
                    "message": (
                        "Invalid session token. Mock mode accepts token 'mock-officer-token-xyz'"
                    ),
                    "field": "authorization",
                },
            )
        # In mock mode, synthesize a mock active officer
        return User(
            id=1,
            username="mock_officer",
            name="Mock Officer",
            role="officer",
            password_hash="mock",
            is_active=True,
        )

    # Real mode
    if token == FAKE_MOCK_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Mock tokens are not accepted in real mode",
                "field": "authorization",
            },
        )

    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Invalid, expired, or tampered access token",
                "field": "authorization",
            },
        ) from None

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Access token missing subject claim",
                "field": "authorization",
            },
        )

    try:
        user_id = int(sub)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "Invalid access token subject",
                "field": "authorization",
            },
        ) from None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "UNAUTHORIZED",
                "message": "User not found or account is deactivated",
                "field": "authorization",
            },
        )

    return user


def require_officer(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Authorize access for officer or admin roles."""
    if current_user.role not in ("officer", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "Officer or Admin role required",
                "field": None,
            },
        )
    return current_user


def require_admin(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Authorize access strictly for admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "FORBIDDEN",
                "message": "Admin role required",
                "field": None,
            },
        )
    return current_user
