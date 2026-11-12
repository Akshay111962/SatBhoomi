"""Unit tests for T-06 risk scoring, bands, and plain-language explanations."""

import json
import math

import numpy as np
import pandas as pd
import pytest

from satbhoomi.features.config import FEATURE_COLUMNS
from satbhoomi.risk.explain import explain_logistic_regression, explain_rules_baseline
from satbhoomi.risk.models import build_logistic_regression
from satbhoomi.risk.reason_templates import (
    OFFICER_RECORDED_PHRASE,
    TEMPLATE_FEATURES,
    render_feature_reason,
)
from satbhoomi.risk.scoring import (
    BAND_LOW_MAX,
    BAND_MEDIUM_MAX,
    FIXED_INTERPRETATION,
    FIXED_RELIABILITY_NOTE,
    MAX_MISSING_FEATURES_ALLOWED,
    RULES_BASELINE_VERSION,
    RiskScoreResult,
    map_score_to_band,
    score_plot_season,
)
from scripts.score_plot import main as score_cli_main

BANNED_MENTAL_OR_BLAME_WORDS: tuple[str, ...] = (
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

PII_FIELD_NAMES: tuple[str, ...] = (
    "aadhaar",
    "pan",
    "phone",
    "mobile",
    "email",
    "bank_account",
    "account_number",
    "farmer_name",
    "address",
)


@pytest.fixture
def healthy_row() -> dict:
    return {
        "plot_code": "ANAND_TEST_01",
        "season": "2024-25",
        "ndvi_early": 0.48,
        "ndvi_pre_cutoff_mean": 0.54,
        "ndvi_pre_cutoff_std": 0.04,
        "ndvi_trend_pre_cutoff": 0.015,
        "rain_pre_cutoff_total_mm": 12.0,
        "rain_pre_cutoff_deficit_pct": 14.3,
        "mandi_pre_cutoff_volatility": 0.045,
        "past_stressed_seasons_count": 0,
        "prev_season_ndvi_peak": 0.65,
        "area_acre": 2.15,
        "irrigation": "tube_well",
        "insured": 1,
    }


@pytest.fixture
def stressed_row() -> dict:
    return {
        "plot_code": "ANAND_TEST_02",
        "season": "2024-25",
        "ndvi_early": 0.28,
        "ndvi_pre_cutoff_mean": 0.34,
        "ndvi_pre_cutoff_std": 0.09,
        "ndvi_trend_pre_cutoff": -0.012,
        "rain_pre_cutoff_total_mm": 4.2,
        "rain_pre_cutoff_deficit_pct": -60.0,
        "mandi_pre_cutoff_volatility": 0.112,
        "past_stressed_seasons_count": 2,
        "prev_season_ndvi_peak": 0.61,
        "area_acre": 1.45,
        "irrigation": "canal",
        "insured": 0,
    }


def test_score_bounds_and_band_boundaries() -> None:
    """Verify score range 0..100 and exact band thresholds."""
    assert map_score_to_band(0) == "low"
    assert map_score_to_band(BAND_LOW_MAX) == "low"
    assert map_score_to_band(BAND_LOW_MAX + 1) == "medium"
    assert map_score_to_band(BAND_MEDIUM_MAX) == "medium"
    assert map_score_to_band(BAND_MEDIUM_MAX + 1) == "high"
    assert map_score_to_band(100) == "high"

    with pytest.raises(ValueError):
        map_score_to_band(-1)
    with pytest.raises(ValueError):
        map_score_to_band(101)


def test_scoring_determinism(stressed_row: dict) -> None:
    """Same input twice produces identical output."""
    r1 = score_plot_season(stressed_row)
    r2 = score_plot_season(stressed_row)
    assert r1 == r2
    assert r1.status == "ok"
    assert r1.score == 85
    assert r1.band == "high"
    assert r1.scorer == "rules_baseline"
    assert r1.model_version == RULES_BASELINE_VERSION


def test_exactly_three_grounded_reasons_and_direction(stressed_row: dict) -> None:
    """Low-NDVI stressed plot returns 3 grounded reasons pointing to stress drivers."""
    res = score_plot_season(stressed_row)
    assert len(res.reasons) == 3

    combined = " ".join(res.reasons).lower()
    # Grounded numbers from stressed_row: ndvi_early=0.28, deficit=-60.0, slope=-0.0120
    assert "0.28" in combined
    assert "-60.0%" in combined
    assert "-0.0120" in combined
    # Direction check: low NDVI explained as low, never as healthy/high
    assert "low" in combined
    assert "healthy" not in res.reasons[0].lower()


def test_rules_baseline_additivity(healthy_row: dict, stressed_row: dict) -> None:
    """Rules baseline contributions + base_value == predicted_probability."""
    for row in (healthy_row, stressed_row):
        exp = explain_rules_baseline(row)
        reconstructed = exp.base_value + sum(exp.contributions.values())
        assert reconstructed == pytest.approx(exp.model_output_value, abs=1e-9)

    # Partial stress (only rainfall deficit)
    partial_row = dict(healthy_row)
    partial_row["rain_pre_cutoff_deficit_pct"] = -35.0
    exp_partial = explain_rules_baseline(partial_row)
    assert exp_partial.predicted_probability == pytest.approx(0.45, abs=1e-9)
    assert exp_partial.base_value + sum(exp_partial.contributions.values()) == pytest.approx(
        0.45, abs=1e-9
    )


def test_logreg_explainer_additivity_on_synthetic_multiclass(
    healthy_row: dict,
    stressed_row: dict,
) -> None:
    """Logistic regression contributions + intercept == logit on synthetic multi-class data."""
    rng = np.random.default_rng(42)
    rows = []
    labels = []
    for i in range(30):
        base = dict(stressed_row if i % 2 == 0 else healthy_row)
        base["ndvi_early"] = float(base["ndvi_early"]) + float(rng.normal(0, 0.03))
        base["rain_pre_cutoff_deficit_pct"] = float(base["rain_pre_cutoff_deficit_pct"]) + float(
            rng.normal(0, 5.0)
        )
        rows.append(base)
        labels.append(1 if i % 2 == 0 else 0)

    X_train = pd.DataFrame(rows)[FEATURE_COLUMNS]
    y_train = np.array(labels)
    model = build_logistic_regression(C=1.0, random_state=42).fit(X_train, y_train)

    exp = explain_logistic_regression(stressed_row, model=model)
    reconstructed_logit = exp.base_value + sum(exp.contributions.values())
    assert reconstructed_logit == pytest.approx(exp.model_output_value, abs=1e-9)
    reconstructed_prob = 1.0 / (1.0 + math.exp(-reconstructed_logit))
    assert reconstructed_prob == pytest.approx(exp.predicted_probability, abs=1e-9)

    res = score_plot_season(
        stressed_row,
        scorer="logreg",
        model=model,
        model_version="satbhoomi-risk-v1.0-logreg-synth-test",
    )
    assert res.status == "ok"
    assert res.scorer == "logreg"
    assert 0 <= res.score <= 100
    assert len(res.reasons) == 3
    assert res.reliability_note == FIXED_RELIABILITY_NOTE


def test_missing_features_tolerance_and_insufficient_data(healthy_row: dict) -> None:
    """Below limit gives warnings + score; above limit gives insufficient_data + no score."""
    # Below/at limit: 2 missing features
    row_2_missing = dict(healthy_row)
    row_2_missing["ndvi_early"] = np.nan
    row_2_missing["prev_season_ndvi_peak"] = None

    res_ok = score_plot_season(row_2_missing)
    assert res_ok.status == "ok"
    assert res_ok.score is not None
    assert res_ok.band is not None
    assert len(res_ok.reasons) == 3
    assert len(res_ok.data_warnings) == 2
    assert any("ndvi_early" in w for w in res_ok.data_warnings)
    assert any("prev_season_ndvi_peak" in w for w in res_ok.data_warnings)
    # Skipped missing features must not appear as reasons
    assert all("Early-season vegetation greenness" not in r for r in res_ok.reasons)

    # Above limit: 3 missing features (> MAX_MISSING_FEATURES_ALLOWED=2)
    row_3_missing = dict(row_2_missing)
    row_3_missing["mandi_pre_cutoff_volatility"] = np.nan
    assert MAX_MISSING_FEATURES_ALLOWED == 2

    res_insuff = score_plot_season(row_3_missing)
    assert res_insuff.status == "insufficient_data"
    assert res_insuff.score is None
    assert res_insuff.band is None
    assert res_insuff.reasons == []
    assert res_insuff.insufficient_data_reason is not None
    assert len(res_insuff.data_warnings) == 3
    assert res_insuff.model_version == RULES_BASELINE_VERSION
    assert res_insuff.interpretation == FIXED_INTERPRETATION
    assert res_insuff.reliability_note == FIXED_RELIABILITY_NOTE


def test_every_feature_has_template_and_no_banned_wording(stressed_row: dict) -> None:
    """Every feature in FEATURE_COLUMNS has a template and passes banned-wording check."""
    assert set(TEMPLATE_FEATURES) == set(FEATURE_COLUMNS)

    for feat in FEATURE_COLUMNS:
        for direction in ("up", "down", "neutral"):
            text = render_feature_reason(
                feat,
                stressed_row[feat],
                direction=direction,
                row_context=stressed_row,
            )
            assert isinstance(text, str) and len(text) > 10
            lower_text = text.lower()
            for banned in BANNED_MENTAL_OR_BLAME_WORDS:
                assert banned not in lower_text, f"Banned word {banned!r} in {text!r}"


def test_assigned_attributes_carry_officer_wording(healthy_row: dict) -> None:
    """Assigned attributes must carry 'as recorded by the officer' wording."""
    for feat in ("area_acre", "irrigation", "insured"):
        for direction in ("up", "down", "neutral"):
            text = render_feature_reason(feat, healthy_row[feat], direction=direction)
            assert OFFICER_RECORDED_PHRASE in text


def test_result_metadata_and_zero_pii(healthy_row: dict) -> None:
    """Result always includes model_version, interpretation, reliability_note, and zero PII."""
    res = score_plot_season(healthy_row)
    assert res.model_version == RULES_BASELINE_VERSION
    assert res.interpretation == FIXED_INTERPRETATION
    assert res.reliability_note == FIXED_RELIABILITY_NOTE

    payload = json.loads(res.model_dump_json())
    assert set(RiskScoreResult.model_fields.keys()) == set(payload.keys())
    lower_keys = {k.lower() for k in payload}
    for pii in PII_FIELD_NAMES:
        assert pii not in lower_keys


def test_score_plot_cli_prints_valid_json(
    tmp_path,
    healthy_row: dict,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI scores a plot-season from a features CSV and prints valid JSON."""
    csv_path = tmp_path / "features.csv"
    row = dict(healthy_row)
    row["plot_code"] = "ANAND_WHEAT_01"
    row["season"] = "2024-25"
    pd.DataFrame([row]).to_csv(csv_path, index=False)

    exit_code = score_cli_main(
        [
            "--plot",
            "ANAND_WHEAT_01",
            "--season",
            "2024-25",
            "--features-csv",
            str(csv_path),
        ]
    )
    assert exit_code == 0
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["plot_code"] == "ANAND_WHEAT_01"
    assert parsed["season"] == "2024-25"
    assert parsed["scorer"] == "rules_baseline"
    assert parsed["reliability_note"] == FIXED_RELIABILITY_NOTE
