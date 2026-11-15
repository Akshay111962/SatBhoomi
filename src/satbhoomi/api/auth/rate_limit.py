"""In-memory per-IP rate limiter for authentication endpoints.

Architectural Note:
This in-memory rate limiter is per-process and does not share state across multiple worker
processes or load-balanced instances. In a multi-worker production cluster, use an external
distributed store (e.g., Redis).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class InMemoryLoginRateLimiter:
    """Thread-safe in-memory sliding window rate limiter keyed by client IP."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 60) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def check_attempt(
        self,
        client_ip: str,
        now: float | None = None,
    ) -> tuple[bool, int]:
        """Check whether a client IP is permitted to attempt login.

        Args:
            client_ip: Direct peer IP address (must not trust X-Forwarded-For).
            now: Optional current timestamp (epoch seconds) for deterministic testing.

        Returns:
            Tuple of (is_allowed: bool, retry_after_seconds: int).
        """
        current_time = time.time() if now is None else now
        cutoff = current_time - self.window_seconds

        with self._lock:
            # Prune attempts outside sliding window
            timestamps = [t for t in self._attempts[client_ip] if t > cutoff]

            if len(timestamps) >= self.max_attempts:
                # Rate limit exceeded: compute time until oldest attempt in window expires
                oldest_in_window = timestamps[0]
                retry_after = max(1, int(oldest_in_window + self.window_seconds - current_time) + 1)
                self._attempts[client_ip] = timestamps
                return False, retry_after

            # Record this attempt
            timestamps.append(current_time)
            self._attempts[client_ip] = timestamps
            return True, 0

    def reset(self) -> None:
        """Clear all recorded attempts (for test isolation)."""
        with self._lock:
            self._attempts.clear()


# Default singleton instance
login_rate_limiter = InMemoryLoginRateLimiter()
