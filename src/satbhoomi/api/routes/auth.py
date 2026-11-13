"""Authentication routes (blueprint section 8)."""

from __future__ import annotations

from fastapi import APIRouter, Header, Response, status

from satbhoomi.api.mock_data import FAKE_MOCK_TOKEN, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    not_implemented_response,
    standard_error_response,
)
from satbhoomi.api.schemas.auth import LoginRequest, TokenResponse
from satbhoomi.api.schemas.common import ErrorResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


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
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Authenticate officer and issue session token."""
    if not get_mock_status():
        return not_implemented_response()

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
