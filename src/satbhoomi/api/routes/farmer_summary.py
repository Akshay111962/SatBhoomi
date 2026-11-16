"""Vernacular farmer summary routes (blueprint section 8)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response, status
from fastapi import Path as FPath
from sqlalchemy.orm import Session

from satbhoomi.api.mock_data import MOCK_ASSESSMENTS, MOCK_FARMER_SUMMARIES, SYNTHETIC_META
from satbhoomi.api.routes.deps import (
    check_mock_error_triggers,
    enforce_farmer_consent,
    get_mock_status,
    require_officer,
    standard_error_response,
)
from satbhoomi.api.schemas.common import ErrorResponse, ResponseMeta
from satbhoomi.api.schemas.farmer_summary import FarmerSummaryResponse
from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.assessment import Assessment
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db

router = APIRouter(tags=["Farmer Summary"])


@router.get(
    "/assessments/{id}/farmer-summary",
    response_model=FarmerSummaryResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Unsupported language parameter"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Consent required or forbidden"},
        404: {"model": ErrorResponse, "description": "Assessment not found"},
    },
)
def get_farmer_summary(
    id: int = FPath(..., description="Target assessment identifier"),
    lang: str = Query(default="en", description="Language code: en, gu, or hi"),
    current_user: Annotated[User, Depends(require_officer)] = ...,  # type: ignore[assignment]
    db: Annotated[Session, Depends(get_db)] = ...,  # type: ignore[assignment]
    x_mock_error: str | None = Header(default=None, alias="X-Mock-Error"),
) -> Response:
    """Generate plain-language credit summary in Gujarati, Hindi, or English."""
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

    # 1. Mock mode branch
    if get_mock_status():
        if id not in MOCK_ASSESSMENTS:
            return standard_error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                code="NOT_FOUND",
                message=f"Assessment with id {id} not found",
                field="id",
            )

        key = (id, lang_lower)
        if key in MOCK_FARMER_SUMMARIES:
            return MOCK_FARMER_SUMMARIES[key]

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

    # 2. Real database mode branch
    assessment = db.get(Assessment, id)
    if not assessment:
        return standard_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            message=f"Assessment with id {id} not found",
            field="id",
        )

    plot = db.get(Plot, assessment.plot_id)
    if plot:
        enforce_farmer_consent(db, plot.farmer_id)

    plot_code_str = plot.plot_code if plot else f"PLOT-{assessment.plot_id:03d}"
    limit_val = 60000
    if assessment.loan_suggestion and isinstance(assessment.loan_suggestion, dict):
        limit_val = int(assessment.loan_suggestion.get("suggested_limit_inr", 60000))

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

    write_audit_log(
        db=db,
        user_id=current_user.id,
        event="farmer_summary_read",
        entity="assessment",
        entity_id=assessment.id,
    )
    db.commit()

    return FarmerSummaryResponse(
        assessment_id=id,
        plot_code=plot_code_str,
        lang=lang_lower,  # type: ignore[arg-type]
        source="template",
        summary_text=text,
        key_points=points,
        meta=ResponseMeta(
            timestamp=assessment.created_at,
            synthetic=True,
            version="0.6.0",
        ),
    )
