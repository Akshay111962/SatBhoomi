"""Consent management routes (DPDP Act 2023 compliance)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath
from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    require_officer,
    standard_error_response,
)
from satbhoomi.api.schemas.common import ErrorResponse
from satbhoomi.api.schemas.consent import (
    ALLOWED_CONSENT_PURPOSES,
    ConsentCreateRequest,
    ConsentListResponse,
    ConsentResponse,
)
from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.consent import Consent
from satbhoomi.db.models.farmer import Farmer
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db

router = APIRouter(tags=["Consents"])


@router.post(
    "/farmers/{id}/consents",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid purpose"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Farmer not found"},
        409: {"model": ErrorResponse, "description": "Active consent already exists"},
    },
)
def give_consent(
    id: int = FPath(..., description="Farmer identifier"),
    payload: ConsentCreateRequest | None = None,
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Record a newly granted processing consent for a farmer."""
    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    if payload is None or not payload.purpose:
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_PURPOSE",
            message="Consent purpose is required",
            field="purpose",
        )

    if payload.purpose not in ALLOWED_CONSENT_PURPOSES:
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_PURPOSE",
            message=(
                f"Invalid consent purpose '{payload.purpose}'. "
                f"Must be one of: {', '.join(ALLOWED_CONSENT_PURPOSES)}"
            ),
            field="purpose",
        )

    if get_mock_status():
        now_iso = datetime.now(UTC).isoformat()
        return ConsentResponse(
            id=101,
            farmer_id=id,
            purpose=payload.purpose,
            given_on=now_iso,
            withdrawn_on=None,
            recorded_by=current_user.id if current_user else 1,
        )

    farmer = db.get(Farmer, id)
    if not farmer:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FARMER_NOT_FOUND",
            message=f"Farmer with id {id} not found",
            field="id",
        )

    # Check for active consent for this farmer and purpose
    existing_stmt = select(Consent).where(
        Consent.farmer_id == id,
        Consent.purpose == payload.purpose,
        Consent.withdrawn_on.is_(None),
    )
    existing_active = db.execute(existing_stmt).scalar_one_or_none()
    if existing_active:
        return standard_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="ACTIVE_CONSENT_EXISTS",
            message=(
                f"An active consent for purpose '{payload.purpose}' already exists for this farmer"
            ),
            field="purpose",
        )

    now = datetime.now(UTC)
    consent = Consent(
        farmer_id=id,
        purpose=payload.purpose,
        given_on=now,
        withdrawn_on=None,
        recorded_by=current_user.id,
    )
    db.add(consent)
    db.flush()

    farmer.consent_id = consent.id

    write_audit_log(
        db=db,
        user_id=current_user.id,
        event="consent_granted",
        entity="consent",
        entity_id=consent.id,
        at=now,
    )
    db.commit()

    return ConsentResponse(
        id=consent.id,
        farmer_id=consent.farmer_id,
        purpose=consent.purpose,
        given_on=consent.given_on.isoformat(),
        withdrawn_on=None,
        recorded_by=consent.recorded_by,
    )


@router.post(
    "/consents/{id}/withdraw",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Consent not found"},
        409: {"model": ErrorResponse, "description": "Consent already withdrawn"},
    },
)
def withdraw_consent(
    id: int = FPath(..., description="Consent identifier"),
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Withdraw an active processing consent."""
    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    if get_mock_status():
        now_iso = datetime.now(UTC).isoformat()
        return ConsentResponse(
            id=id,
            farmer_id=1,
            purpose="credit_scoring",
            given_on="2026-11-01T00:00:00Z",
            withdrawn_on=now_iso,
            recorded_by=current_user.id if current_user else 1,
        )

    consent = db.get(Consent, id)
    if not consent:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="CONSENT_NOT_FOUND",
            message=f"Consent with id {id} not found",
            field="id",
        )

    if consent.withdrawn_on is not None:
        return standard_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="CONSENT_ALREADY_WITHDRAWN",
            message=f"Consent with id {id} has already been withdrawn",
            field="id",
        )

    now = datetime.now(UTC)
    consent.withdrawn_on = now

    farmer = db.get(Farmer, consent.farmer_id)
    if farmer and farmer.consent_id == consent.id:
        farmer.consent_id = None

    write_audit_log(
        db=db,
        user_id=current_user.id,
        event="consent_withdrawn",
        entity="consent",
        entity_id=consent.id,
        at=now,
    )
    db.commit()

    return ConsentResponse(
        id=consent.id,
        farmer_id=consent.farmer_id,
        purpose=consent.purpose,
        given_on=consent.given_on.isoformat(),
        withdrawn_on=consent.withdrawn_on.isoformat(),
        recorded_by=consent.recorded_by,
    )


@router.get(
    "/farmers/{id}/consents",
    response_model=ConsentListResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Farmer not found"},
    },
)
def list_farmer_consents(
    id: int = FPath(..., description="Farmer identifier"),
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Retrieve full consent history for a farmer."""
    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    if get_mock_status():
        return ConsentListResponse(
            items=[
                ConsentResponse(
                    id=1,
                    farmer_id=id,
                    purpose="credit_scoring",
                    given_on="2026-11-01T00:00:00Z",
                    withdrawn_on=None,
                    recorded_by=current_user.id if current_user else 1,
                )
            ],
            total=1,
        )

    farmer = db.get(Farmer, id)
    if not farmer:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="FARMER_NOT_FOUND",
            message=f"Farmer with id {id} not found",
            field="id",
        )

    stmt = select(Consent).where(Consent.farmer_id == id).order_by(Consent.given_on.desc())
    consents = db.execute(stmt).scalars().all()

    items = [
        ConsentResponse(
            id=c.id,
            farmer_id=c.farmer_id,
            purpose=c.purpose,
            given_on=c.given_on.isoformat(),
            withdrawn_on=c.withdrawn_on.isoformat() if c.withdrawn_on else None,
            recorded_by=c.recorded_by,
        )
        for c in consents
    ]

    return ConsentListResponse(items=items, total=len(items))
