"""[DRAFT] What-if simulator route (blueprint section 8)."""

from __future__ import annotations

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
    """[DRAFT] Simulate prospective risk score changes under a controllable mitigation."""
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

    # Calculate realistic synthetic simulation
    if payload.changed_input == "insured":
        sim_score = max(0, orig_score - 10)
        old_val = "0"
    elif payload.changed_input in ("irrigation", "supplementary_irrigation"):
        sim_score = max(0, orig_score - 30)
        old_val = "rainfed"
    else:
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_SIMULATION_INPUT",
            message=f"Simulation not allowed on input '{payload.changed_input}'",
            field="changed_input",
        )

    sim_band = "low" if sim_score <= 34 else "medium" if sim_score <= 69 else "high"

    return WhatIfResponse(
        assessment_id=id,
        plot_id=base.plot_id,
        changed_input=payload.changed_input,
        old_value=old_val,
        new_value=payload.new_value,
        original_score=orig_score,
        simulated_score=sim_score,
        original_band=base.band,
        simulated_band=sim_band,
        score_delta=sim_score - orig_score,
        estimate_label="estimate",
        causation_disclaimer=(
            "What-if simulations show model sensitivity under prospective mitigations; "
            "they do not prove causation or guarantee crop outcomes."
        ),
        meta=SYNTHETIC_META,
    )
