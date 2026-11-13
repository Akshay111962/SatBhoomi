"""[DRAFT] Alert action logging routes (blueprint section 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath

from satbhoomi.api.mock_data import SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    not_implemented_response,
    standard_error_response,
    verify_mock_auth,
)
from satbhoomi.api.schemas.alerts import AlertActionRequest, AlertActionResponse
from satbhoomi.api.schemas.common import ErrorResponse

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post(
    "/{id}/actions",
    response_model=AlertActionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Alert not found"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def log_alert_action(
    id: int = FPath(..., description="Target alert identifier"),
    payload: AlertActionRequest = ...,
    token: str = Depends(verify_mock_auth),
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """[DRAFT] Log a supportive loan officer action taken in response to an in-season alert."""
    if not get_mock_status():
        return not_implemented_response()

    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    if id > 500:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Alert with id {id} not found",
            field="id",
        )

    return AlertActionResponse(
        action_id=1,
        alert_id=id,
        action_type=payload.action_type,
        note=payload.note,
        done_by="Officer-001",
        done_on="2026-11-13T10:30:00Z",
        status="recorded",
        meta=SYNTHETIC_META,
    )
