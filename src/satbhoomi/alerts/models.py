"""Data models for Raksha in-season stress alerts (T-09, FR-008)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AlertItem(BaseModel):
    """Immutable representation of an active in-season farm stress alert."""

    model_config = ConfigDict(frozen=True)

    type: Literal["crop_health_drop", "rainfall_deficit", "price_crash"]
    severity: Literal["low", "medium", "high"]
    status: Literal["open", "acknowledged", "resolved", "dismissed"] = "open"
    detected_on: date
    checkpoint_label: str
    plot_code: str
    season: str
    headline: str
    detail: str
    supportive_action: str
    data_gap_warning: str | None = None


class EvaluationCheckpointResult(BaseModel):
    """Result of alert evaluation at a specific temporal checkpoint."""

    model_config = ConfigDict(frozen=True)

    plot_code: str
    season: str
    checkpoint_label: str
    evaluation_date: date
    status: Literal["ok", "data_gap"]
    data_gap_reason: str | None = None
    alerts: list[AlertItem] = Field(default_factory=list)


class ReplayReport(BaseModel):
    """Descriptive summary of historical alert replay across all plots and seasons."""

    model_config = ConfigDict(frozen=True)

    total_plots: int
    seasons_replayed: list[str]
    alert_counts_by_season: dict[str, int]
    alert_counts_by_type: dict[str, int]
    alert_counts_by_severity: dict[str, int]
    false_alert_rate_unflagged: float = Field(
        description="Alert rate on seasons with no confirmed bad disaster events."
    )
    synthetic_stress_scenario_tested: bool = Field(
        default=False,
        description="Whether replay was executed on the synthetic stress scenario.",
    )
    tc007_passed: bool = Field(
        description="True if early alerts fired before harvest on the synthetic stress scenario.",
    )
    notes: list[str] = Field(default_factory=list)
