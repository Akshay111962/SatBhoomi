"""Calamity relief evidence report routes (blueprint section 8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath
from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.api.mock_data import MOCK_RELIEF_REPORTS, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    enforce_farmer_consent,
    get_mock_status,
    require_officer,
    standard_error_response,
)
from satbhoomi.api.schemas.common import ErrorResponse, ResponseMeta
from satbhoomi.api.schemas.relief import ReliefReportResponse
from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_features import PlotSeasonFeatures
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db

router = APIRouter(tags=["Relief"])

RELIEF_DISCLAIMER = (
    "Official crop loss assessment and calamity declaration remain strictly with "
    "government and bank relief committees. This evidence report is for decision support only."
)


@router.get(
    "/plots/{id}/relief-report",
    response_model=ReliefReportResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Consent required or forbidden"},
        404: {"model": ErrorResponse, "description": "Plot not found"},
    },
)
def get_relief_report(
    id: int = FPath(..., description="Target plot identifier"),
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Generate evidence report supporting restructuring under RBI 33% relief rules."""
    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    # 1. Mock mode branch
    if get_mock_status():
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
            disclaimer=RELIEF_DISCLAIMER,
            meta=SYNTHETIC_META,
        )

    # 2. Real database mode branch
    plot = db.get(Plot, id)
    if not plot or getattr(plot, "status", "active") != "active":
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Plot with id {id} not found or inactive",
            field="id",
        )

    enforce_farmer_consent(db, plot.farmer_id)

    # Look up latest features for plot
    psf_stmt = (
        select(PlotSeasonFeatures)
        .where(PlotSeasonFeatures.plot_id == plot.id)
        .order_by(PlotSeasonFeatures.season.desc())
    )
    psf = db.execute(psf_stmt).scalars().first()

    base_ndvi = 0.65
    curr_ndvi = 0.60
    drop_pct = 7.7
    exceeds_33 = False
    loss_band = "< 33% normal"

    if psf and isinstance(psf.features, dict):
        base_ndvi = float(psf.features.get("mean_ndvi_prior") or 0.65)
        curr_ndvi = float(psf.features.get("mean_ndvi") or 0.60)
        if base_ndvi > 0:
            drop_pct = max(0.0, round(((base_ndvi - curr_ndvi) / base_ndvi) * 100, 1))
        exceeds_33 = drop_pct >= 33.0
        loss_band = ">= 33% calamity candidate" if exceeds_33 else "< 33% normal"

    season_val = psf.season if psf else "2024-25"
    plot_code_val = plot.plot_code or f"PLOT-{plot.id:03d}"

    write_audit_log(
        db=db,
        user_id=current_user.id,
        event="relief_report_read",
        entity="plot",
        entity_id=plot.id,
    )
    db.commit()

    return ReliefReportResponse(
        plot_id=plot.id,
        plot_code=plot_code_val,
        season=season_val,
        baseline_ndvi_mean=base_ndvi,
        current_ndvi_mean=curr_ndvi,
        ndvi_drop_pct=drop_pct,
        estimated_loss_band=loss_band,
        exceeds_rbi_33_threshold=exceeds_33,
        supporting_evidence_summary=(f"Screening departure of {drop_pct}% vs historical baseline."),
        disclaimer=RELIEF_DISCLAIMER,
        meta=ResponseMeta(
            timestamp=None,
            synthetic=(getattr(plot.farmer, "data_origin", "synthetic") == "synthetic"),
            version="0.6.0",
        ),
    )
