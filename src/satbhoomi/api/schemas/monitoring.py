"""[STABLE] In-season plot monitoring timeline and alert schemas (blueprint section 8).

Matches the real AlertItem and EvaluationCheckpointResult from
src/satbhoomi/alerts/models.py (T-09).
Rule 2 Compliance: Alerts strictly describe farm and repayment stress and support needed.
Action playbooks and workflow execution are finalised in Task T-12.
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
    """[STABLE] In-season stress alert summary mirroring AlertItem (T-09) and Alert ORM."""

    model_config = ConfigDict(frozen=True)

    id: int | None = Field(
        default=None, description="Database alert identifier if persisted", example=1
    )
    plot_code: str = Field(..., description="Synthetic plot code", example="PLOT-001")
    season: str = Field(..., description="Cropping season of the alert", example="2023-24")
    checkpoint_label: str = Field(
        ..., description="Seasonal monitoring checkpoint date", example="January 15"
    )
    detected_on: str = Field(
        ..., description="Date alert condition was detected (YYYY-MM-DD)", example="2024-01-15"
    )
    type: Literal["crop_health_drop", "rainfall_deficit", "price_crash"] = Field(
        ...,
        description="Type of in-season stress condition detected",
        example="crop_health_drop",
    )
    severity: Literal["low", "medium", "high"] = Field(
        ...,
        description="Severity level matching Alert ORM check constraint ('low', 'medium', 'high')",
        example="medium",
    )
    status: Literal["open", "acknowledged", "resolved", "dismissed"] = Field(
        default="open",
        description="Alert workflow state matching Alert ORM state constraints",
        example="open",
    )
    headline: str = Field(
        ...,
        description="Brief headline describing stress event with supportive framing",
        example="Vegetation vigor decline (18% drop below plot prior baseline)",
    )
    detail: str = Field(
        ...,
        description="Detailed agronomic explanation of stress indicator",
        example="At Jan 15, plot recorded vegetative drag indicating support needed.",
    )
    supportive_action: str = Field(
        ...,
        description="Recommended supportive action playbook for loan officer",
        example="Schedule supportive field visit to verify plot moisture and canopy vigor.",
    )
    data_gap_warning: str | None = Field(
        default=None,
        description="Diagnostic warning if cloud gap or missing prior baseline impacted detection",
        example=None,
    )


class PlotMonitoringResponse(BaseModel):
    """[STABLE] In-season plot monitoring timeline and active stress alerts.

    Mirrors EvaluationCheckpointResult (T-09). Action playbooks and resolution logs
    are finalised in Task T-12.
    """

    model_config = ConfigDict(frozen=True)

    plot_id: int = Field(..., description="Plot identifier", example=1)
    plot_code: str = Field(..., description="Synthetic plot code", example="PLOT-001")
    season: str = Field(..., description="Monitored cropping season", example="2023-24")
    status: Literal["ok", "data_gap"] = Field(
        default="ok",
        description="Checkpoint evaluation status ('ok' or 'data_gap')",
        example="ok",
    )
    data_gap_reason: str | None = Field(
        default=None,
        description="Explanatory text for data gap, if present",
        example=None,
    )
    checkpoint_label: str | None = Field(
        default=None,
        description="Active seasonal checkpoint label (e.g. 'January 15')",
        example="January 15",
    )
    evaluation_date: str | None = Field(
        default=None,
        description="Date of latest checkpoint evaluation (YYYY-MM-DD)",
        example="2024-01-15",
    )
    timeline: list[TimelinePoint] = Field(
        default_factory=list,
        description="Sequential time-series observations of crop health and rainfall",
    )
    active_alerts: list[AlertSummary] = Field(
        default_factory=list,
        description="List of currently active in-season alerts",
    )
    past_alerts: list[AlertSummary] = Field(
        default_factory=list,
        description="List of resolved or escalated historical alerts",
    )
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
