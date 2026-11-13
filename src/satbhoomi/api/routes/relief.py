"""[DRAFT] Calamity relief evidence report routes (blueprint section 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath

from satbhoomi.api.mock_data import MOCK_RELIEF_REPORTS, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    not_implemented_response,
    standard_error_response,
    verify_mock_auth,
)
from satbhoomi.api.schemas.common import ErrorResponse
from satbhoomi.api.schemas.relief import ReliefReportResponse

router = APIRouter(tags=["Relief"])


@router.get(
    "/plots/{id}/relief-report",
    response_model=ReliefReportResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Plot not found"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def get_relief_report(
    id: int = FPath(..., description="Target plot identifier"),
    token: str = Depends(verify_mock_auth),
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """[DRAFT] Generate evidence report supporting restructuring under RBI 33% relief rules."""
    if not get_mock_status():
        return not_implemented_response()

    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    if id in MOCK_RELIEF_REPORTS:
        return MOCK_RELIEF_REPORTS[id]

    if id > 5:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Plot with id {id} not found",
            field="id",
        )

    return ReliefReportResponse(
        plot_id=id,
        plot_code=f"PLOT-{id:03d}",
        season="2024-25",
        baseline_ndvi_mean=0.70,
        current_ndvi_mean=0.68,
        ndvi_drop_pct=2.8,
        estimated_loss_band="< 33% normal",
        exceeds_rbi_33_threshold=False,
        supporting_evidence_summary=(
            "Normal vegetative health sustained; no severe crop calamity evidence."
        ),
        disclaimer=(
            "Official crop loss assessment and calamity declaration remain strictly with "
            "government and bank relief committees. This evidence report is for decision "
            "support only."
        ),
        meta=SYNTHETIC_META,
    )
