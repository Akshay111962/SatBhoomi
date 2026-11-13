"""Assessment execution and retrieval routes (blueprint section 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, status
from fastapi import Path as FPath

from satbhoomi.api.mock_data import MOCK_ASSESSMENTS
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    not_implemented_response,
    standard_error_response,
    verify_mock_auth,
)
from satbhoomi.api.schemas.assessments import AssessmentCreateRequest, AssessmentResponse
from satbhoomi.api.schemas.common import ErrorResponse

router = APIRouter(tags=["Assessments"])


@router.post(
    "/plots/{id}/assessments",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,

    
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Plot not found"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def create_assessment(
    id: int = FPath(..., description="Target plot identifier"),
    payload: AssessmentCreateRequest | None = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    token: str = Depends(verify_mock_auth),
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Execute risk assessment for a plot and return deterministic score with reasons."""
    if not get_mock_status():
        return not_implemented_response()

    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    # Check mock plot exists
    if id not in MOCK_ASSESSMENTS:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Plot with id {id} not found",
            field="id",
        )

    return MOCK_ASSESSMENTS[id]


@router.get(
    "/assessments/{id}",
    response_model=AssessmentResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Assessment not found"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def get_assessment(
    id: int = FPath(..., description="Assessment identifier"),
    token: str = Depends(verify_mock_auth),
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Retrieve an existing assessment result by ID."""
    if not get_mock_status():
        return not_implemented_response()

    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    if id not in MOCK_ASSESSMENTS:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Assessment with id {id} not found",
            field="id",
        )

    return MOCK_ASSESSMENTS[id]
