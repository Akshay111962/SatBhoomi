"""Deterministic underwriting suggestion rules (T-07, FR-006).

Computes right-sized loan limit bands from District Level Technical Committee (DLTC)
Scale of Finance (SoF), harvest-aligned repayment schedules, and mandatory crop
insurance flags grounded in the farm risk assessment.

In accordance with Rule 1 (Human-in-the-Loop):
SatBhoomi NEVER approves or rejects loans. These suggestions are structured decision-support
recommendations for human bank officers.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.risk.scoring import RiskScoreResult

# ---------------------------------------------------------------------------
# Constants: Scale of Finance & RBI Guidelines
# ---------------------------------------------------------------------------

SCALE_OF_FINANCE_WHEAT_IRRIGATED: Final[int] = 32_000  # INR per acre (Gujarat DLTC irrigated wheat)
SCALE_OF_FINANCE_WHEAT_RAINFED: Final[int] = 22_000  # INR per acre (Gujarat DLTC rainfed wheat)
RBI_COLLATERAL_FREE_LIMIT_INR: Final[int] = 200_000  # INR (RBI KCC collateral-free ceiling)

# Risk-based haircut multipliers for right-sizing limits [min_pct, max_pct]
LIMIT_BAND_RATIOS: Final[dict[str, tuple[float, float]]] = {
    "low": (0.90, 1.00),  # 90% - 100% of maximum scale limit
    "medium": (0.65, 0.80),  # 65% - 80% haircut to prevent over-indebtedness
    "high": (0.40, 0.50),  # 40% - 50% conservative cap for elevated risk
}

REPAYMENT_MONTH_RABI_WHEAT: Final[str] = "May"
REPAYMENT_WINDOW_LABEL: Final[str] = (
    "April–May (aligned with post-harvest APMC mandi arrivals and marketing window)"
)

DISCLAIMER_LOAN_SUGGESTION: Final[str] = (
    "Decision-support suggestion only. SatBhoomi does not approve or reject loans. "
    "Final credit sanction, limit approval, and risk determination rest exclusively "
    "with the designated bank loan officer (Rule 1: Human-in-the-Loop)."
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class LimitBand(BaseModel):
    """Right-sized loan limit band based on Scale of Finance and risk assessment."""

    model_config = ConfigDict(frozen=True)

    min_amount_inr: int = Field(ge=0, description="Lower bound of suggested loan limit in INR.")
    max_amount_inr: int = Field(ge=0, description="Upper bound of suggested loan limit in INR.")
    scale_of_finance_per_acre_inr: int = Field(
        ge=0, description="DLTC Scale of Finance per acre applied in INR."
    )
    gross_scale_limit_inr: int = Field(
        ge=0, description="Gross scale limit (area * SoF) before collateral cap."
    )
    collateral_free_cap_applied: bool = Field(
        description="True if gross scale exceeded RBI collateral-free limit (₹2,00,000)."
    )
    haircut_percentage_range: str = Field(
        description="Human-readable haircut percentage range applied for risk band."
    )


class RepaymentSchedule(BaseModel):
    """Harvest-aligned repayment schedule specification."""

    model_config = ConfigDict(frozen=True)

    repayment_month: str = Field(
        description="Recommended bullet repayment month (e.g. May for Rabi wheat)."
    )
    schedule_type: str = Field(
        default="bullet_post_harvest",
        description="Repayment structure (bullet post-harvest or installment).",
    )
    harvest_window: str = Field(
        default="March–April",
        description="Typical crop harvesting window for the region.",
    )
    marketing_window: str = Field(
        default="April–May",
        description="Peak marketing and mandi arrival window for crop sales.",
    )
    rationale: str = Field(
        description="Plain-language economic explanation for the scheduled repayment timing."
    )


class LoanSuggestionResult(BaseModel):
    """Structured loan suggestion output for bank loan officer review."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "manual_appraisal_required"]
    plot_code: str
    season: str
    crop: str
    area_acre: float = Field(gt=0)
    irrigation: str
    risk_band: Literal["low", "medium", "high"] | None = None
    risk_score: int | None = None
    limit_band: LimitBand | None = None
    repayment_schedule: RepaymentSchedule | None = None
    insurance_required: bool
    insurance_note: str
    disclaimer: str = DISCLAIMER_LOAN_SUGGESTION
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Loan Suggestion Engine
# ---------------------------------------------------------------------------


def generate_loan_suggestion(
    score_result: RiskScoreResult,
    *,
    area_acre: float,
    crop: str = "wheat",
    irrigation: str | None = None,
    insured: bool | int = False,
) -> LoanSuggestionResult:
    """Generate deterministic, right-sized loan suggestions from risk assessment.

    Args:
        score_result: Output from risk scoring engine (RiskScoreResult).
        area_acre: Plot operational area in acres (> 0).
        crop: Crop cultivated (defaults to 'wheat').
        irrigation: Irrigation source ('tube_well', 'canal', 'rainfed', etc.).
        insured: Whether the plot is already covered by crop insurance (0 or 1, False or True).

    Returns:
        Immutable LoanSuggestionResult containing limit band, repayment schedule,
        and mandatory insurance flags.
    """
    if area_acre <= 0:
        raise ValueError(f"area_acre must be strictly positive, got {area_acre}")

    plot_code = score_result.plot_code
    season = score_result.season
    irr_norm = (irrigation or "unknown").strip().lower()
    is_rainfed = irr_norm == "rainfed"
    is_already_insured = bool(insured)

    # 1. Handle insufficient data / missing score
    if score_result.status == "insufficient_data" or score_result.band is None:
        return LoanSuggestionResult(
            status="manual_appraisal_required",
            plot_code=plot_code,
            season=season,
            crop=crop,
            area_acre=float(area_acre),
            irrigation=irrigation or "unknown",
            risk_band=None,
            risk_score=None,
            limit_band=None,
            repayment_schedule=None,
            insurance_required=True,
            insurance_note=(
                "Mandatory PMFBY crop insurance enrollment and field inspection required "
                "prior to loan appraisal due to missing satellite or weather data."
            ),
            notes=[
                "Automated loan sizing suspended: insufficient data to establish farm risk score.",
                score_result.insufficient_data_reason
                or "Missing core satellite or weather observations.",
            ],
        )

    band = score_result.band
    score = score_result.score

    # 2. Determine Scale of Finance (SoF)
    sof = SCALE_OF_FINANCE_WHEAT_RAINFED if is_rainfed else SCALE_OF_FINANCE_WHEAT_IRRIGATED

    # 3. Compute Gross Scale Limit & Apply RBI Collateral-Free Cap (₹2,00,000)
    gross_scale = int(round(float(area_acre) * sof))
    capped_scale = min(gross_scale, RBI_COLLATERAL_FREE_LIMIT_INR)
    cap_applied = gross_scale > RBI_COLLATERAL_FREE_LIMIT_INR

    # 4. Apply Risk Band Haircuts to Right-Size Limit
    ratio_min, ratio_max = LIMIT_BAND_RATIOS.get(band, (0.50, 0.70))

    # Round to nearest ₹500 for practical banking limits
    raw_min = capped_scale * ratio_min
    raw_max = capped_scale * ratio_max
    suggested_min = int(round(raw_min / 500.0) * 500)
    suggested_max = int(round(raw_max / 500.0) * 500)

    haircut_pct = f"{int(ratio_min * 100)}%–{int(ratio_max * 100)}% of applicable scale"

    limit_band = LimitBand(
        min_amount_inr=suggested_min,
        max_amount_inr=suggested_max,
        scale_of_finance_per_acre_inr=sof,
        gross_scale_limit_inr=gross_scale,
        collateral_free_cap_applied=cap_applied,
        haircut_percentage_range=haircut_pct,
    )

    # 5. Determine Harvest-Aligned Repayment Schedule
    rationale = (
        "Wheat harvesting in March–April is followed by peak APMC mandi arrivals in April–May. "
        "Scheduling bullet repayment in May aligns debt service with peak crop liquidation, "
        "eliminating mid-season distress sales."
    )
    if band == "high":
        rationale += (
            " Recommended: officer mid-season health check in February/March"
            " to verify heading stage."
        )

    repayment_schedule = RepaymentSchedule(
        repayment_month=REPAYMENT_MONTH_RABI_WHEAT,
        schedule_type="bullet_post_harvest",
        harvest_window="March–April",
        marketing_window="April–May",
        rationale=rationale,
    )

    # 6. Determine Crop Insurance Flag
    notes: list[str] = []
    if is_already_insured:
        insurance_required = False
        insurance_note = (
            "Plot is already verified as covered by crop insurance (PMFBY / commercial policy)."
        )
    elif band == "low":
        insurance_required = False
        insurance_note = (
            "Crop insurance (PMFBY) is recommended to protect against unseasonal heatwaves "
            "or late rains, but is not mandatory for disbursal given favorable farm risk."
        )
    else:  # medium or high risk
        insurance_required = True
        insurance_note = (
            "Mandatory PMFBY crop insurance enrollment required prior to loan disbursal to "
            f"mitigate elevated farm stress risk ({band} risk band)."
        )

    if cap_applied:
        notes.append(
            f"Gross loan scale limit (₹{gross_scale:,}) capped at RBI collateral-free ceiling of "
            f"₹{RBI_COLLATERAL_FREE_LIMIT_INR:,} for smallholder KCC financing."
        )

    return LoanSuggestionResult(
        status="ok",
        plot_code=plot_code,
        season=season,
        crop=crop,
        area_acre=float(area_acre),
        irrigation=irr_norm,
        risk_band=band,
        risk_score=score,
        limit_band=limit_band,
        repayment_schedule=repayment_schedule,
        insurance_required=insurance_required,
        insurance_note=insurance_note,
        notes=notes,
    )
