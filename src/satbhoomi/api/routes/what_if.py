"""[STABLE] What-if simulator route (blueprint section 8).

Matches the real WhatIfResult structure from Task T-08.
Rule 6 Compliance: Every simulation output must carry estimate_label='estimate'
and the causation disclaimer.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath

from satbhoomi.api.mock_data import MOCK_ASSESSMENTS, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    not_implemented_response,
    standard_error_response,
    verify_mock_auth,
)
from satbhoomi.api.schemas.common import ErrorResponse
from satbhoomi.api.schemas.what_if import WhatIfRequest, WhatIfResponse
from satbhoomi.risk.loan_suggestions import LimitBand
from satbhoomi.risk.scoring import FIXED_RELIABILITY_NOTE
from satbhoomi.risk.what_if import DISCLAIMER_WHAT_IF

router = APIRouter(tags=["What-If"])


@router.post(
    "/assessments/{id}/what-if",
    response_model=WhatIfResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error on input parameter"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Assessment not found"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def run_what_if(
    id: int = FPath(..., description="Target assessment ID to simulate from"),
    payload: WhatIfRequest = ...,
    token: str = Depends(verify_mock_auth),
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """[STABLE] Simulate prospective risk score changes under a controllable mitigation (T-08)."""
    if not get_mock_status():
        return not_implemented_response()

    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    if id not in MOCK_ASSESSMENTS:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Assessment with id {id} not found",
            field="id",
        )

    base = MOCK_ASSESSMENTS[id]
    orig_score = base.score or 50
    orig_band = base.band or "medium"
    orig_limit = base.loan_suggestion.limit_band if base.loan_suggestion else None

    # Calculate realistic synthetic simulation parameters
    effect_basis: Literal["scorer_input", "scenario_assumption", "not_modelled"]
    assumption: str | None = None

    if payload.changed_input == "insured":
        if payload.new_value in ("1", "true", "True"):
            sim_score = max(0, orig_score - 10)
            old_val = "0"
            effect_basis = "scorer_input"
            rationale = (
                "Enrolling in PMFBY crop insurance provides financial buffering against "
                "yield drag, reducing prospective credit risk."
            )
        else:
            sim_score = orig_score
            old_val = "1"
            effect_basis = "not_modelled"
            rationale = "No risk reduction simulated for uninsuring crop."

    elif payload.changed_input == "irrigation":
        old_val = "rainfed"
        if payload.new_value in ("tube_well", "canal"):
            sim_score = max(0, orig_score - 30)
            effect_basis = "scorer_input"
            rationale = (
                "Switching to assured irrigation directly removes rainfall deficit penalties "
                "in the active agronomic baseline model."
            )
        else:
            sim_score = orig_score
            effect_basis = "not_modelled"
            rationale = "Target irrigation value is identical or unmodelled."

    elif payload.changed_input == "supplementary_irrigation":
        old_val = "0"
        if payload.new_value in ("1", "true", "True"):
            sim_score = max(0, orig_score - 15)
            effect_basis = "scenario_assumption"
            assumption = (
                "Supplementary irrigation assumes assured secondary water application "
                "during flowering/grain-filling stages."
            )
            rationale = (
                "Under the scenario assumption of secondary critical-stage watering, "
                "mid-season vegetation drag is partially mitigated."
            )
        else:
            sim_score = orig_score
            effect_basis = "not_modelled"
            rationale = "Supplementary irrigation flag set to inactive; zero delta modelled."

    else:
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_SIMULATION_INPUT",
            message=f"Simulation not allowed on input '{payload.changed_input}'",
            field="changed_input",
        )

    sim_band = "low" if sim_score <= 34 else "medium" if sim_score <= 69 else "high"

    # Simulate updated limit band if baseline exists
    if orig_limit:
        if sim_band == "low":
            new_min = int(orig_limit.gross_scale_limit_inr * 0.90)
            new_max = int(orig_limit.gross_scale_limit_inr * 1.00)
            new_haircut = "0%–10%"
        elif sim_band == "medium":
            new_min = int(orig_limit.gross_scale_limit_inr * 0.65)
            new_max = int(orig_limit.gross_scale_limit_inr * 0.80)
            new_haircut = "20%–35%"
        else:
            new_min = int(orig_limit.gross_scale_limit_inr * 0.40)
            new_max = int(orig_limit.gross_scale_limit_inr * 0.50)
            new_haircut = "50%–60%"

        if orig_limit.collateral_free_cap_applied:
            new_max = min(new_max, 200000)
            new_min = min(new_min, 160000)

        sim_limit_band = LimitBand(
            min_amount_inr=new_min,
            max_amount_inr=new_max,
            scale_of_finance_per_acre_inr=orig_limit.scale_of_finance_per_acre_inr,
            gross_scale_limit_inr=orig_limit.gross_scale_limit_inr,
            collateral_free_cap_applied=orig_limit.collateral_free_cap_applied,
            haircut_percentage_range=new_haircut,
        )
    else:
        sim_limit_band = None

    return WhatIfResponse(
        status="ok",
        assessment_id=id,
        plot_id=base.plot_id,
        plot_code=base.plot_code,
        season=base.season,
        changed_input=payload.changed_input,
        old_value=old_val,
        new_value=payload.new_value,
        old_score=orig_score,
        new_score=sim_score,
        score_delta=sim_score - orig_score,
        old_band=orig_band,
        new_band=sim_band,
        old_limit_band=orig_limit,
        new_limit_band=sim_limit_band,
        estimate_label="estimate",
        effect_basis=effect_basis,
        assumption=assumption,
        rationale=rationale,
        disclaimer=DISCLAIMER_WHAT_IF,
        reliability_note=FIXED_RELIABILITY_NOTE,
        notes=["Synthetic simulation computed deterministically for mock mode."],
        meta=SYNTHETIC_META,
    )
