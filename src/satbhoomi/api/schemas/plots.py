"""Plot registration, inspection, and pagination schemas (blueprint section 8)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta


class PlotCreateRequest(BaseModel):
    """Payload to register a new agricultural plot for assessment.

    Wording Rule: Zero personal data fields. Only anonymized identifiers allowed.
    """

    model_config = ConfigDict(frozen=True)

    farmer_id: int = Field(
        ...,
        description="Internal anonymized farmer reference ID",
        example=1,
    )
    crop: str = Field(
        default="wheat",
        description="Primary crop grown on the plot",
        example="wheat",
    )
    area_acre: float = Field(
        ...,
        gt=0.0,
        description="Plot operational area in acres (must be > 0)",
        example=2.5,
    )
    district: str = Field(
        default="Anand",
        description="District name in Gujarat",
        example="Anand",
    )
    village: str = Field(
        default="Boriavi",
        description="Village name",
        example="Boriavi",
    )
    lat: float | None = Field(
        default=22.5645,
        ge=-90.0,
        le=90.0,
        description="Representative latitude coordinate",
        example=22.5645,
    )
    lon: float | None = Field(
        default=72.9289,
        ge=-180.0,
        le=180.0,
        description="Representative longitude coordinate",
        example=72.9289,
    )
    geometry: str | None = Field(
        default=None,
        description="Optional boundary geometry string (GeoJSON or WKT polygon)",
        example=None,
    )
    irrigation: Literal["tube_well", "canal", "rainfed"] = Field(
        default="tube_well",
        description="Irrigation water source infrastructure",
        example="tube_well",
    )
    insured: int = Field(
        default=1,
        ge=0,
        le=1,
        description="PMFBY crop insurance coverage status (1=insured, 0=uninsured)",
        example=1,
    )


class PlotResponse(BaseModel):
    """Standard plot details response representation."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(..., description="Unique plot identifier", example=1)
    plot_code: str = Field(..., description="Synthetic plot code", example="PLOT-001")
    farmer_id: int = Field(..., description="Anonymized farmer ID", example=1)
    farmer_display_name: str = Field(
        ...,
        description="Synthetic non-PII farmer code",
        example="Farmer-001",
    )
    district: str = Field(..., example="Anand")
    village: str = Field(..., example="Boriavi")
    crop: str = Field(..., example="wheat")
    area_acre: float = Field(..., example=2.5)
    lat: float | None = Field(default=None, example=22.5645)
    lon: float | None = Field(default=None, example=72.9289)
    irrigation: str = Field(..., example="tube_well")
    insured: int = Field(..., example=1)
    created_at: str = Field(..., example="2026-11-13T10:00:00Z")
    meta: ResponseMeta | None = Field(default=None, description="Response metadata")


class PlotListResponse(BaseModel):
    """Paginated list envelope for plots."""

    model_config = ConfigDict(frozen=True)

    items: list[PlotResponse] = Field(..., description="List of plot records on the current page")
    total: int = Field(
        ..., description="Total number of matching plots across all pages", example=24
    )
    limit: int = Field(..., description="Page item limit", example=10)
    offset: int = Field(..., description="Page offset index", example=0)
    meta: ResponseMeta | None = Field(default=None, description="Response metadata")
