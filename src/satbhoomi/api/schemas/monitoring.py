"""[DRAFT] In-season plot monitoring timeline and alert schemas (blueprint section 8).

Tagged DRAFT. Subject to refinement and expansion in Task T-09.
Rule 2 Compliance: Alerts strictly describe farm and repayment stress and support needed.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta


class TimelinePoint(BaseModel):
    """Observation point along the season timeline."""

    model_config = ConfigDict(frozen=True)

    date: str = Field(..., description="Observation date (YYYY-MM-DD)", example="2023-12-15")
    ndvi: float | None = Field(default=None, description="Clear-sky NDVI value", example=0.52)
    rainfall_mm: float | None = Field(
        default=None, description="Daily/cumulative rainfall in mm", example=4.5
    )
    data_gap: bool = Field(
        default=False, description="Whether cloud cover or missing scene created a data gap"
    )


class AlertSummary(BaseModel):
    """In-season stress alert summary."""

    model_config = ConfigDict(frozen=True)

    id: int = Field(..., description="Alert ID", example=1)
    type: Literal["crop_health_drop", "rainfall_deficit", "price_crash"] = Field(
        ...,
        description="Type of in-season stress condition detected",
        example="crop_health_drop",
    )
    severity: Literal["low", "medium", "high"] = Field(
        ...,
        description="Severity level matching database constraint",
        example="medium",
    )
    status: Literal["open", "acknowledged", "resolved", "dismissed"] = Field(
        default="open",
        description="Alert workflow state",
        example="open",
    )
    detected_on: str = Field(..., description="Date alert was detected", example="2023-12-15")
    headline: str = Field(
        ...,
        description="Brief headline describing stress event",
        example="Vegetation vigor decline (18% drop below plot prior baseline)",
    )
    detail: str = Field(
        ...,
        description="Detailed agronomic explanation",
        example="At Dec 15, plot recorded vegetative drag indicating support needed.",
    )
    supportive_action: str = Field(
        ...,
        description="Recommended supportive action playbook for loan officer",
        example="Schedule supportive field visit to verify plot moisture and canopy vigor.",
    )


class PlotMonitoringResponse(BaseModel):
    """[DRAFT] In-season plot monitoring timeline and active stress alerts.

    Tagged DRAFT: Will be refined in Task T-09.
    """

    model_config = ConfigDict(frozen=True)

    plot_id: int = Field(..., description="Plot identifier", example=1)
    plot_code: str = Field(..., description="Synthetic plot code", example="PLOT-001")
    season: str = Field(..., description="Monitored cropping season", example="2023-24")
    data_gap_flag: bool = Field(
        default=False,
        description="Flag indicating whether cloud cover produced an active data gap banner",
        example=False,
    )
    data_gap_note: str | None = Field(
        default=None,
        description="Explanatory text for data gap, if present",
        example=None,
    )
    timeline: list[TimelinePoint] = Field(
        default_factory=list,
        description="Sequential time-series observations of crop health and rainfall",
    )
    active_alerts: list[AlertSummary] = Field(
        default_factory=list,
        description="List of currently active in-season alerts",
    )
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
