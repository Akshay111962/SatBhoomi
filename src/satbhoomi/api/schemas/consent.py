"""Consent management schemas (blueprint section 8, DPDP Act 2023 compliance)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

ALLOWED_CONSENT_PURPOSES: tuple[str, ...] = (
    "credit_scoring",
    "in_season_monitoring",
    "relief_assessment",
    "farmer_summary",
    "farm_advisory",
)


class ConsentCreateRequest(BaseModel):
    """Payload to grant a new processing consent for a farmer."""

    model_config = ConfigDict(frozen=True)

    purpose: str = Field(
        ...,
        description="Stated processing purpose from fixed allowed list",
        example="credit_scoring",
    )


class ConsentResponse(BaseModel):
    """Representation of an individual farmer consent record."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(..., description="Unique consent identifier", example=1)
    farmer_id: int = Field(..., description="Farmer identifier", example=1)
    purpose: str = Field(..., description="Processing purpose", example="credit_scoring")
    given_on: str = Field(
        ...,
        description="UTC ISO timestamp when consent was granted",
        example="2026-11-16T10:00:00Z",
    )
    withdrawn_on: str | None = Field(
        default=None,
        description="Nullable UTC ISO timestamp if revoked",
        example=None,
    )
    recorded_by: int = Field(
        ...,
        description="Officer user ID who recorded the consent",
        example=1,
    )


class ConsentListResponse(BaseModel):
    """List response envelope for a farmer's consent history."""

    model_config = ConfigDict(frozen=True)

    items: list[ConsentResponse] = Field(..., description="List of consent records")
    total: int = Field(..., description="Total count of consents for farmer", example=1)
