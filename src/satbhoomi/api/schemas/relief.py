"""[DRAFT] Calamity relief evidence report schemas (blueprint section 8).

Tagged DRAFT. Subject to expansion and refinement in Task T-12.
Mandatory Disclaimer: Official crop loss assessment decides.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta


class ReliefReportResponse(BaseModel):
    """[DRAFT] Crop calamity relief evidence report payload.

    Tagged DRAFT: Will be refined in Task T-12.
    """

    model_config = ConfigDict(frozen=True)

    plot_id: int = Field(..., description="Target plot identifier", example=1)
    plot_code: str = Field(..., description="Synthetic plot code", example="PLOT-001")
    season: str = Field(..., description="Affected cropping season", example="2023-24")
    baseline_ndvi_mean: float = Field(
        ...,
        description="Historical benchmark NDVI for plot in this calendar window",
        example=0.68,
    )
    current_ndvi_mean: float = Field(
        ...,
        description="Recorded in-season NDVI mean",
        example=0.42,
    )
    ndvi_drop_pct: float = Field(
        ...,
        description="Percentage drop below historical baseline",
        example=38.2,
    )
    estimated_loss_band: str = Field(
        ...,
        description="Categorical crop loss band estimate (e.g. 33% to 50%)",
        example="33% to 50% loss",
    )
    exceeds_rbi_33_threshold: bool = Field(
        ...,
        description="Whether estimated crop loss meets or exceeds the RBI 33% threshold",
        example=True,
    )
    supporting_evidence_summary: str = Field(
        ...,
        description="Summary of satellite vegetative decline and meteorological deficit",
        example=(
            "Vegetative vigor fell 38.2% below historical baseline following winter dry spell."
        ),
    )

    # Mandatory Disclaimer Rule
    disclaimer: str = Field(
        default=(
            "Official crop loss assessment and calamity declaration remain strictly "
            "with government and bank relief committees. This evidence report is for "
            "decision support only."
        ),
        description="Mandatory statutory relief disclaimer",
    )
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
