"""[STABLE] What-if simulator route (blueprint section 8).

Matches the real WhatIfResult structure from Task T-08.
Rule 6 Compliance: Every simulation output must carry estimate_label='estimate'
and the causation disclaimer.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.api.adapters import adapt_what_if_to_response
from satbhoomi.api.mock_data import MOCK_ASSESSMENTS, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    require_officer,
    standard_error_response,
)
from satbhoomi.api.schemas.common import ErrorResponse
from satbhoomi.api.schemas.what_if import WhatIfRequest, WhatIfResponse
from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.assessment import Assessment
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_features import PlotSeasonFeatures
from satbhoomi.db.models.user import User
from satbhoomi.db.models.what_if import WhatIf
from satbhoomi.db.session import get_db
from satbhoomi.risk.loan_suggestions import LimitBand
from satbhoomi.risk.scoring import FIXED_RELIABILITY_NOTE
from satbhoomi.risk.what_if import (
    ALLOWED_IRRIGATION_VALUES,
    DISCLAIMER_WHAT_IF,
    simulate_what_if,
)

router = APIRouter(tags=["What-If"])

FORBIDDEN_LABEL_FIELDS: frozenset[str] = frozenset(
    {
        "stressed",
        "label_unavailable",
        "peak_drop_pct",
        "historical_baseline_ndvi",
    }
)

ALLOWED_WHAT_IF_INPUTS: frozenset[str] = frozenset({"insured", "irrigation"})
ALLOWED_INSURED_VALUES: frozenset[str] = frozenset({"0", "1", "true", "false"})


@router.post(
    "/assessments/{id}/what-if",
    response_model=WhatIfResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error on input parameter"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Assessment not found"},
    },
)
def run_what_if(
    id: int = FPath(..., description="Target assessment ID to simulate from"),
    payload: WhatIfRequest = ...,
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Simulate prospective risk score changes under a controllable mitigation (T-08)."""
    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    # 1. Mock mode branch for synthetic development
    if get_mock_status():
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

    # 2. Real mode: Validate allowed changed inputs (strictly insured and irrigation)
    if payload.changed_input not in ALLOWED_WHAT_IF_INPUTS:
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message=(
                f"Invalid changed_input '{payload.changed_input}'. "
                f"Allowed inputs for what-if simulation: {sorted(ALLOWED_WHAT_IF_INPUTS)}."
            ),
            field="changed_input",
        )

    # Validate new_value for the selected input
    norm_val = str(payload.new_value).strip().lower()
    if payload.changed_input == "insured":
        if norm_val not in ALLOWED_INSURED_VALUES:
            return standard_error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message=(
                    f"Invalid value '{payload.new_value}' for insured. "
                    f"Allowed values: {sorted(ALLOWED_INSURED_VALUES)}."
                ),
                field="new_value",
            )
    elif payload.changed_input == "irrigation":
        if norm_val not in ALLOWED_IRRIGATION_VALUES:
            return standard_error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message=(
                    f"Invalid value '{payload.new_value}' for irrigation. "
                    f"Allowed values: {sorted(ALLOWED_IRRIGATION_VALUES)}."
                ),
                field="new_value",
            )

    # 3. Load stored Assessment record
    assessment = db.execute(select(Assessment).where(Assessment.id == id)).scalars().one_or_none()
    if not assessment:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Assessment with id {id} not found",
            field="id",
        )

    if assessment.status == "insufficient_data" or assessment.score is None:
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_STATE",
            message="Cannot run what-if simulation on assessment with insufficient data.",
            field="id",
        )

    # 4. Load Plot and PlotSeasonFeatures
    plot = db.execute(select(Plot).where(Plot.id == assessment.plot_id)).scalars().one_or_none()
    if not plot:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Plot for assessment {id} not found",
            field="id",
        )

    psf = (
        db.execute(
            select(PlotSeasonFeatures).where(
                PlotSeasonFeatures.plot_id == plot.id,
                PlotSeasonFeatures.season == assessment.season,
            )
        )
        .scalars()
        .one_or_none()
    )
    if not psf:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=(
                f"Pre-cutoff features for plot {plot.id} and season {assessment.season} not found"
            ),
            field="season",
        )

    # 5. Rebuild baseline scoring input with plot table overlays & enforce label blindness
    scoring_input = dict(psf.features)
    scoring_input["plot_code"] = plot.plot_code or f"PLOT-{plot.id:03d}"
    scoring_input["season"] = psf.season
    scoring_input["crop"] = plot.crop
    scoring_input["area_acre"] = float(plot.area_acre)
    scoring_input["irrigation"] = plot.irrigation
    scoring_input["insured"] = 1 if plot.insured else 0

    for forbidden in FORBIDDEN_LABEL_FIELDS:
        assert forbidden not in scoring_input, (
            f"Forbidden label field '{forbidden}' in what-if input"
        )

    # 6. Execute pure what-if simulation engine
    sim_result = simulate_what_if(
        baseline_row=scoring_input,
        changed_input=payload.changed_input,
        new_value=payload.new_value,
        scorer=assessment.scorer,  # type: ignore[arg-type]
        area_acre=float(plot.area_acre),
        crop=plot.crop,
        assessment_id=assessment.id,
    )

    # Record snapshot of original assessment to verify immutability
    orig_score = assessment.score
    orig_band = assessment.band

    # 7. Persist WhatIf simulation record and audit trail in single transaction
    what_if_entry = WhatIf(
        assessment_id=assessment.id,
        changed_input=sim_result.changed_input,
        old_value=str(sim_result.old_value),
        new_value=str(sim_result.new_value),
        new_score=float(sim_result.new_score),
        result_json=sim_result.model_dump(),
        created_at=datetime.now(UTC),
    )
    db.add(what_if_entry)
    db.flush()

    write_audit_log(
        db=db,
        user_id=current_user.id,
        event="what_if_simulated",
        entity="what_if",
        entity_id=what_if_entry.id,
    )
    db.commit()
    db.refresh(what_if_entry)

    # Invariant: Original assessment row must never be modified
    assert assessment.score == orig_score, "Original assessment score was mutated by what-if run!"
    assert assessment.band == orig_band, "Original assessment band was mutated by what-if run!"

    response_obj = adapt_what_if_to_response(
        sim_result,
        assessment_id=assessment.id,
        plot_id=plot.id,
        synthetic=False,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_obj.model_dump(),
    )
