"""Assessment creation and score result schemas (blueprint section 8).

Matches the real RiskScoreResult from src/satbhoomi/risk/scoring.py (T-06).
Loan suggestion schema is tagged DRAFT and will be finalized in T-07.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta
from satbhoomi.risk.scoring import (
    FIXED_INTERPRETATION,
    FIXED_RELIABILITY_NOTE,
    RULES_BASELINE_VERSION,
)


class ReasonItem(BaseModel):
    """Structured plain-language reason attributed to a specific model feature."""

    model_config = ConfigDict(frozen=True)

    feature_name: str = Field(
        ...,
        description="Name of the predictive feature driving this attribution",
        example="ndvi_trend_pre_cutoff",
    )
    text: str = Field(
        ...,
        description="Plain-language reason explanation for loan officers",
        example="Vegetative canopy vigor expanded steadily through January.",
    )


class DraftLoanSuggestion(BaseModel):
    """[DRAFT] Preliminary loan suggestion structure.

    Subject to expansion and rule refinement in Task T-07.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "insufficient_data"] = Field(
        default="ok",
        description="Loan suggestion determination status",
        example="ok",
    )
    suggested_limit_inr: float = Field(
        ...,
        ge=0.0,
        description="Recommended maximum credit limit in INR",
        example=80000.0,
    )
    repayment_month: str = Field(
        default="May",
        description="Harvest-aligned bullet repayment month",
        example="May",
    )
    mandatory_crop_insurance: bool = Field(
        default=True,
        description="Whether PMFBY enrollment is mandatory for this risk profile",
        example=True,
    )
    scale_of_finance_applied_inr_per_acre: float = Field(
        default=32000.0,
        description="District DLTC Scale of Finance benchmark per acre",
        example=32000.0,
    )
    risk_haircut_pct: float = Field(
        default=0.0,
        description="Risk band adjustment haircut percentage applied to limit",
        example=0.0,
    )
    disclaimer: str = Field(
        default=(
            "Loan limits are decision-support suggestions for bank loan officers only. "
            "The human loan officer makes the final credit decision."
        ),
        description="Decision-support disclaimer",
    )


class AssessmentCreateRequest(BaseModel):
    """Payload to trigger a new farm risk assessment for a plot."""

    model_config = ConfigDict(frozen=True)

    season: str = Field(
        default="2024-25",
        description="Target agricultural cropping season",
        example="2024-25",
    )


class AssessmentResponse(BaseModel):
    """Farm credit risk assessment result matching RiskScoreResult (T-06).

    Zero personal data fields. Only farm agronomic risk attributes.
    """

    model_config = ConfigDict(frozen=True)

    id: int = Field(..., description="Unique assessment identifier", example=1)
    plot_id: int = Field(..., description="Plot reference identifier", example=1)
    plot_code: str = Field(..., description="Synthetic plot code", example="PLOT-001")
    season: str = Field(..., description="Assessed cropping season", example="2024-25")

    # Core scoring fields matching RiskScoreResult
    status: Literal["ok", "insufficient_data"] = Field(
        ...,
        description="Evaluation status: ok or insufficient_data",
        example="ok",
    )
    score: int | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "Deterministic risk score (0=lowest risk, 100=highest risk; null if insufficient_data)"
        ),
        example=18,
    )
    band: Literal["low", "medium", "high"] | None = Field(
        default=None,
        description="Risk tier categorization (low, medium, high)",
        example="low",
    )
    reasons: list[ReasonItem] = Field(
        default_factory=list,
        description="Exactly 3 plain-language explanations with feature names",
    )
    protective_factor: str | None = Field(
        default=None,
        description="Key resilience or protective factor mitigating risk",
        example="Assured tubewell irrigation buffers plot from winter precipitation deficit.",
    )
    model_version: str = Field(
        default=RULES_BASELINE_VERSION,
        description="Exact model or baseline version identifier",
        example=RULES_BASELINE_VERSION,
    )
    scorer: Literal["rules_baseline", "logreg"] = Field(
        default="rules_baseline",
        description="Active scoring implementation",
        example="rules_baseline",
    )
    cutoff_date: str = Field(
        default="January 31",
        description="In-season temporal cutoff date",
        example="January 31",
    )
    data_warnings: list[str] = Field(
        default_factory=list,
        description="Diagnostic data quality warnings (e.g. cloud gaps)",
    )
    insufficient_data_reason: str | None = Field(
        default=None,
        description="Explanation if status is insufficient_data",
    )
    interpretation: str = Field(
        default=FIXED_INTERPRETATION,
        description="Mandatory scoring interpretation banner",
    )
    reliability_note: str = Field(
        default=FIXED_RELIABILITY_NOTE,
        description="Mandatory validation status disclosure",
    )

    # [DRAFT] preliminary loan suggestion component
    loan_suggestion: DraftLoanSuggestion | None = Field(
        default=None,
        description="[DRAFT] Preliminary loan suggestion structure. Subject to change in T-07.",
    )

    created_at: str = Field(
        ...,
        description="Assessment generation timestamp",
        example="2026-11-13T10:05:00Z",
    )
    meta: ResponseMeta | None = Field(
        default=None,
        description="Response metadata container",
    )
