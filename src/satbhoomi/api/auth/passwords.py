"""Argon2id password hashing and verification module.

Architectural Decisions:
- Algorithm: Argon2id (RFC 9106) via argon2-cffi.
- Replaces legacy/insecure algorithms (MD5, SHA1, plain bcrypt, and passlib).
- Standard parameters: time_cost=3, memory_cost=65536 KiB (64 MiB), parallelism=4.
- Lower-cost parameters (time_cost=1, memory_cost=1024 KiB, parallelism=1) are strictly
  forbidden in production and allowed ONLY when ENVIRONMENT=test.
- Zero secrets logging: Passwords and password hashes are never logged.
"""

from __future__ import annotations

import secrets
from typing import Final

from argon2 import PasswordHasher, Type, exceptions

from satbhoomi.config.settings import Settings, get_settings

# Fallback precomputed dummy hash for constant-time rejection of unknown users
DUMMY_SALT: Final[str] = "satbhoomi_dummy_timing_mitigation"


def get_hasher(settings: Settings | None = None) -> PasswordHasher:
    """Instantiate and return an Argon2id PasswordHasher based on active environment settings.

    Raises:
        RuntimeError: If lower-cost test parameters are requested outside ENVIRONMENT=test.
    """
    cfg = settings or get_settings()

    if cfg.argon2_low_cost_for_test:
        if cfg.is_production or not cfg.is_test:
            raise RuntimeError(
                "Lower-cost Argon2id hashing parameters are forbidden outside ENVIRONMENT=test."
            )
        return PasswordHasher(
            time_cost=1,
            memory_cost=1024,
            parallelism=1,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    return PasswordHasher(
        time_cost=cfg.argon2_time_cost,
        memory_cost=cfg.argon2_memory_cost_kib,
        parallelism=cfg.argon2_parallelism,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    )


def hash_password(plain_password: str, *, settings: Settings | None = None) -> str:
    """Hash a plain text password using Argon2id.

    Args:
        plain_password: Cleartext password string.
        settings: Optional custom or overridden application settings.

    Returns:
        Encoded Argon2id hash string ($argon2id$v=19$m=...$...).
    """
    hasher = get_hasher(settings)
    return hasher.hash(plain_password)


def verify_password(
    plain_password: str,
    password_hash: str,
    *,
    settings: Settings | None = None,
) -> bool:
    """Verify a cleartext password against an Argon2id hash.

    Args:
        plain_password: Cleartext password to check.
        password_hash: Encoded password hash from database.
        settings: Optional custom settings.

    Returns:
        True if password matches hash; False on mismatch or corrupted hash.
    """
    hasher = get_hasher(settings)
    try:
        return hasher.verify(password_hash, plain_password)
    except (
        exceptions.VerifyMismatchError,
        exceptions.VerificationError,
        exceptions.InvalidHashError,
    ):
        return False


def needs_rehash(password_hash: str, *, settings: Settings | None = None) -> bool:
    """Check if an existing password hash needs re-hashing due to parameter updates.

    Args:
        password_hash: Encoded hash string to evaluate.
        settings: Optional custom settings.

    Returns:
        True if hash parameters differ from the active hasher's configuration.
    """
    hasher = get_hasher(settings)
    try:
        return hasher.check_needs_rehash(password_hash)
    except exceptions.InvalidHashError:
        return True


_cached_dummy_hash: str | None = None
_cached_dummy_mode: tuple[bool, int, int, int] | None = None


def dummy_hash(*, settings: Settings | None = None) -> str:
    """Return a valid Argon2id hash formatted with current cost parameters.

    Used during authentication attempts for non-existent users so the server
    performs identical key derivation work and takes the same elapsed time as
    a valid user lookup, preventing user-enumeration timing side-channels.
    """
    global _cached_dummy_hash, _cached_dummy_mode
    cfg = settings or get_settings()
    mode_key = (
        cfg.argon2_low_cost_for_test,
        cfg.argon2_time_cost,
        cfg.argon2_memory_cost_kib,
        cfg.argon2_parallelism,
    )

    if _cached_dummy_hash is None or _cached_dummy_mode != mode_key:
        hasher = get_hasher(cfg)
        # Hash a random token so dummy hash is fully formed and verifiable
        _cached_dummy_hash = hasher.hash(secrets.token_hex(16))
        _cached_dummy_mode = mode_key

    return _cached_dummy_hash
