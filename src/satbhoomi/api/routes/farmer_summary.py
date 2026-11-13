"""[DRAFT] Vernacular farmer summary routes (blueprint section 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi import Path as FPath

from satbhoomi.api.mock_data import MOCK_ASSESSMENTS, MOCK_FARMER_SUMMARIES, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    get_mock_status,
    not_implemented_response,
    standard_error_response,
    verify_mock_auth,
)
from satbhoomi.api.schemas.common import ErrorResponse
from satbhoomi.api.schemas.farmer_summary import FarmerSummaryResponse

router = APIRouter(tags=["Farmer Summary"])


@router.get(
    "/assessments/{id}/farmer-summary",
    response_model=FarmerSummaryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Unsupported language parameter"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        404: {"model": ErrorResponse, "description": "Assessment not found"},
        501: {"model": ErrorResponse, "description": "Not implemented (when MOCK_API=false)"},
    },
)
def get_farmer_summary(
    id: int = FPath(..., description="Target assessment identifier"),
    lang: str = Query(default="en", description="Language code: en, gu, or hi"),
    token: str = Depends(verify_mock_auth),
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """[DRAFT] Generate plain-language credit summary in Gujarati, Hindi, or English."""
    if not get_mock_status():
        return not_implemented_response()

    err = check_mock_error_triggers(x_mock_error, resource_id=id)
    if err:
        return err

    lang_lower = lang.lower()
    if lang_lower not in ("en", "gu", "hi"):
        return standard_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_LANGUAGE",
            message="Supported languages are 'en' (English), 'gu' (Gujarati), and 'hi' (Hindi)",
            field="lang",
        )

    if id not in MOCK_ASSESSMENTS:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Assessment with id {id} not found",
            field="id",
        )

    # Return predefined translation if available
    key = (id, lang_lower)
    if key in MOCK_FARMER_SUMMARIES:
        return MOCK_FARMER_SUMMARIES[key]

    # Deterministic template fallback
    base_asm = MOCK_ASSESSMENTS[id]
    limit_val = (
        int(base_asm.loan_suggestion.suggested_limit_inr) if base_asm.loan_suggestion else 60000
    )

    if lang_lower == "gu":
        text = f"તમારા પાકની સ્થિતિનું મૂલ્યાંકન કરવામાં આવ્યું છે. સૂચવેલ ધિરાણ મર્યાદા ₹{limit_val:,} છે."
        points = ["પાકનું મૂલ્યાંકન પૂર્ણ થયું છે.", "ચુકવણી લણણી પછી મે મહિનામાં રહેશે."]
    elif lang_lower == "hi":
        text = f"आपकी फसल का मूल्यांकन पूरा हो गया है। सुझाई गई ऋण सीमा ₹{limit_val:,} है।"
        points = ["फसल का मूल्यांकन पूरा हुआ।", "भुगतान कटाई के बाद मई में होगा।"]
    else:
        text = (
            f"Your crop risk assessment is complete. Suggested credit limit is ₹{limit_val:,} "
            "with repayment in May."
        )
        points = ["Assessment is complete.", "Repayment scheduled after harvest in May."]

    return FarmerSummaryResponse(
        assessment_id=id,
        plot_code=base_asm.plot_code,
        lang=lang_lower,  # type: ignore[arg-type]
        source="template",
        summary_text=text,
        key_points=points,
        meta=SYNTHETIC_META,
    )
