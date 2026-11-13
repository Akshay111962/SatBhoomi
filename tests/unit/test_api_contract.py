"""Unit tests verifying SatBhoomi API contract, OpenAPI specification, and PII guardrails."""

from __future__ import annotations

import json
import re
from pathlib import Path

from satbhoomi.api.main import API_CONTRACT_VERSION, app
from satbhoomi.api.mock_data import (
    MOCK_ASSESSMENTS,
    MOCK_FARMER_SUMMARIES,
    MOCK_MONITORING,
    MOCK_RELIEF_REPORTS,
)
from satbhoomi.api.schemas.assessments import AssessmentResponse
from satbhoomi.api.schemas.relief import ReliefReportResponse
from satbhoomi.api.schemas.what_if import WhatIfResponse
from satbhoomi.risk.scoring import RiskScoreResult

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

    # Every key field from RiskScoreResult must be in AssessmentResponse
    missing_fields = risk_fields - assessment_fields
    assert not missing_fields, (
        f"AssessmentResponse missing RiskScoreResult fields: {missing_fields}"
    )


def test_what_if_and_relief_mandatory_disclaimers() -> None:
    """What-if responses must carry 'estimate' label; relief reports must carry disclaimer."""
    what_if = WhatIfResponse(
        assessment_id=1,
        plot_id=1,
        changed_input="insured",
        old_value="0",
        new_value="1",
        original_score=45,
        simulated_score=35,
        original_band="medium",
        simulated_band="medium",
        score_delta=-10,
    )
    assert what_if.estimate_label == "estimate"
    assert "not prove causation" in what_if.causation_disclaimer.lower()

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
