"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
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
        description="Deployment environment name",
    )
    log_level: str = Field(
        default="INFO",
        description="Application logging verbosity level",
    )
    debug: bool = Field(
        default=True,
        description="Whether debug mode and verbose errors are enabled",
    )

    # API Server
    api_host: str = Field(
        default="0.0.0.0",
        description="Network interface for FastAPI server",
    )
    api_port: int = Field(
        default=8000,
        description="Port for FastAPI server",
    )

    # Security
    secret_key: str = Field(
        default="change-this-to-a-secure-random-secret-key-in-production",
        description="HMAC secret key used for session signing and tokens",
    )

    # Database
    database_url: str = Field(
        default="sqlite:///./data/satbhoomi.db",
        description="Database connection URI (SQLite for PoC, PostgreSQL for production)",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()
