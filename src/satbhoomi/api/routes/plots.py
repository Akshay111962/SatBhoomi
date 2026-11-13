"""Plot registration and retrieval routes (blueprint section 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response, status

from satbhoomi.api.mock_data import MOCK_PLOTS, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    not_implemented_response,
    standard_error_response,
    verify_mock_auth,
)
from satbhoomi.api.schemas.common import ErrorResponse
from satbhoomi.api.schemas.plots import PlotCreateRequest, PlotListResponse, PlotResponse

router = APIRouter(prefix="/plots", tags=["Plots"])


@router.post(
    "",
    response_model=PlotResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def create_plot(
    payload: PlotCreateRequest,
    token: str = Depends(verify_mock_auth),
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Create a new agricultural plot record for risk assessment."""
    if not get_mock_status():
        return not_implemented_response()

    err = check_mock_error_triggers(x_mock_error)
    if err:
        return err

    if payload.area_acre <= 0:
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="VALIDATION_ERROR",
            message="area_acre must be above 0",
            field="area_acre",
        )

    # Return newly created synthetic plot
    new_id = len(MOCK_PLOTS) + 1
    new_plot = PlotResponse(
        id=new_id,
        plot_code=f"PLOT-{new_id:03d}",
        farmer_id=payload.farmer_id,
        farmer_display_name=f"Farmer-{payload.farmer_id:03d}",
        district=payload.district,
        village=payload.village,
        crop=payload.crop,
        area_acre=payload.area_acre,
        lat=payload.lat,
        lon=payload.lon,
        irrigation=payload.irrigation,
        insured=payload.insured,
        created_at="2026-11-13T10:00:00Z",
        meta=SYNTHETIC_META,
    )
    return new_plot


@router.get(
    "",
    response_model=PlotListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def list_plots(
    limit: int = Query(default=10, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    district: str | None = Query(default=None, description="Filter by district name"),
    token: str = Depends(verify_mock_auth),
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """List agricultural plots with pagination and optional district filter."""
    if not get_mock_status():
        return not_implemented_response()

    err = check_mock_error_triggers(x_mock_error)
    if err:
        return err

    plots = MOCK_PLOTS
    if district:
        plots = [p for p in plots if p.district.lower() == district.lower()]

    total = len(plots)
    paginated = plots[offset : offset + limit]

    return PlotListResponse(
        items=paginated,
        total=total,
        limit=limit,
        offset=offset,
        meta=SYNTHETIC_META,
    )
