"""Assessment creation and score result schemas (blueprint section 8).

Matches the real RiskScoreResult from src/satbhoomi/risk/scoring.py (T-06).
Loan suggestion schema is tagged DRAFT and will be finalized in T-07.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.api.schemas.common import ResponseMeta
from satbhoomi.risk.loan_suggestions import (
    DISCLAIMER_LOAN_SUGGESTION,
    LimitBand,
    RepaymentSchedule,
)
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


class LoanSuggestionResponse(BaseModel):
    """[STABLE] Structured loan suggestion output mirroring LoanSuggestionResult (T-07).

    Indicative credit limit band for loan officer decision support only—not a credit
    sanction or approval. The human loan officer makes the final credit decision.
    Rule parameters derive from underwriting configuration and must be verified against
    RBI Master Directions and bank internal credit policy.
    """

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "manual_appraisal_required"] = Field(
        ...,
        description="Eligibility status: 'ok' or 'manual_appraisal_required'",
        example="ok",
    )
    plot_code: str = Field(..., description="Synthetic plot code", example="PLOT-001")
    season: str = Field(..., description="Target cropping season", example="2024-25")
    crop: str = Field(default="wheat", description="Cultivated crop name", example="wheat")
    area_acre: float = Field(..., gt=0, description="Plot area in acres", example=2.5)
    irrigation: str = Field(
        default="tube_well",
        description="Primary irrigation source",
        example="tube_well",
    )
    risk_band: Literal["low", "medium", "high"] | None = Field(
        default=None,
        description="Assigned risk band influencing haircut",
        example="low",
    )
    risk_score: int | None = Field(
        default=None,
        description="Assessed risk score (0-100)",
        example=18,
    )
    limit_band: LimitBand | None = Field(
        default=None,
        description="Indicative loan limit range in integer rupees based on DLTC Scale of Finance",
    )
    repayment_schedule: RepaymentSchedule | None = Field(
        default=None,
        description="Harvest-aligned repayment schedule specification",
    )
    insurance_required: bool = Field(
        default=False,
        description="Whether PMFBY enrollment is mandatory for this risk profile",
        example=False,
    )
    insurance_note: str = Field(
        ...,
        description="Explanation of crop insurance requirement or verification",
        example="Low risk: crop insurance recommended under standard KCC guidelines.",
    )
    disclaimer: str = Field(
        default=DISCLAIMER_LOAN_SUGGESTION,
        description="Statutory human-in-the-loop and decision-support disclaimer",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Auditable decision-support notes and Scale of Finance parameters",
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

    # Indicative loan suggestion component matching LoanSuggestionResult (T-07)
    loan_suggestion: LoanSuggestionResponse | None = Field(
        default=None,
        description=(
            "[STABLE] Structured loan suggestion output mirroring LoanSuggestionResult (T-07)."
        ),
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
