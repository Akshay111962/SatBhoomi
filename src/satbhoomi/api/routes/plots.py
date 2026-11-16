"""Plot registration and retrieval routes (blueprint section 8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from satbhoomi.api.mock_data import MOCK_PLOTS, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    require_officer,
    standard_error_response,
)
from satbhoomi.api.schemas.common import ErrorResponse, ResponseMeta
from satbhoomi.api.schemas.plots import PlotCreateRequest, PlotListResponse, PlotResponse
from satbhoomi.config.settings import get_settings
from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.farmer import Farmer
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db

router = APIRouter(prefix="/plots", tags=["Plots"])


@router.post(
    "",
    response_model=PlotResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Real farmer data disallowed"},
    },
)
def create_plot(
    payload: PlotCreateRequest,
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Create a new agricultural plot record for risk assessment."""
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

    # 1. Mock mode branch
    if get_mock_status():
        new_id = len(MOCK_PLOTS) + 1
        return PlotResponse(
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

    # 2. Real database mode branch
    farmer = db.get(Farmer, payload.farmer_id)
    if farmer is None:
        farmer = Farmer(
            display_name=f"Farmer-{payload.farmer_id:03d}",
            village=payload.village,
            district=payload.district,
            data_origin="synthetic",
        )
        db.add(farmer)
        db.flush()

    if farmer.data_origin == "real" and not get_settings().allow_real_data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "REAL_DATA_DISALLOWED",
                "message": "Real farmer data processing is disabled by system policy",
                "field": None,
            },
        )

    plot_count = db.query(Plot).count()
    plot = Plot(
        plot_code=f"PLOT-{plot_count + 1:03d}",
        farmer_id=farmer.id,
        crop=payload.crop,
        area_acre=payload.area_acre,
        lat=payload.lat,
        lon=payload.lon,
        geometry=payload.geometry,
        irrigation=payload.irrigation,
        insured=payload.insured,
    )
    db.add(plot)
    db.flush()

    write_audit_log(
        db=db,
        user_id=current_user.id,
        event="plot_created",
        entity="plot",
        entity_id=plot.id,
    )
    db.commit()

    return PlotResponse(
        id=plot.id,
        plot_code=plot.plot_code or f"PLOT-{plot.id:03d}",
        farmer_id=farmer.id,
        farmer_display_name=farmer.display_name,
        district=farmer.district,
        village=farmer.village,
        crop=plot.crop,
        area_acre=plot.area_acre,
        lat=plot.lat,
        lon=plot.lon,
        irrigation=plot.irrigation,
        insured=plot.insured,
        created_at=plot.created_at.isoformat(),
        meta=ResponseMeta(
            timestamp=plot.created_at,
            synthetic=(farmer.data_origin == "synthetic"),
            version="0.6.0",
        ),
    )


@router.get(
    "",
    response_model=PlotListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
)
def list_plots(
    limit: int = Query(default=10, ge=1, le=100, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    district: str | None = Query(default=None, description="Filter by district name"),
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """List agricultural plots with pagination and optional district filter."""
    err = check_mock_error_triggers(x_mock_error)
    if err:
        return err

    if get_mock_status():
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

    stmt = select(Plot).join(Farmer, Plot.farmer_id == Farmer.id)
    if district:
        stmt = stmt.where(Farmer.district.ilike(district))

    total = (
        db.scalar(
            select(func.count(Plot.id)).select_from(Plot).join(Farmer, Plot.farmer_id == Farmer.id)
        )
        if not district
        else len(db.execute(stmt).scalars().all())
    )
    plots = db.execute(stmt.offset(offset).limit(limit)).scalars().all()

    items = [
        PlotResponse(
            id=p.id,
            plot_code=p.plot_code or f"PLOT-{p.id:03d}",
            farmer_id=p.farmer_id,
            farmer_display_name=p.farmer.display_name if p.farmer else f"Farmer-{p.farmer_id:03d}",
            district=p.farmer.district if p.farmer else "Anand",
            village=p.farmer.village if p.farmer else "Boriavi",
            crop=p.crop,
            area_acre=p.area_acre,
            lat=p.lat,
            lon=p.lon,
            irrigation=p.irrigation,
            insured=p.insured,
            created_at=p.created_at.isoformat(),
            meta=ResponseMeta(
                timestamp=p.created_at,
                synthetic=True,
                version="0.6.0",
            ),
        )
        for p in plots
    ]

    return PlotListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        meta=ResponseMeta(
            timestamp=None,
            synthetic=True,
            version="0.6.0",
        ),
    )
