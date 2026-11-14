"""[STABLE] In-season plot monitoring and timeline routes (blueprint section 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath

from satbhoomi.api.mock_data import MOCK_MONITORING, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    not_implemented_response,
    standard_error_response,
    verify_mock_auth,
)
from satbhoomi.api.schemas.common import ErrorResponse
from satbhoomi.api.schemas.monitoring import PlotMonitoringResponse, TimelinePoint

router = APIRouter(tags=["Monitoring"])


@router.get(
    "/plots/{id}/monitoring",
    response_model=PlotMonitoringResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Plot not found"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def get_plot_monitoring(
    id: int = FPath(..., description="Target plot identifier"),
    token: str = Depends(verify_mock_auth),
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """[DRAFT] Retrieve in-season crop health timeline, rainfall trajectory, and active alerts."""
    if not get_mock_status():
        return not_implemented_response()

    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    if id in MOCK_MONITORING:
        return MOCK_MONITORING[id]

    if id > 5:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Monitoring data for plot {id} not found",
            field="id",
        )

    # Generic fallback mock for other plots
    return PlotMonitoringResponse(
        plot_id=id,
        plot_code=f"PLOT-{id:03d}",
        season="2024-25",
        status="ok",
        data_gap_reason=None,
        checkpoint_label="January 15",
        evaluation_date="2025-01-15",
        timeline=[
            TimelinePoint(date="2024-12-01", ndvi=0.45, rainfall_mm=0.0, data_gap=False),
            TimelinePoint(date="2025-01-01", ndvi=0.65, rainfall_mm=1.0, data_gap=False),
            TimelinePoint(date="2025-01-15", ndvi=0.72, rainfall_mm=0.0, data_gap=False),
        ],
        active_alerts=[],
        meta=SYNTHETIC_META,
    )
