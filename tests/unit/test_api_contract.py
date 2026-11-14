"""Unit tests verifying SatBhoomi API contract, OpenAPI specification, and PII guardrails."""

from __future__ import annotations

import json
import re
from pathlib import Path

from satbhoomi.alerts.models import AlertItem, EvaluationCheckpointResult
from satbhoomi.api.adapters import (
    adapt_alert_item_to_summary,
    adapt_checkpoint_to_monitoring_response,
    adapt_loan_suggestion_to_response,
    adapt_risk_score_to_assessment_response,
    adapt_what_if_to_response,
)
from satbhoomi.api.main import API_CONTRACT_VERSION, app
from satbhoomi.api.mock_data import (
    MOCK_ASSESSMENTS,
    MOCK_FARMER_SUMMARIES,
    MOCK_MONITORING,
    MOCK_RELIEF_REPORTS,
)
from satbhoomi.api.schemas.assessments import AssessmentResponse, LoanSuggestionResponse
from satbhoomi.api.schemas.monitoring import AlertSummary
from satbhoomi.api.schemas.relief import ReliefReportResponse
from satbhoomi.api.schemas.what_if import WhatIfResponse
from satbhoomi.risk.loan_suggestions import (
    DISCLAIMER_LOAN_SUGGESTION,
    LimitBand,
    LoanSuggestionResult,
    RepaymentSchedule,
)
from satbhoomi.risk.scoring import RiskScoreResult
from satbhoomi.risk.what_if import DISCLAIMER_WHAT_IF, WhatIfResult

BANNED_WORDS: tuple[str, ...] = (
    "depressed",
    "depression",
    "suicidal",
    "suicide",
    "hopeless",
    "despair",
    "anxiety",
    "panic",
    "mental",
    "lazy",
    "irresponsible",
    "negligent",
    "fault",
    "guilty",
    "reckless",
    "careless",
    "defaulter",
    "criminal",
    "blame",
)

FORBIDDEN_PII_FIELDS: tuple[str, ...] = (
    "aadhaar",
    "pan",
    "phone",
    "mobile",
    "bank_account",
    "account_number",
    "ssn",
    "national_id",
)


def test_openapi_spec_deterministic_and_no_drift() -> None:
    """Committed docs/api/openapi.json must strictly equal the generated spec."""
    spec_path = Path("docs/api/openapi.json")
    assert spec_path.is_file(), "docs/api/openapi.json must exist in repo."

    with open(spec_path, encoding="utf-8") as f:
        committed_spec = json.load(f)

    generated_spec = app.openapi()
    generated_spec["info"]["version"] = API_CONTRACT_VERSION

    # Dump and reload to normalize json types
    norm_generated = json.loads(json.dumps(generated_spec, sort_keys=True))
    norm_committed = json.loads(json.dumps(committed_spec, sort_keys=True))

    assert norm_committed == norm_generated, (
        "OpenAPI spec drift detected! Run 'python scripts/export_openapi.py' to update spec."
    )


def test_no_personal_data_fields_in_schemas() -> None:
    """Response and request schemas must not contain any personal data fields."""
    openapi = app.openapi()
    schemas = openapi.get("components", {}).get("schemas", {})

    for schema_name, schema_obj in schemas.items():
        properties = schema_obj.get("properties", {})
        for prop_name in properties:
            for pii in FORBIDDEN_PII_FIELDS:
                assert pii not in prop_name.lower(), (
                    f"Forbidden PII field '{prop_name}' found in schema '{schema_name}'"
                )


def test_no_banned_wording_in_mock_text() -> None:
    """Mock sample data must adhere strictly to Rule 2 ethical wording."""
    text_corpus: list[str] = []

    for a in MOCK_ASSESSMENTS.values():
        text_corpus.extend([r.text for r in a.reasons])
        if a.protective_factor:
            text_corpus.append(a.protective_factor)
        text_corpus.append(a.interpretation)
        text_corpus.append(a.reliability_note)

    for m in MOCK_MONITORING.values():
        for alert in m.active_alerts:
            text_corpus.extend([alert.headline, alert.detail, alert.supportive_action])

    for r in MOCK_RELIEF_REPORTS.values():
        text_corpus.extend([r.supporting_evidence_summary, r.disclaimer])

    for s in MOCK_FARMER_SUMMARIES.values():
        text_corpus.append(s.summary_text)
        text_corpus.extend(s.key_points)

    for text in text_corpus:
        text_lower = text.lower()
        for banned in BANNED_WORDS:
            assert not re.search(rf"\b{re.escape(banned)}\b", text_lower), (
                f"Banned word '{banned}' found in mock text: '{text}'"
            )


def test_assessment_schema_matches_t06_risk_score_result() -> None:
    """AssessmentResponse schema must match the real RiskScoreResult from scoring.py."""
    risk_fields = set(RiskScoreResult.model_fields.keys())
    assessment_fields = set(AssessmentResponse.model_fields.keys())

    missing_fields = risk_fields - assessment_fields
    assert not missing_fields, (
        f"AssessmentResponse missing RiskScoreResult fields: {missing_fields}"
    )


def test_loan_suggestion_schema_matches_real_loan_suggestion_result() -> None:
    """LoanSuggestionResponse schema must match the real LoanSuggestionResult from T-07."""
    real_fields = set(LoanSuggestionResult.model_fields.keys())
    schema_fields = set(LoanSuggestionResponse.model_fields.keys())

    missing_fields = real_fields - schema_fields
    assert not missing_fields, (
        f"LoanSuggestionResponse missing LoanSuggestionResult fields: {missing_fields}"
    )


def test_what_if_schema_matches_real_what_if_result() -> None:
    """WhatIfResponse schema must match the real WhatIfResult from T-08."""
    real_fields = set(WhatIfResult.model_fields.keys())
    schema_fields = set(WhatIfResponse.model_fields.keys())

    missing_fields = real_fields - schema_fields
    assert not missing_fields, f"WhatIfResponse missing WhatIfResult fields: {missing_fields}"


def test_alert_item_schema_matches_real_alert_item() -> None:
    """AlertSummary schema must match the real AlertItem from T-09."""
    real_fields = set(AlertItem.model_fields.keys())
    schema_fields = set(AlertSummary.model_fields.keys())

    missing_fields = real_fields - schema_fields
    assert not missing_fields, f"AlertSummary missing AlertItem fields: {missing_fields}"


def test_what_if_and_relief_mandatory_disclaimers() -> None:
    """What-if responses must carry 'estimate' label; relief reports must carry disclaimer."""
    what_if = WhatIfResponse(
        assessment_id=1,
        plot_id=1,
        plot_code="PLOT-001",
        season="2024-25",
        changed_input="insured",
        old_value="0",
        new_value="1",
        old_score=45,
        new_score=35,
        score_delta=-10,
        old_band="medium",
        new_band="medium",
        estimate_label="estimate",
        effect_basis="scorer_input",
        rationale="Insurance reduces prospective credit risk.",
        disclaimer=DISCLAIMER_WHAT_IF,
    )
    assert what_if.estimate_label == "estimate"
    assert "proof of causation" in what_if.disclaimer.lower()

    relief = ReliefReportResponse(
        plot_id=1,
        plot_code="PLOT-001",
        season="2024-25",
        baseline_ndvi_mean=0.70,
        current_ndvi_mean=0.40,
        ndvi_drop_pct=42.8,
        estimated_loss_band="33% to 50% loss",
        exceeds_rbi_33_threshold=True,
        supporting_evidence_summary="Vegetative drop observed.",
    )
    assert "official crop loss assessment" in relief.disclaimer.lower()


def test_adapters_built_from_real_domain_objects() -> None:
    """Explicit adapters successfully convert real domain results into API schemas."""
    # 1. Real RiskScoreResult -> AssessmentResponse
    score_res = RiskScoreResult(
        status="ok",
        plot_code="PLOT-REAL-01",
        season="2024-25",
        scorer="rules_baseline",
        model_version="rules-v1.0",
        cutoff_date="January 31",
        score=22,
        band="low",
        reasons=["Normal vegetative vigor.", "Adequate precipitation."],
        protective_factor="Tubewell irrigation available.",
        data_warnings=[],
        interpretation="Farm stress estimate.",
        reliability_note="Not validated on disasters.",
    )
    adapted_assessment = adapt_risk_score_to_assessment_response(
        score_res, assessment_id=99, plot_id=42
    )
    assert adapted_assessment.score == 22
    assert adapted_assessment.band == "low"
    assert len(adapted_assessment.reasons) == 2
    assert adapted_assessment.reasons[0].text == "Normal vegetative vigor."

    # 2. Real LoanSuggestionResult -> LoanSuggestionResponse
    limit_b = LimitBand(
        min_amount_inr=72000,
        max_amount_inr=80000,
        scale_of_finance_per_acre_inr=32000,
        gross_scale_limit_inr=80000,
        collateral_free_cap_applied=False,
        haircut_percentage_range="0%–10%",
    )
    repay_s = RepaymentSchedule(
        repayment_month="May",
        rationale="Harvest aligned.",
    )
    loan_res = LoanSuggestionResult(
        status="ok",
        plot_code="PLOT-REAL-01",
        season="2024-25",
        crop="wheat",
        area_acre=2.5,
        irrigation="tube_well",
        risk_band="low",
        risk_score=22,
        limit_band=limit_b,
        repayment_schedule=repay_s,
        insurance_required=False,
        insurance_note="Optional insurance.",
        disclaimer=DISCLAIMER_LOAN_SUGGESTION,
        notes=["Test note"],
    )
    adapted_loan = adapt_loan_suggestion_to_response(loan_res)
    assert adapted_loan.status == "ok"
    assert adapted_loan.limit_band is not None
    assert adapted_loan.limit_band.max_amount_inr == 80000
    assert adapted_loan.repayment_schedule is not None
    assert adapted_loan.repayment_schedule.repayment_month == "May"

    # 3. Real WhatIfResult -> WhatIfResponse
    what_if_res = WhatIfResult(
        status="ok",
        assessment_id=99,
        plot_code="PLOT-REAL-01",
        season="2024-25",
        changed_input="supplementary_irrigation",
        old_value="0",
        new_value="1",
        old_score=45,
        new_score=30,
        score_delta=-15,
        old_band="medium",
        new_band="low",
        old_limit_band=limit_b,
        new_limit_band=limit_b,
        estimate_label="estimate",
        rationale="Secondary watering applied.",
        disclaimer=DISCLAIMER_WHAT_IF,
        notes=["Simulation note"],
    )
    adapted_what_if = adapt_what_if_to_response(what_if_res, plot_id=42)
    assert adapted_what_if.effect_basis == "scenario_assumption"
    assert adapted_what_if.assumption is not None
    assert adapted_what_if.score_delta == -15
    assert adapted_what_if.estimate_label == "estimate"

    # 4. Real AlertItem -> AlertSummary
    from datetime import date

    alert_item = AlertItem(
        type="crop_health_drop",
        severity="medium",
        status="open",
        detected_on=date(2025, 1, 15),
        checkpoint_label="January 15",
        plot_code="PLOT-REAL-01",
        season="2024-25",
        headline="Vegetation drag",
        detail="18% drop recorded.",
        supportive_action="Schedule supportive visit.",
        data_gap_warning=None,
    )
    adapted_alert = adapt_alert_item_to_summary(alert_item, alert_id=501)
    assert adapted_alert.id == 501
    assert adapted_alert.detected_on == "2025-01-15"
    assert adapted_alert.severity == "medium"

    # 5. Real EvaluationCheckpointResult -> PlotMonitoringResponse
    checkpoint_res = EvaluationCheckpointResult(
        plot_code="PLOT-REAL-01",
        season="2024-25",
        checkpoint_label="January 15",
        evaluation_date=date(2025, 1, 15),
        status="ok",
        alerts=[alert_item],
    )
    adapted_monitoring = adapt_checkpoint_to_monitoring_response(checkpoint_res, plot_id=42)
    assert adapted_monitoring.status == "ok"
    assert len(adapted_monitoring.active_alerts) == 1
    assert adapted_monitoring.active_alerts[0].headline == "Vegetation drag"
