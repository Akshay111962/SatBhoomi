"""Controllable clock for authentication, lockout, and token verification."""

from __future__ import annotations

from datetime import UTC, datetime

_CLOCK_OVERRIDE: datetime | None = None


def set_test_clock(now: datetime | None) -> None:
    """Set or clear a simulated current time for deterministic testing."""
    global _CLOCK_OVERRIDE
    _CLOCK_OVERRIDE = now


def is_clock_overridden() -> bool:
    """Return True if a simulated clock override is active."""
    return _CLOCK_OVERRIDE is not None


def get_current_time() -> datetime:
    """Return current UTC time or the injected test clock override."""
    if _CLOCK_OVERRIDE is not None:
        return _CLOCK_OVERRIDE
    return datetime.now(UTC)
