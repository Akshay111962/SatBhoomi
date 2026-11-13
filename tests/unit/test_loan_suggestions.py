"""Unit tests for deterministic loan suggestion rules (T-07, FR-006)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from satbhoomi.risk.loan_suggestions import (
    DISCLAIMER_LOAN_SUGGESTION,
    RBI_COLLATERAL_FREE_LIMIT_INR,
    REPAYMENT_MONTH_RABI_WHEAT,
    SCALE_OF_FINANCE_WHEAT_IRRIGATED,
    SCALE_OF_FINANCE_WHEAT_RAINFED,
    generate_loan_suggestion,
)
from satbhoomi.risk.scoring import RiskScoreResult
from scripts.score_plot import main as score_cli_main


def _make_dummy_score(
    score: int | None,
    band: str | None,
    status: str = "ok",
    insufficient_reason: str | None = None,
) -> RiskScoreResult:
    return RiskScoreResult(
        status=status,  # type: ignore[arg-type]
        plot_code="TEST_PLOT_01",
        season="2024-25",
        scorer="rules_baseline",
        model_version="satbhoomi-rules-v1.0-agronomic-jan31",
        score=score,
        band=band,  # type: ignore[arg-type]
        reasons=["Normal growth observed."],
        protective_factor=None,
        data_warnings=[],
        insufficient_data_reason=insufficient_reason,
    )


def test_loan_suggestion_low_risk_irrigated() -> None:
    """Low risk plot receives 90%-100% of scale of finance, recommended insurance."""
    score = _make_dummy_score(score=10, band="low")
    res = generate_loan_suggestion(
        score,
        area_acre=2.5,
        crop="wheat",
        irrigation="tube_well",
        insured=False,
    )

    assert res.status == "ok"
    assert res.risk_band == "low"
    assert res.area_acre == 2.5
    assert res.irrigation == "tube_well"
    assert res.limit_band is not None

    # Gross: 2.5 * 32,000 = 80,000
    assert res.limit_band.scale_of_finance_per_acre_inr == SCALE_OF_FINANCE_WHEAT_IRRIGATED
    assert res.limit_band.gross_scale_limit_inr == 80_000
    assert not res.limit_band.collateral_free_cap_applied

    # Haircut: 90% - 100%
    assert res.limit_band.min_amount_inr == 72_000
    assert res.limit_band.max_amount_inr == 80_000

    # Insurance & schedule
    assert not res.insurance_required
    assert "recommended" in res.insurance_note.lower()
    assert res.repayment_schedule is not None
    assert res.repayment_schedule.repayment_month == REPAYMENT_MONTH_RABI_WHEAT
    assert res.disclaimer == DISCLAIMER_LOAN_SUGGESTION


def test_loan_suggestion_already_insured_skips_mandatory_flag() -> None:
    """Plots already insured receive confirmed status without mandatory requirement."""
    score = _make_dummy_score(score=50, band="medium")
    res = generate_loan_suggestion(
        score,
        area_acre=2.0,
        crop="wheat",
        irrigation="canal",
        insured=True,
    )

    assert res.status == "ok"
    assert not res.insurance_required
    assert "already verified as covered" in res.insurance_note.lower()


def test_loan_suggestion_medium_risk_haircut_and_mandatory_insurance() -> None:
    """Medium risk receives 65%-80% haircut and mandatory PMFBY flag."""
    score = _make_dummy_score(score=45, band="medium")
    res = generate_loan_suggestion(
        score,
        area_acre=2.0,
        crop="wheat",
        irrigation="canal",
        insured=False,
    )

    assert res.status == "ok"
    assert res.risk_band == "medium"
    assert res.limit_band is not None

    # Gross: 2.0 * 32,000 = 64,000
    assert res.limit_band.gross_scale_limit_inr == 64_000
    # 65% of 64,000 = 41,600 -> round 500 = 41,500
    assert res.limit_band.min_amount_inr == 41_500
    # 80% of 64,000 = 51,200 -> round 500 = 51,000
    assert res.limit_band.max_amount_inr == 51_000

    assert res.insurance_required
    assert "mandatory" in res.insurance_note.lower()


def test_loan_suggestion_high_risk_conservative_cap() -> None:
    """High risk receives 40%-50% conservative cap and mid-season review note."""
    score = _make_dummy_score(score=85, band="high")
    res = generate_loan_suggestion(
        score,
        area_acre=3.0,
        crop="wheat",
        irrigation="tube_well",
        insured=False,
    )

    assert res.status == "ok"
    assert res.risk_band == "high"
    assert res.limit_band is not None

    # Gross: 3.0 * 32,000 = 96,000
    assert res.limit_band.gross_scale_limit_inr == 96_000
    # 40% of 96,000 = 38,400 -> round 500 = 38,500
    assert res.limit_band.min_amount_inr == 38_500
    # 50% of 96,000 = 48,000
    assert res.limit_band.max_amount_inr == 48_000

    assert res.insurance_required
    assert res.repayment_schedule is not None
    assert "officer mid-season health check" in res.repayment_schedule.rationale.lower()


def test_loan_suggestion_caps_at_rbi_collateral_free_limit() -> None:
    """Gross scale limits above ₹2,00,000 are capped by RBI KCC guideline."""
    score = _make_dummy_score(score=15, band="low")
    res = generate_loan_suggestion(
        score,
        area_acre=10.0,
        crop="wheat",
        irrigation="canal",
        insured=True,
    )

    assert res.status == "ok"
    assert res.limit_band is not None

    # Gross: 10.0 * 32,000 = 320,000 > 200,000
    assert res.limit_band.gross_scale_limit_inr == 320_000
    assert res.limit_band.collateral_free_cap_applied

    # Haircuts apply to capped ceiling (200,000)
    assert res.limit_band.max_amount_inr == RBI_COLLATERAL_FREE_LIMIT_INR
    assert res.limit_band.min_amount_inr == int(0.90 * RBI_COLLATERAL_FREE_LIMIT_INR)

    assert any("capped at rbi collateral-free ceiling" in n.lower() for n in res.notes)


def test_loan_suggestion_rainfed_scale_of_finance() -> None:
    """Rainfed irrigation uses the lower ₹22,000 / acre scale of finance."""
    score = _make_dummy_score(score=25, band="low")
    res = generate_loan_suggestion(
        score,
        area_acre=4.0,
        crop="wheat",
        irrigation="rainfed",
        insured=False,
    )

    assert res.status == "ok"
    assert res.limit_band is not None
    assert res.limit_band.scale_of_finance_per_acre_inr == SCALE_OF_FINANCE_WHEAT_RAINFED
    # Gross: 4.0 * 22,000 = 88,000
    assert res.limit_band.gross_scale_limit_inr == 88_000
    assert res.limit_band.min_amount_inr == int(round(88_000 * 0.90 / 500) * 500)
    assert res.limit_band.max_amount_inr == 88_000


def test_loan_suggestion_invalid_area_raises() -> None:
    """Area must be strictly positive."""
    score = _make_dummy_score(score=20, band="low")
    with pytest.raises(ValueError, match="area_acre must be strictly positive"):
        generate_loan_suggestion(score, area_acre=0)

    with pytest.raises(ValueError, match="area_acre must be strictly positive"):
        generate_loan_suggestion(score, area_acre=-1.5)


def test_loan_suggestion_insufficient_data_status() -> None:
    """Insufficient data score returns manual appraisal required status."""
    score = _make_dummy_score(
        score=None,
        band=None,
        status="insufficient_data",
        insufficient_reason="Satellite passes obscured by clouds.",
    )
    res = generate_loan_suggestion(
        score,
        area_acre=3.0,
        crop="wheat",
        irrigation="canal",
        insured=False,
    )

    assert res.status == "manual_appraisal_required"
    assert res.limit_band is None
    assert res.repayment_schedule is None
    assert res.insurance_required
    assert "mandatory" in res.insurance_note.lower()
    assert any("suspended" in n.lower() for n in res.notes)


def test_score_plot_cli_with_suggest_loan_flag(tmp_path: Path, monkeypatch) -> None:
    """CLI prints valid LoanSuggestionResult JSON when --suggest-loan is passed."""
    csv_path = tmp_path / "features.csv"
    dummy_row = {
        "plot_code": "TEST_PLOT_01",
        "season": "2024-25",
        "crop": "wheat",
        "district": "Anand",
        "irrigation": "tube_well",
        "insured": 0,
        "ndvi_early": 0.48,
        "ndvi_pre_cutoff_mean": 0.54,
        "ndvi_pre_cutoff_std": 0.04,
        "ndvi_trend_pre_cutoff": 0.015,
        "rain_pre_cutoff_total_mm": 12.0,
        "rain_pre_cutoff_deficit_pct": 14.3,
        "mandi_pre_cutoff_volatility": 0.045,
        "past_stressed_seasons_count": 0,
        "prev_season_ndvi_peak": 0.65,
        "area_acre": 3.0,
    }
    pd.DataFrame([dummy_row]).to_csv(csv_path, index=False)

    import io

    stdout_capture = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout_capture)

    exit_code = score_cli_main(
        [
            "--plot",
            "TEST_PLOT_01",
            "--season",
            "2024-25",
            "--features-csv",
            str(csv_path),
            "--suggest-loan",
            "--area-acre",
            "3.0",
        ]
    )

    assert exit_code == 0
    output = stdout_capture.getvalue()
    parsed = json.loads(output)

    assert parsed["status"] == "ok"
    assert parsed["plot_code"] == "TEST_PLOT_01"
    assert parsed["area_acre"] == 3.0
    assert parsed["limit_band"]["gross_scale_limit_inr"] == 96_000
    assert parsed["repayment_schedule"]["repayment_month"] == "May"
    assert parsed["disclaimer"] == DISCLAIMER_LOAN_SUGGESTION
