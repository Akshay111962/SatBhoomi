"""Authentication and session token schemas (blueprint section 8)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta


class LoginRequest(BaseModel):
    """Officer login credential payload."""

    model_config = ConfigDict(frozen=True)

    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="Bank loan officer or admin username",
        example="officer_anand",
    )
    password: str = Field(
        ...,
        min_length=6,
        description="User password",
        example="demo_password_123",
    )


class TokenResponse(BaseModel):
    """Session authentication token response."""

    model_config = ConfigDict(frozen=True)

    access_token: str = Field(
        ...,
        description="Bearer access token for API authorization",
        example="mock-officer-token-xyz",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type",
        example="bearer",
    )
    expires_in: int = Field(
        default=3600,
        description="Token lifetime in seconds",
        example=3600,
    )
    role: Literal["officer", "admin"] = Field(
        default="officer",
        description="Assigned system role",
        example="officer",
    )
    user_id: int = Field(
        ...,
        description="Internal user identifier",
        example=1,
    )
    display_name: str = Field(
        default="Officer Anand Branch",
        description="Display name of the authenticated user",
        example="Officer Anand Branch",
    )
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
