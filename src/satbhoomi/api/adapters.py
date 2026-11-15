"""Explicit adapter functions converting real domain result objects into API response schemas.

Task T-10 / v0.3.0 API contract compliance:
- Bridges RiskScoreResult (T-06) -> AssessmentResponse
- Bridges LoanSuggestionResult (T-07) -> LoanSuggestionResponse
- Bridges WhatIfResult (T-08) -> WhatIfResponse
- Bridges AlertItem / EvaluationCheckpointResult (T-09) -> AlertSummary / PlotMonitoringResponse
- Bridges stored ORM Assessment -> AssessmentResponse
"""

from __future__ import annotations

from typing import Any, Literal

from satbhoomi.alerts.models import AlertItem, EvaluationCheckpointResult
from satbhoomi.api.schemas.assessments import (
    AssessmentResponse,
    LoanSuggestionResponse,
    ReasonItem,
)
from satbhoomi.api.schemas.common import ResponseMeta
from satbhoomi.api.schemas.monitoring import AlertSummary, PlotMonitoringResponse, TimelinePoint
from satbhoomi.api.schemas.what_if import WhatIfResponse
from satbhoomi.risk.config import CUTOFF_DATE_LABEL, FIXED_INTERPRETATION
from satbhoomi.risk.loan_suggestions import LoanSuggestionResult
from satbhoomi.risk.scoring import FIXED_RELIABILITY_NOTE, RiskScoreResult
from satbhoomi.risk.what_if import WhatIfResult


def adapt_loan_suggestion_to_response(
    loan_result: LoanSuggestionResult,
) -> LoanSuggestionResponse:
    """Adapt a domain LoanSuggestionResult (T-07) into the API LoanSuggestionResponse schema."""
    return LoanSuggestionResponse(
        status=loan_result.status,
        plot_code=loan_result.plot_code,
        season=loan_result.season,
        crop=loan_result.crop,
        area_acre=loan_result.area_acre,
        irrigation=loan_result.irrigation,
        risk_band=loan_result.risk_band,
        risk_score=loan_result.risk_score,
        limit_band=loan_result.limit_band,
        repayment_schedule=loan_result.repayment_schedule,
        insurance_required=loan_result.insurance_required,
        insurance_note=loan_result.insurance_note,
        disclaimer=loan_result.disclaimer,
        notes=list(loan_result.notes),
    )


def adapt_risk_score_to_assessment_response(
    score_result: RiskScoreResult,
    *,
    assessment_id: int = 1,
    plot_id: int = 1,
    created_at: str = "2026-11-13T10:00:00Z",
    loan_suggestion: LoanSuggestionResponse | None = None,
    synthetic: bool = True,
) -> AssessmentResponse:
    """Adapt a domain RiskScoreResult (T-06) into the API AssessmentResponse schema."""
    keys = (
        score_result.reason_keys
        if score_result.reason_keys and len(score_result.reason_keys) == len(score_result.reasons)
        else ["in_season_agronomic_indicators"] * len(score_result.reasons)
    )
    reasons: list[ReasonItem] = []
    for k, r in zip(keys, score_result.reasons, strict=False):
        reasons.append(
            ReasonItem(
                feature_name=k,
                text=r,
            )
        )

    return AssessmentResponse(
        id=assessment_id,
        plot_id=plot_id,
        plot_code=score_result.plot_code,
        season=score_result.season,
        status=score_result.status,
        score=score_result.score,
        band=score_result.band,
        reasons=reasons,
        protective_factor=score_result.protective_factor,
        model_version=score_result.model_version,
        scorer=score_result.scorer,
        cutoff_date=score_result.cutoff_date,
        cutoff_date_iso=getattr(score_result, "cutoff_date_iso", None),
        data_warnings=list(score_result.data_warnings),
        insufficient_data_reason=score_result.insufficient_data_reason,
        interpretation=score_result.interpretation,
        reliability_note=score_result.reliability_note,
        loan_suggestion=loan_suggestion,
        created_at=created_at,
        meta=ResponseMeta(synthetic=synthetic, version="0.3.0"),
    )


def adapt_stored_assessment_to_response(
    assessment: Any,
    *,
    plot_code: str,
    protective_factor: str | None = None,
    synthetic: bool = False,
) -> AssessmentResponse:
    """Adapt a persisted ORM Assessment model into the API AssessmentResponse schema."""
    reasons: list[ReasonItem] = []
    reason_keys: list[str] = []
    if assessment.reasons_json:
        if isinstance(assessment.reasons_json, dict):
            items = assessment.reasons_json.get("top_reasons", [])
            for item in items:
                reasons.append(
                    ReasonItem(
                        feature_name="in_season_agronomic_indicators",
                        text=str(item),
                    )
                )
                reason_keys.append("in_season_agronomic_indicators")
        elif isinstance(assessment.reasons_json, list):
            for item in assessment.reasons_json:
                if isinstance(item, dict):
                    fn = item.get("feature_name", "in_season_agronomic_indicators")
                    reasons.append(
                        ReasonItem(
                            feature_name=fn,
                            text=item.get("text", ""),
                        )
                    )
                    reason_keys.append(fn)
                else:
                    reasons.append(
                        ReasonItem(
                            feature_name="in_season_agronomic_indicators",
                            text=str(item),
                        )
                    )
                    reason_keys.append("in_season_agronomic_indicators")

    loan_resp = None
    if assessment.loan_suggestion_json:
        loan_resp = LoanSuggestionResponse(**assessment.loan_suggestion_json)

    cutoff_iso = (
        assessment.cutoff_date.isoformat()
        if hasattr(assessment.cutoff_date, "isoformat")
        else (str(assessment.cutoff_date) if assessment.cutoff_date else None)
    )

    return AssessmentResponse(
        id=assessment.id,
        plot_id=assessment.plot_id,
        plot_code=plot_code,
        season=assessment.season,
        status=assessment.status,
        score=int(round(assessment.score)) if assessment.score is not None else None,
        band=assessment.band,
        reasons=reasons,
        protective_factor=protective_factor,
        model_version=assessment.model_version,
        scorer=assessment.scorer,
        cutoff_date=CUTOFF_DATE_LABEL,
        cutoff_date_iso=cutoff_iso,
        data_warnings=list(assessment.data_warnings or []),
        insufficient_data_reason=assessment.insufficient_data_reason,
        interpretation=FIXED_INTERPRETATION,
        reliability_note=FIXED_RELIABILITY_NOTE,
        loan_suggestion=loan_resp,
        created_at=assessment.created_at.isoformat()
        if hasattr(assessment.created_at, "isoformat")
        else str(assessment.created_at),
        meta=ResponseMeta(synthetic=synthetic, version="0.3.0"),
    )


def adapt_what_if_to_response(
    what_if_result: WhatIfResult,
    *,
    assessment_id: int | None = None,
    plot_id: int | None = None,
    effect_basis: Literal["scorer_input", "scenario_assumption", "not_modelled"] | None = None,
    assumption: str | None = None,
    synthetic: bool = True,
) -> WhatIfResponse:
    """Adapt a domain WhatIfResult (T-08) into the API WhatIfResponse schema."""
    if effect_basis is None:
        if what_if_result.score_delta == 0 and what_if_result.changed_input not in (
            "insured",
            "irrigation",
        ):
            derived_effect_basis: Literal["scorer_input", "scenario_assumption", "not_modelled"] = (
                "not_modelled"
            )
        elif what_if_result.changed_input == "supplementary_irrigation":
            derived_effect_basis = "scenario_assumption"
        else:
            derived_effect_basis = "scorer_input"
    else:
        derived_effect_basis = effect_basis

    if assumption is None and derived_effect_basis == "scenario_assumption":
        derived_assumption = (
            "Supplementary irrigation assumes assured secondary water application "
            "during flowering/grain-filling stages."
        )
    else:
        derived_assumption = assumption

    return WhatIfResponse(
        status=what_if_result.status,
        assessment_id=assessment_id or what_if_result.assessment_id,
        plot_id=plot_id or 1,
        plot_code=what_if_result.plot_code,
        season=what_if_result.season,
        changed_input=what_if_result.changed_input,  # type: ignore[arg-type]
        old_value=what_if_result.old_value,
        new_value=what_if_result.new_value,
        old_score=what_if_result.old_score,
        new_score=what_if_result.new_score,
        score_delta=what_if_result.score_delta,
        old_band=what_if_result.old_band,
        new_band=what_if_result.new_band,
        old_limit_band=what_if_result.old_limit_band,
        new_limit_band=what_if_result.new_limit_band,
        estimate_label="estimate",
        effect_basis=derived_effect_basis,
        assumption=derived_assumption,
        rationale=what_if_result.rationale,
        disclaimer=what_if_result.disclaimer,
        reliability_note=getattr(what_if_result, "reliability_note", FIXED_RELIABILITY_NOTE),
        notes=list(what_if_result.notes),
        meta=ResponseMeta(synthetic=synthetic, version="0.3.0"),
    )


def adapt_alert_item_to_summary(
    alert_item: AlertItem,
    *,
    alert_id: int | None = None,
) -> AlertSummary:
    """Adapt a domain AlertItem (T-09) into the API AlertSummary schema."""
    return AlertSummary(
        id=alert_id,
        plot_code=alert_item.plot_code,
        season=alert_item.season,
        checkpoint_label=alert_item.checkpoint_label,
        detected_on=str(alert_item.detected_on),
        type=alert_item.type,
        severity=alert_item.severity,
        status=alert_item.status,
        headline=alert_item.headline,
        detail=alert_item.detail,
        supportive_action=alert_item.supportive_action,
        data_gap_warning=alert_item.data_gap_warning,
    )


def adapt_checkpoint_to_monitoring_response(
    checkpoint: EvaluationCheckpointResult,
    *,
    plot_id: int = 1,
    timeline: list[TimelinePoint] | None = None,
    past_alerts: list[AlertSummary] | None = None,
    synthetic: bool = True,
) -> PlotMonitoringResponse:
    """Adapt an EvaluationCheckpointResult (T-09) into PlotMonitoringResponse."""
    active_summaries = [adapt_alert_item_to_summary(a) for a in checkpoint.alerts]
    return PlotMonitoringResponse(
        plot_id=plot_id,
        plot_code=checkpoint.plot_code,
        season=checkpoint.season,
        status=checkpoint.status,
        data_gap_reason=checkpoint.data_gap_reason,
        checkpoint_label=checkpoint.checkpoint_label,
        evaluation_date=str(checkpoint.evaluation_date),
        timeline=timeline or [],
        active_alerts=active_summaries,
        past_alerts=past_alerts or [],
        meta=ResponseMeta(synthetic=synthetic, version="0.3.0"),
    )
