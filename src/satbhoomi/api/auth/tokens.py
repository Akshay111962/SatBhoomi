"""JWT access token issuance and verification (blueprint section 8)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import jwt

from satbhoomi.api.auth.clock import get_current_time, is_clock_overridden
from satbhoomi.config.settings import get_settings


def create_access_token(
    user_id: int,
    role: str,
    expires_delta: timedelta | None = None,
    now: datetime | None = None,
) -> str:
    """Issue a signed HS256 JWT access token.

    Contains sub, iat, exp, and role claims. Never includes credentials or personal data.
    """
    settings = get_settings()
    current_time = now or get_current_time()
    lifetime = expires_delta or timedelta(minutes=settings.jwt_token_lifetime_minutes)
    expire_time = current_time + lifetime

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "iat": int(current_time.timestamp()),
        "exp": int(expire_time.timestamp()),
    }

    secret = settings.jwt_secret_key
    if not secret:
        raise RuntimeError("JWT secret key is not configured.")

    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(
    token: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Decode and strictly validate an HS256 JWT access token.

    Algorithm is fixed strictly to HS256; 'none' and other algorithms are unconditionally rejected.
    Claims exp, iat, and sub are mandatory.
    Supports injected clock for deterministic testing.
    """
    settings = get_settings()
    secret = settings.jwt_secret_key
    if not secret:
        raise RuntimeError("JWT secret key is not configured.")

    # When testing with an injected clock, disable PyJWT's internal system clock check
    # and perform deterministic temporal validation against current_dt.
    current_dt = now or get_current_time()
    use_system_clock = (now is None) and not is_clock_overridden()

    options = {
        "require": ["exp", "iat", "sub"],
        "verify_signature": True,
        "verify_exp": use_system_clock,
        "verify_iat": use_system_clock,
    }

    payload: dict[str, Any] = jwt.decode(
        token,
        key=secret,
        algorithms=["HS256"],
        options=options,
    )

    if not use_system_clock:
        current_ts = current_dt.timestamp()
        if payload.get("exp", 0) < current_ts:
            raise jwt.ExpiredSignatureError("Signature has expired")
        if payload.get("iat", 0) > current_ts:
            raise jwt.ImmatureSignatureError("The token is not yet valid (iat)")

    return payload
