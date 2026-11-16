"""Assessment execution and retrieval routes (blueprint section 8)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.api.adapters import adapt_stored_assessment_to_response
from satbhoomi.api.mock_data import MOCK_ASSESSMENTS
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    enforce_farmer_consent,
    get_mock_status,
    require_officer,
    standard_error_response,
)
from satbhoomi.api.schemas.assessments import AssessmentCreateRequest, AssessmentResponse
from satbhoomi.api.schemas.common import ErrorResponse
from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.assessment import Assessment
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_features import PlotSeasonFeatures
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db
from satbhoomi.risk.loan_suggestions import generate_loan_suggestion
from satbhoomi.risk.scoring import score_plot_season

router = APIRouter(tags=["Assessments"])

FORBIDDEN_LABEL_FIELDS: frozenset[str] = frozenset(
    {
        "stressed",
        "label_unavailable",
        "peak_drop_pct",
        "historical_baseline_ndvi",
    }
)


@router.post(
    "/plots/{id}/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error or idempotency key reuse"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Plot or stored features not found"},
    },
)
def create_assessment(
    id: int = FPath(..., description="Target plot identifier"),
    payload: AssessmentCreateRequest | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Execute risk assessment for a plot and return deterministic score with reasons."""
    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    # 1. Mock mode fallback for synthetic local workflows
    if get_mock_status():
        if id not in MOCK_ASSESSMENTS:
            return standard_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                code="NOT_FOUND",
                message=f"Plot with id {id} not found",
                field="id",
            )
        return MOCK_ASSESSMENTS[id]

    # 2. Validate Idempotency-Key header length if provided (8 to 64 chars)
    if idempotency_key is not None:
        if len(idempotency_key) < 8 or len(idempotency_key) > 64:
            return standard_error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="VALIDATION_ERROR",
                message="Idempotency-Key header must be between 8 and 64 characters long.",
                field="Idempotency-Key",
            )

    # 3. Retrieve active Plot record (404 if missing or inactive)
    plot = db.execute(select(Plot).where(Plot.id == id)).scalars().one_or_none()
    if not plot or getattr(plot, "status", "active") != "active":
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Plot with id {id} not found or inactive",
            field="id",
        )

    enforce_farmer_consent(db, plot.farmer_id)

    # 4. Retrieve stored pre-cutoff seasonal features (404 if missing)
    if payload is not None and payload.season:
        target_season = payload.season
        psf = (
            db.execute(
                select(PlotSeasonFeatures).where(
                    PlotSeasonFeatures.plot_id == plot.id,
                    PlotSeasonFeatures.season == target_season,
                )
            )
            .scalars()
            .one_or_none()
        )
    else:
        # If no season requested, select latest season with stored features
        psf = (
            db.execute(
                select(PlotSeasonFeatures)
                .where(PlotSeasonFeatures.plot_id == plot.id)
                .order_by(PlotSeasonFeatures.season.desc())
            )
            .scalars()
            .first()
        )
        target_season = psf.season if psf else "latest"

    if not psf:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"No stored features found for plot {id} and season {target_season}",
            field="season",
        )

    # 5. Check Idempotency-Key reuse
    request_hash = hashlib.sha256(f"plot_id={plot.id}|season={psf.season}".encode()).hexdigest()

    if idempotency_key is not None:
        existing = (
            db.execute(
                select(Assessment).where(
                    Assessment.created_by == current_user.id,
                    Assessment.idempotency_key == idempotency_key,
                )
            )
            .scalars()
            .first()
        )
        if existing:
            if existing.plot_id == plot.id and existing.season == psf.season:
                # Same key and identical request: replay existing assessment as 200 OK
                plot_code = plot.plot_code or f"PLOT-{plot.id:03d}"
                replay_response = adapt_stored_assessment_to_response(existing, plot_code=plot_code)
                return JSONResponse(
                    status_code=status.HTTP_200_OK,
                    content=replay_response.model_dump(),
                )
            else:
                # Same key with different plot or season: 400 IDEMPOTENCY_KEY_REUSED
                return standard_error_response(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="IDEMPOTENCY_KEY_REUSED",
                    message=(
                        "Idempotency key has already been used with different request parameters."
                    ),
                    field="Idempotency-Key",
                )

    # 6. Build scoring input with plot table overlays & enforce label blindness
    scoring_input = dict(psf.features)
    scoring_input["plot_code"] = plot.plot_code or f"PLOT-{plot.id:03d}"
    scoring_input["season"] = psf.season
    scoring_input["crop"] = plot.crop
    scoring_input["area_acre"] = float(plot.area_acre)
    scoring_input["irrigation"] = plot.irrigation
    scoring_input["insured"] = 1 if plot.insured else 0

    # Hard invariant: Assert scoring input never contains label fields
    for forbidden in FORBIDDEN_LABEL_FIELDS:
        assert forbidden not in scoring_input, (
            f"Forbidden label field '{forbidden}' in scoring input"
        )

    # 7. Execute pure risk scoring and underwriting suggestions
    score_res = score_plot_season(scoring_input, scorer="rules_baseline")
    loan_res = generate_loan_suggestion(
        score_res,
        area_acre=float(plot.area_acre),
        crop=plot.crop,
        irrigation=plot.irrigation,
        insured=plot.insured,
    )

    keys = (
        score_res.reason_keys
        if score_res.reason_keys and len(score_res.reason_keys) == len(score_res.reasons)
        else ["in_season_agronomic_indicators"] * len(score_res.reasons)
    )
    reasons_list = [
        {"feature_name": k, "text": r} for k, r in zip(keys, score_res.reasons, strict=False)
    ]

    # 8. Store assessment and append-only audit log in single atomic transaction
    new_assessment = Assessment(
        plot_id=plot.id,
        season=psf.season,
        status=score_res.status,
        scorer=score_res.scorer,
        model_version=score_res.model_version,
        score=float(score_res.score) if score_res.score is not None else None,
        band=score_res.band,
        cutoff_date=psf.cutoff_date,
        reasons_json=reasons_list,
        loan_suggestion_json=loan_res.model_dump(),
        data_warnings=list(score_res.data_warnings),
        insufficient_data_reason=score_res.insufficient_data_reason,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        created_by=current_user.id,
        created_at=datetime.now(UTC),
    )
    db.add(new_assessment)
    db.flush()

    write_audit_log(
        db=db,
        user_id=current_user.id,
        event="assessment_created",
        entity="assessment",
        entity_id=new_assessment.id,
    )
    db.commit()
    db.refresh(new_assessment)

    plot_code = plot.plot_code or f"PLOT-{plot.id:03d}"
    created_response = adapt_stored_assessment_to_response(
        new_assessment,
        plot_code=plot_code,
        protective_factor=score_res.protective_factor,
    )
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=created_response.model_dump(),
    )


@router.get(
    "/assessments/{id}",
    response_model=AssessmentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Assessment not found"},
    },
)
def get_assessment(
    id: int = FPath(..., description="Assessment identifier"),
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Retrieve an existing assessment result by ID."""
    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    if get_mock_status():
        if id not in MOCK_ASSESSMENTS:
            return standard_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                code="NOT_FOUND",
                message=f"Assessment with id {id} not found",
                field="id",
            )
        return MOCK_ASSESSMENTS[id]

    assessment = db.execute(select(Assessment).where(Assessment.id == id)).scalars().one_or_none()
    if not assessment:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Assessment with id {id} not found",
            field="id",
        )

    plot = db.execute(select(Plot).where(Plot.id == assessment.plot_id)).scalars().one_or_none()
    plot_code = plot.plot_code if plot and plot.plot_code else f"PLOT-{assessment.plot_id:03d}"

    response_schema = adapt_stored_assessment_to_response(assessment, plot_code=plot_code)
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_schema.model_dump(),
    )
