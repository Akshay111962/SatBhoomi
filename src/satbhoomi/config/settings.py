"""Application configuration loaded from environment variables."""

import json
import os
from functools import lru_cache
from typing import Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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
