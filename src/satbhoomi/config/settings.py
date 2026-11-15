"""Application configuration loaded from environment variables."""

import json
import logging
import os
import secrets
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_EPHEMERAL_JWT_SECRET: str | None = None

EXAMPLE_JWT_SECRETS: frozenset[str] = frozenset(
    {
        "change-this-to-a-secure-random-secret-key-in-production",
        "your_jwt_secret_key_here",
        "your-jwt-secret-key-here-minimum-32-chars",
        "replace_with_a_secure_random_jwt_secret_key_32_chars_min",
    }
)


def reset_ephemeral_jwt_secret() -> None:
    """Reset the module-level ephemeral secret (used for test isolation)."""
    global _EPHEMERAL_JWT_SECRET
    _EPHEMERAL_JWT_SECRET = None


def _get_ephemeral_jwt_secret() -> str:
    """Generate or retrieve ephemeral secret when JWT_SECRET_KEY is unset in dev/test."""
    global _EPHEMERAL_JWT_SECRET
    if _EPHEMERAL_JWT_SECRET is None:
        _EPHEMERAL_JWT_SECRET = secrets.token_urlsafe(32)
        logger.warning(
            "JWT_SECRET_KEY is not set. Generated ephemeral per-process secret. "
            "Active tokens will stop working when the server restarts."
        )
    return _EPHEMERAL_JWT_SECRET


class Settings(BaseSettings):
    """Central configuration for SatBhoomi Score + Raksha."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(
        default="SatBhoomi Score + Raksha",
        description="Public display name of the application",
    )
    app_env: Literal["development", "staging", "production", "test"] = Field(
        default="development",
        alias="APP_ENV",
        description="Deployment environment name",
    )
    environment: str | None = Field(
        default=None,
        alias="ENVIRONMENT",
        description="Alternative deployment environment name",
    )
    log_level: str = Field(
        default="INFO",
        description="Application logging verbosity level",
    )
    debug: bool = Field(
        default=True,
        description="Whether debug mode and verbose errors are enabled",
    )

    # API Server & Mock Mode
    api_host: str = Field(
        default="0.0.0.0",
        description="Network interface for FastAPI server",
    )
    api_port: int = Field(
        default=8000,
        description="Port for FastAPI server",
    )
    mock_api: bool = Field(
        default=False,
        alias="MOCK_API",
        description="Whether to run API in synthetic mock mode for frontend development",
    )
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"],
        alias="CORS_ALLOWED_ORIGINS",
        description="Configurable allowed origins for Cross-Origin Resource Sharing",
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                return json.loads(v)
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_production(self) -> bool:
        """Return True if running in production environment."""
        env_val = os.environ.get("ENVIRONMENT") or self.environment or self.app_env or "development"
        return env_val.lower() == "production"

    @property
    def is_test(self) -> bool:
        """Return True if running in test environment."""
        env_val = os.environ.get("ENVIRONMENT") or self.environment or self.app_env or "development"
        return env_val.lower() == "test"

    # Security & Password Hashing (Argon2id)
    secret_key: str = Field(
        default="change-this-to-a-secure-random-secret-key-in-production",
        description="HMAC secret key used for session signing and tokens",
    )
    jwt_secret_key: str | None = Field(
        default=None,
        alias="JWT_SECRET_KEY",
        description="JWT secret key from environment variable; no hardcoded default in code",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm. Fixed strictly to HS256",
    )
    jwt_token_lifetime_minutes: int = Field(
        default=60,
        alias="JWT_TOKEN_LIFETIME_MINUTES",
        description="JWT session token validity lifetime in minutes",
    )
    login_rate_limit_per_minute: int = Field(
        default=10,
        alias="LOGIN_RATE_LIMIT_PER_MINUTE",
        description="Max login attempts per minute per direct client IP address",
    )
    lockout_threshold: int = Field(
        default=5,
        description="Number of consecutive failed logins before account lockout",
    )
    lockout_duration_minutes: int = Field(
        default=15,
        description="Duration of account lockout in minutes",
    )
    argon2_time_cost: int = Field(
        default=3,
        description="Argon2id time cost (iterations)",
    )
    argon2_memory_cost_kib: int = Field(
        default=65536,
        description="Argon2id memory cost in KiB",
    )
    argon2_parallelism: int = Field(
        default=4,
        description="Argon2id parallelism (lanes/threads)",
    )
    argon2_low_cost_for_test: bool = Field(
        default=False,
        alias="ARGON2_LOW_COST_FOR_TEST",
        description="Lower-cost Argon2id parameters strictly allowed only when ENVIRONMENT=test",
    )

    def validate_production_security(self) -> None:
        """Validate security invariants required for production environment."""
        if not self.is_production:
            return
        if self.mock_api:
            raise RuntimeError("FATAL: MOCK_API cannot be enabled in production environment.")
        raw_secret = os.environ.get("JWT_SECRET_KEY") or self.jwt_secret_key
        if not raw_secret:
            raise RuntimeError(
                "FATAL: JWT_SECRET_KEY must be provided via environment variable in production."
            )
        if len(raw_secret) < 32:
            raise RuntimeError(
                "FATAL: JWT_SECRET_KEY must be at least 32 characters in production."
            )
        if raw_secret in EXAMPLE_JWT_SECRETS:
            raise RuntimeError(
                "FATAL: JWT_SECRET_KEY cannot be set to a template/example value in production."
            )

    def model_post_init(self, __context: Any) -> None:
        """Enforce production security validations and initialize ephemeral dev secrets."""
        super().model_post_init(__context)
        if self.is_production:
            self.validate_production_security()
        else:
            if not self.jwt_secret_key:
                self.jwt_secret_key = _get_ephemeral_jwt_secret()

    # Database
    database_url: str = Field(
        default="sqlite:///./data/satbhoomi.db",
        description="Database connection URI (SQLite for PoC, PostgreSQL for production)",
    )

    # External Provider Credentials
    ceda_api_key: str | None = Field(
        default=None,
        description="API key for CEDA Agri Market API",
    )
    gee_project: str | None = Field(
        default=None,
        description="Google Earth Engine project ID",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()
