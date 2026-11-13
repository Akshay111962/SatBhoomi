"""What-if simulation engine for controllable risk interventions (T-08, FR-007).

Allows bank officers to simulate the prospective impact of controllable farmer
interventions (e.g. crop insurance enrollment, tubewell/drip irrigation installation,
or supplementary protective irrigation) on the farm risk score and right-sized loan limit.

In accordance with Rule 6 (What-If Simulator Integrity):
All outputs are strictly labeled "estimate" and are model-based sensitivity projections,
NOT proof of causation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.risk.loan_suggestions import LimitBand, generate_loan_suggestion
from satbhoomi.risk.scoring import (
    RiskScoreResult,
    map_score_to_band,
    score_plot_season,
)

# ---------------------------------------------------------------------------
# Constants & Allowed Inputs
# ---------------------------------------------------------------------------

ALLOWED_CONTROLLABLE_INPUTS: Final[set[str]] = {
    "insured",
    "irrigation",
    "supplementary_irrigation",
}

ALLOWED_IRRIGATION_VALUES: Final[set[str]] = {
    "rainfed",
    "tube_well",
    "canal",
    "drip",
    "sprinkler",
}

DISCLAIMER_WHAT_IF: Final[str] = (
    "Model-based sensitivity estimate only, not proof of causation (Rule 6). "
    "What-if simulations project prospective score and limit changes under "
    "hypothetical interventions. Final credit terms and verification rest "
    "exclusively with the bank loan officer."
)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class WhatIfResult(BaseModel):
    """Structured result of a what-if simulation experiment."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "invalid_input"]
    assessment_id: int | None = Field(
        default=None,
        description="Optional database assessment foreign key if linked to persisted record.",
    )
    plot_code: str
    season: str
    changed_input: str
    old_value: str
    new_value: str
    old_score: int
    new_score: int
    score_delta: int = Field(description="new_score - old_score (negative means lower risk).")
    old_band: Literal["low", "medium", "high"]
    new_band: Literal["low", "medium", "high"]
    old_limit_band: LimitBand | None = None
    new_limit_band: LimitBand | None = None
    estimate_label: Literal["estimate"] = Field(
        default="estimate",
        description="Mandatory label explicitly marking output as an estimate per Rule 6.",
    )
    rationale: str
    disclaimer: str = DISCLAIMER_WHAT_IF
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Simulation Engine
# ---------------------------------------------------------------------------


def simulate_what_if(
    baseline_row: Mapping[str, Any] | pd.Series,
    changed_input: str,
    new_value: Any,
    *,
    scorer: Literal["rules_baseline", "logreg"] = "rules_baseline",
    area_acre: float = 2.5,
    crop: str = "wheat",
    assessment_id: int | None = None,
) -> WhatIfResult:
    """Run a deterministic what-if sensitivity simulation for a single controllable input.

    Args:
        baseline_row: Feature row for the plot-season.
        changed_input: Controllable variable name to alter
                       ('insured', 'irrigation', or 'supplementary_irrigation').
        new_value: New target value for the variable.
        scorer: Active risk scorer ('rules_baseline' default).
        area_acre: Farm operational area in acres.
        crop: Crop cultivated.
        assessment_id: Optional ID of the parent assessment record.

    Returns:
        Immutable WhatIfResult detailing old vs new score, band, limit band, and rationale.

    Raises:
        ValueError: If changed_input is not in the allowed controllable set, or if
                    new_value is invalid for the variable.
    """
    row_dict = (
        dict(baseline_row.items()) if isinstance(baseline_row, pd.Series) else dict(baseline_row)
    )
    plot_code = str(row_dict.get("plot_code", "UNKNOWN_PLOT"))
    season = str(row_dict.get("season", "UNKNOWN_SEASON"))

    # 1. Validate controllable input parameter
    norm_input = changed_input.strip().lower()
    if norm_input not in ALLOWED_CONTROLLABLE_INPUTS:
        raise ValueError(
            f"Invalid controllable input '{changed_input}'. "
            f"Allowed inputs for what-if simulation: {sorted(ALLOWED_CONTROLLABLE_INPUTS)}. "
            "Historical satellite, weather, and yield metrics cannot be modified."
        )

    # 2. Evaluate Baseline State
    old_score_res = score_plot_season(row_dict, scorer=scorer)
    if old_score_res.status == "insufficient_data" or old_score_res.score is None:
        raise ValueError(
            f"Cannot run what-if simulation: baseline plot-season has insufficient data "
            f"({old_score_res.insufficient_data_reason})."
        )

    old_score = old_score_res.score
    old_band = old_score_res.band or map_score_to_band(old_score)
    old_irrigation = str(row_dict.get("irrigation", "unknown"))
    old_insured = bool(row_dict.get("insured", 0))

    old_loan_res = generate_loan_suggestion(
        old_score_res,
        area_acre=area_acre,
        crop=crop,
        irrigation=old_irrigation,
        insured=old_insured,
    )
    old_limit_band = old_loan_res.limit_band

    # 3. Apply Simulated Intervention to Clone Row
    simulated_row = dict(row_dict)
    rationale_parts: list[str] = []

    if norm_input == "insured":
        old_val_str = "1" if old_insured else "0"
        # Parse new boolean/int value
        if isinstance(new_value, (bool, int)):
            new_insured = bool(new_value)
        else:
            new_insured = str(new_value).strip().lower() in ("1", "true", "yes", "y", "insured")

        new_val_str = "1" if new_insured else "0"
        simulated_row["insured"] = 1 if new_insured else 0

        if new_insured and not old_insured:
            # Crop insurance indemnification buffers credit default
            rationale_parts.append(
                "Enrolling in PMFBY crop insurance provides financial indemnification against "
                "extreme yield loss, lowering credit default exposure and removing mandatory "
                "insurance flags for loan disbursal."
            )
        elif not new_insured and old_insured:
            rationale_parts.append(
                "Simulating cancellation of crop insurance increases credit default risk "
                "under adverse weather anomalies."
            )
        else:
            rationale_parts.append(f"Insurance status unchanged ({new_val_str}).")

    elif norm_input == "irrigation":
        old_val_str = old_irrigation
        new_irr = str(new_value).strip().lower()
        if new_irr not in ALLOWED_IRRIGATION_VALUES:
            raise ValueError(
                f"Invalid irrigation value '{new_value}'. "
                f"Allowed values: {sorted(ALLOWED_IRRIGATION_VALUES)}."
            )
        new_val_str = new_irr
        simulated_row["irrigation"] = new_irr

        if old_val_str == "rainfed" and new_irr in ("tube_well", "canal", "drip"):
            # Upgrading from rainfed to assured irrigation buffers moisture deficit
            simulated_row["rain_pre_cutoff_deficit_pct"] = max(
                float(simulated_row.get("rain_pre_cutoff_deficit_pct", 0.0) or 0.0),
                -10.0,  # Assured irrigation buffers deficit to safe zone
            )
            rationale_parts.append(
                f"Upgrading from rainfed to assured {new_irr} irrigation buffers the crop "
                "against winter rainfall deficits and increases the eligible Scale of Finance."
            )
        elif old_val_str != "rainfed" and new_irr == "rainfed":
            rationale_parts.append(
                "Simulating rainfed condition removes assured water supply, elevating moisture "
                "stress vulnerability and lowering the base Scale of Finance."
            )
        else:
            rationale_parts.append(f"Transitioning irrigation from {old_val_str} to {new_val_str}.")

    elif norm_input == "supplementary_irrigation":
        old_deficit = float(row_dict.get("rain_pre_cutoff_deficit_pct", 0.0) or 0.0)
        old_val_str = f"{old_deficit:0.1f}% deficit"
        is_active = str(new_value).strip().lower() in ("1", "true", "yes", "applied", "buffer")
        new_val_str = "applied" if is_active else "none"

        if is_active:
            # Applying 1-2 protective irrigations eliminates winter moisture deficit
            simulated_row["rain_pre_cutoff_deficit_pct"] = 0.0
            rationale_parts.append(
                "Applying 1–2 supplementary protective irrigations during dry winter periods "
                f"buffers moisture deficit (from {old_deficit:0.1f}% to 0.0%), "
                "mitigating vegetative drag."
            )
        else:
            rationale_parts.append("No supplementary irrigation applied.")

    else:
        raise ValueError(f"Unhandled input: {norm_input}")

    # 4. Re-score Simulated Plot
    sim_score_res = score_plot_season(simulated_row, scorer=scorer)
    raw_new_score = sim_score_res.score if sim_score_res.score is not None else old_score

    # For insurance intervention under rules_baseline:
    # Adding PMFBY insurance applies a 10-point protective reduction in repayment risk score
    if norm_input == "insured":
        if bool(simulated_row["insured"]) and not old_insured:
            raw_new_score = max(0, raw_new_score - 10)
        elif not bool(simulated_row["insured"]) and old_insured:
            raw_new_score = min(100, raw_new_score + 10)

    new_score = int(round(raw_new_score))
    new_band = map_score_to_band(new_score)
    score_delta = new_score - old_score

    # 5. Re-run Loan Suggestion on Simulated State
    sim_irrigation = str(simulated_row.get("irrigation", old_irrigation))
    sim_insured = bool(simulated_row.get("insured", old_insured))

    # Construct synthesized simulated score result
    synthesized_score_res = RiskScoreResult(
        status="ok",
        plot_code=plot_code,
        season=season,
        scorer=scorer,
        model_version=f"{old_score_res.model_version}-whatif",
        cutoff_date=old_score_res.cutoff_date,
        score=new_score,
        band=new_band,
        reasons=sim_score_res.reasons,
        protective_factor=(
            "Crop insurance (PMFBY)" if sim_insured else sim_score_res.protective_factor
        ),
        data_warnings=[],
        insufficient_data_reason=None,
    )

    new_loan_res = generate_loan_suggestion(
        synthesized_score_res,
        area_acre=area_acre,
        crop=crop,
        irrigation=sim_irrigation,
        insured=sim_insured,
    )
    new_limit_band = new_loan_res.limit_band

    notes: list[str] = [
        f"Simulated parameter: {changed_input} ({old_val_str} -> {new_val_str})",
        (
            f"Prospective score transition: {old_score} ({old_band}) -> "
            f"{new_score} ({new_band}) [delta: {score_delta:+d}]"
        ),
    ]

    if new_band != old_band:
        notes.append(f"Risk tier shifted from {old_band.upper()} to {new_band.upper()}.")

    if old_limit_band and new_limit_band:
        limit_delta_max = new_limit_band.max_amount_inr - old_limit_band.max_amount_inr
        if limit_delta_max != 0:
            notes.append(
                f"Suggested max loan limit adjusted by {limit_delta_max:+d} INR "
                f"(₹{old_limit_band.max_amount_inr:,} -> ₹{new_limit_band.max_amount_inr:,})."
            )

    return WhatIfResult(
        status="ok",
        assessment_id=assessment_id,
        plot_code=plot_code,
        season=season,
        changed_input=norm_input,
        old_value=old_val_str,
        new_value=new_val_str,
        old_score=old_score,
        new_score=new_score,
        score_delta=score_delta,
        old_band=old_band,
        new_band=new_band,
        old_limit_band=old_limit_band,
        new_limit_band=new_limit_band,
        estimate_label="estimate",
        rationale=" ".join(rationale_parts),
        notes=notes,
    )
