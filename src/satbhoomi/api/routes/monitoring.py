"""[DRAFT] In-season plot monitoring and timeline routes (blueprint section 8).

Updated in Task T-11C with real historical replay simulation serving.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi import Path as FPath
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.api.mock_data import MOCK_MONITORING, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    enforce_farmer_consent,
    get_mock_status,
    require_officer,
    standard_error_response,
)
from satbhoomi.api.schemas.common import ErrorResponse, ResponseMeta
from satbhoomi.api.schemas.monitoring import AlertSummary, PlotMonitoringResponse, TimelinePoint
from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.alert import Alert
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_timeline import PlotSeasonTimeline
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db

router = APIRouter(tags=["Monitoring"])

REPLAY_NOTE = (
    "Historical season replay; not live in-season monitoring. "
    "Makes no claim of detecting real-world stress events."
)


@router.get(
    "/plots/{id}/monitoring",
    response_model=PlotMonitoringResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Plot not found"},
    },
)
def get_plot_monitoring(
    id: int = FPath(..., description="Target plot identifier"),
    season: str | None = Query(
        default=None, description="Optional cropping season filter (e.g., '2023-24')"
    ),
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Retrieve in-season crop health timeline, rainfall trajectory, and stress alerts."""
    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    # 1. Mock Mode Branch
    if get_mock_status():
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
            season=season or "2024-25",
            status="ok",
            data_gap_reason=None,
            checkpoint_label="January 15",
            evaluation_date="2025-01-15",
            mode="replay",
            replay_note=REPLAY_NOTE,
            timeline=[
                TimelinePoint(date="2024-12-01", ndvi=0.45, rainfall_mm=0.0, data_gap=False),
                TimelinePoint(date="2025-01-01", ndvi=0.65, rainfall_mm=1.0, data_gap=False),
                TimelinePoint(date="2025-01-15", ndvi=0.72, rainfall_mm=0.0, data_gap=False),
            ],
            active_alerts=[],
            meta=SYNTHETIC_META,
        )

    # 2. Real Mode Branch: fetch active Plot
    plot = db.execute(select(Plot).where(Plot.id == id)).scalars().one_or_none()
    if not plot or getattr(plot, "status", "active") != "active":
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Plot with id {id} not found or inactive",
            field="id",
        )

    enforce_farmer_consent(db, plot.farmer_id)

    # Determine target season: requested season, or latest season with stored timeline
    if season:
        target_season = season
        pst = (
            db.execute(
                select(PlotSeasonTimeline).where(
                    PlotSeasonTimeline.plot_id == plot.id,
                    PlotSeasonTimeline.season == target_season,
                )
            )
            .scalars()
            .first()
        )
    else:
        pst = (
            db.execute(
                select(PlotSeasonTimeline)
                .where(PlotSeasonTimeline.plot_id == plot.id)
                .order_by(PlotSeasonTimeline.season.desc())
            )
            .scalars()
            .first()
        )
        target_season = pst.season if pst else "2024-25"

    plot_code = plot.plot_code or f"PLOT-{plot.id:03d}"

    # Build timeline points
    timeline_pts: list[TimelinePoint] = []
    checkpoint_label: str | None = None
    evaluation_date: str | None = None
    status_label = "ok"
    data_gap_summary: str | None = None

    if pst and pst.timeline_json:
        for pt in pst.timeline_json:
            timeline_pts.append(
                TimelinePoint(
                    date=pt.get("date", ""),
                    ndvi=pt.get("ndvi"),
                    rainfall_mm=pt.get("rainfall_mm"),
                    data_gap=bool(pt.get("data_gap", False)),
                )
            )
        last_pt = pst.timeline_json[-1]
        checkpoint_label = last_pt.get("checkpoint_label")
        evaluation_date = last_pt.get("date")

        if pst.data_gaps_json:
            status_label = "data_gap"
            data_gap_summary = "; ".join(
                g.get("reason", "") for g in pst.data_gaps_json if g.get("reason")
            )

    # Fetch alerts for this plot and season
    alerts = (
        db.execute(
            select(Alert)
            .where(Alert.plot_id == plot.id, Alert.season == target_season)
            .order_by(Alert.detected_on.asc())
        )
        .scalars()
        .all()
    )

    active_summaries: list[AlertSummary] = []
    past_summaries: list[AlertSummary] = []

    for al in alerts:
        det_date_str = (
            al.detected_on.date().isoformat()
            if hasattr(al.detected_on, "date")
            else str(al.detected_on)[:10]
        )
        summary = AlertSummary(
            id=al.id,
            plot_code=plot_code,
            season=al.season,
            checkpoint_label=al.checkpoint_label or "Jan 31",
            detected_on=det_date_str,
            type=al.type,  # type: ignore[arg-type]
            severity=al.severity,  # type: ignore[arg-type]
            status=al.status,  # type: ignore[arg-type]
            headline=al.headline or f"In-season {al.type} detected",
            detail=al.detail or "Vegetation or rainfall drag observed.",
            supportive_action=al.supportive_action or "Schedule supportive field review.",
            data_gap_warning=al.data_gap_warning,
            is_replay=al.is_replay,
        )
        if al.status in ("open", "acknowledged", "in_progress"):
            active_summaries.append(summary)
        else:
            past_summaries.append(summary)

    resp_meta = ResponseMeta(
        timestamp=pst.imported_at if pst else None,
        synthetic=False,
        version="0.4.0",
    )

    response_payload = PlotMonitoringResponse(
        plot_id=plot.id,
        plot_code=plot_code,
        season=target_season,
        status=status_label,  # type: ignore[arg-type]
        data_gap_reason=data_gap_summary,
        checkpoint_label=checkpoint_label,
        evaluation_date=evaluation_date,
        mode="replay",
        replay_note=REPLAY_NOTE,
        timeline=timeline_pts,
        active_alerts=active_summaries,
        past_alerts=past_summaries,
        meta=resp_meta,
    )

    write_audit_log(
        db=db,
        user_id=current_user.id,
        event="monitoring_read",
        entity="plot",
        entity_id=plot.id,
    )
    db.commit()

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_payload.model_dump(mode="json"),
    )
