"""[DRAFT] Alert action logging routes (blueprint section 8).

Updated in Task T-11C with real action persistence, officer lifecycle tracking,
and audit trail generation.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.api.mock_data import SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    require_officer,
    standard_error_response,
)
from satbhoomi.api.schemas.alerts import AlertActionRequest, AlertActionResponse
from satbhoomi.api.schemas.common import ErrorResponse, ResponseMeta
from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.action_log import ActionLog
from satbhoomi.db.models.alert import Alert
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db

router = APIRouter(prefix="/alerts", tags=["Alerts"])

# Canonical officer playbook actions (strictly supportive, no recovery pressure, no direct contact)
PLAYBOOK_ACTIONS: frozenset[str] = frozenset(
    {
        "field_visit",
        "insurance_claim_help",
        "extension_support",
        "repayment_timing_discussion",
        "rescheduling_request",
        "senior_or_local_support",
        # Backward-compatible aliases
        "supportive_field_visit",
        "check_water_irrigation",
        "harvest_repayment_rescheduling",
    }
)

# Regex patterns matching phone numbers, Aadhaar/ID numbers, or account numbers
PII_NUMBER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b\d{10,18}\b"),  # 10 to 18 contiguous digits (phone / account)
    re.compile(r"\b\d{4}[-\s]\d{4}[-\s]\d{4}\b"),  # 12-digit Aadhaar / ID pattern
    re.compile(r"(\+91[\-\s]?)?[6789]\d{9}"),  # Indian mobile number format
)


@router.post(
    "/{id}/actions",
    response_model=AlertActionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error or disallowed PII in note"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Alert not found"},
        409: {"model": ErrorResponse, "description": "Disallowed status transition"},
    },
)
def log_alert_action(
    id: int = FPath(..., description="Target alert identifier"),
    payload: AlertActionRequest = ...,
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Log a supportive loan officer action taken in response to an in-season alert."""
    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    # 1. Mock Mode Branch
    if get_mock_status():
        if id > 500:
            return standard_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                code="NOT_FOUND",
                message=f"Alert {id} not found",
                field="id",
            )

        return AlertActionResponse(
            action_id=id * 10,
            alert_id=id,
            action_type=payload.action_type,
            note=payload.note,
            status_before="open",
            status_after="in_progress",
            done_by="Mock-Officer-01",
            done_on="2026-11-15T12:00:00Z",
            status="recorded",
            meta=SYNTHETIC_META,
        )

    # 2. Real Mode Branch: validate action type against playbook
    if payload.action_type not in PLAYBOOK_ACTIONS:
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_ACTION_TYPE",
            message=(
                f"Action type '{payload.action_type}' is not recognized in the officer playbook."
            ),
            field="action_type",
        )

    # Validate note length and reject phone / ID / account numbers
    if len(payload.note) > 500:
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="NOTE_TOO_LONG",
            message="Action note must not exceed 500 characters.",
            field="note",
        )

    for pat in PII_NUMBER_PATTERNS:
        if pat.search(payload.note):
            return standard_error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="PII_NOT_PERMITTED",
                message=(
                    "Action note must not contain phone numbers, "
                    "identification numbers, or account numbers."
                ),
                field="note",
            )

    # Fetch alert
    alert = db.execute(select(Alert).where(Alert.id == id)).scalars().one_or_none()
    if not alert:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Alert with id {id} not found",
            field="id",
        )

    # Enforce alert status transition lifecycle: open -> in_progress -> resolved
    status_before = alert.status
    if status_before == "open":
        status_after = "in_progress"
    elif status_before in ("in_progress", "acknowledged"):
        status_after = "resolved"
    elif status_before in ("resolved", "dismissed"):
        return standard_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="DISALLOWED_STATUS_TRANSITION",
            message=f"Cannot record action on alert already in '{status_before}' state.",
            field="status",
        )
    else:
        return standard_error_response(
            status_code=status.HTTP_409_CONFLICT,
            code="DISALLOWED_STATUS_TRANSITION",
            message=f"Disallowed status transition from '{status_before}'.",
            field="status",
        )

    # Update alert status
    alert.status = status_after

    # Create ActionLog row
    now = datetime.now(UTC)
    action_log = ActionLog(
        alert_id=alert.id,
        action_type=payload.action_type,
        note=payload.note,
        status_before=status_before,
        status_after=status_after,
        done_by=current_user.id,
        done_on=now,
    )
    db.add(action_log)
    db.flush()

    # Append-only audit trail (zero PII)
    write_audit_log(
        db=db,
        user_id=current_user.id,
        event="alert_action_logged",
        entity="alert",
        entity_id=alert.id,
        at=now,
    )

    db.commit()

    officer_name = current_user.name or current_user.username or f"Officer-{current_user.id:03d}"
    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=AlertActionResponse(
            action_id=action_log.id,
            alert_id=alert.id,
            action_type=action_log.action_type,
            note=action_log.note or "",
            status_before=status_before,
            status_after=status_after,
            done_by=officer_name,
            done_on=now.isoformat(),
            status="recorded",
            meta=ResponseMeta(timestamp=now, synthetic=False, version="0.4.0"),
        ).model_dump(mode="json"),
    )
