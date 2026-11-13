"""Common schema envelopes and error models for SatBhoomi API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    """Structured error object conforming to SatBhoomi blueprint section 8."""

    model_config = ConfigDict(frozen=True)

    code: str = Field(
        ...,
        description=(
            "Machine-readable error code (e.g. VALIDATION_ERROR, NOT_FOUND, NOT_IMPLEMENTED)"
        ),
        example="VALIDATION_ERROR",
    )
    message: str = Field(
        ...,
        description="Human-readable explanation of the error",
        example="area_acre must be above 0",
    )
    field: str | None = Field(
        default=None,
        description="Request field that triggered the error, if applicable",
        example="area_acre",
    )


class ErrorResponse(BaseModel):
    """Standard API error response envelope."""

    model_config = ConfigDict(frozen=True)

    error: ErrorDetail


class ResponseMeta(BaseModel):
    """Standard metadata container for API responses."""

    model_config = ConfigDict(frozen=True)

    synthetic: bool = Field(
        default=False,
        description="Flag indicating whether response payload is synthetic mock data",
        example=True,
    )
    version: str = Field(
        default="0.1.0",
        description="API contract version",
        example="0.1.0",
    )
    extra: dict[str, Any] | None = Field(
        default=None,
        description="Additional context-specific metadata",
    )
