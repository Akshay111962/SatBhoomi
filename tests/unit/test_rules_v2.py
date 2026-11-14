"""Unit tests for approved v2.0 relative rules baseline (Stage B, docs/SCORER_REVIEW.md).

Tests:
1. Season with no prior season (Season 1 2020-21) returns insufficient_data.
2. Permanently low but stable plot is NOT flagged by relative rule.
3. Sharply dropping plot IS flagged by relative rule (moderate and acute).
4. Differentiated rainfall treatment for irrigated vs rainfed plots.
5. All thresholds come strictly from satbhoomi.risk.config.
6. Determinism: identical input yields identical output.
7. Zero PII and zero banned blame/mental health wording in outputs.
"""

from __future__ import annotations

import json
from typing import Any

from satbhoomi.risk import config
from satbhoomi.risk.baseline import AgronomicRulesBaseline
from satbhoomi.risk.config import (
    NDVI_DROP_ACUTE_PCT,
    NDVI_DROP_MODERATE_PCT,
    PROB_ACUTE_STRESS,
    PROB_MODERATE_STRESS,
    PROB_NORMAL,
    RAIN_DEFICIT_MODERATE_PCT,
    RULES_BASELINE_VERSION,
)
from satbhoomi.risk.scoring import (
    map_score_to_band,
    score_plot_season,
)

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
    "guilty",
    "reckless",
    "careless",
    "defaulter",
    "criminal",
    "blame",
)

PII_KEYS: tuple[str, ...] = (
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


def _make_sample_row(**kwargs: Any) -> dict[str, Any]:
    """Helper to create a valid pre-cutoff feature row."""
    base: dict[str, Any] = {
        "plot_code": "ANAND_WHEAT_99",
        "season": "2024-25",
        "crop": "wheat",
        "district": "Anand",
        "ndvi_early": 0.45,
        "ndvi_pre_cutoff_mean": 0.50,
        "ndvi_pre_cutoff_std": 0.04,
        "ndvi_trend_pre_cutoff": 0.015,
        "rain_pre_cutoff_total_mm": 10.0,
        "rain_pre_cutoff_deficit_pct": 0.0,
        "mandi_pre_cutoff_volatility": 0.045,
        "past_stressed_seasons_count": 0,
        "prev_season_ndvi_peak": 0.65,
        "area_acre": 2.5,
        "irrigation": "tube_well",
        "insured": 1,
        "ndvi_pre_cutoff_baseline": 0.50,
        "prior_seasons_count": 2,
    }
    base.update(kwargs)
    return base


def test_season_with_no_prior_season_returns_insufficient_data() -> None:
    """Season 1 (2020-21) or zero prior seasons strictly returns insufficient_data."""
    row_season1 = _make_sample_row(season="2020-21", prior_seasons_count=0)
    res1 = score_plot_season(row_season1)

    assert res1.status == "insufficient_data"
    assert res1.score is None
    assert res1.band is None
    assert res1.reasons == []
    assert (
        res1.insufficient_data_reason
        == "No historical prior seasons available to establish plot baseline"
    )
    assert res1.model_version == RULES_BASELINE_VERSION

    # Arbitrary season with explicit prior_seasons_count = 0
    row_no_history = _make_sample_row(season="2023-24", prior_seasons_count=0)
    res2 = score_plot_season(row_no_history)
    assert res2.status == "insufficient_data"
    assert res2.score is None
    assert res2.band is None


def test_permanently_low_but_stable_plot_not_flagged() -> None:
    """Plot with low but stable vegetative profile across seasons is NOT flagged."""
    # Under old absolute threshold (<= 0.35), ndvi_early 0.24 was permanently flagged.
    # Under relative rule, historical baseline 0.24 vs current 0.24 -> drop = 0.0% -> LOW RISK.
    row_stable_low = _make_sample_row(
        ndvi_early=0.22,
        ndvi_pre_cutoff_mean=0.24,
        ndvi_pre_cutoff_baseline=0.24,
        prior_seasons_count=3,
        irrigation="tube_well",
    )
    res = score_plot_season(row_stable_low)

    assert res.status == "ok"
    assert res.score == int(round(PROB_NORMAL * 100))  # 10
    assert res.band == "low"
    assert res.band == map_score_to_band(res.score)


def test_sharply_dropping_plot_is_flagged_moderate_and_acute() -> None:
    """Relative vegetative collapse flags moderate (>= 15%) and acute (>= 25%) stress."""
    # Baseline = 0.50, current = 0.40 -> drop = 20.0% (Moderate: 15% <= drop < 25%)
    row_moderate = _make_sample_row(
        ndvi_pre_cutoff_baseline=0.50,
        ndvi_pre_cutoff_mean=0.40,
        irrigation="tube_well",
    )
    res_mod = score_plot_season(row_moderate)
    assert res_mod.status == "ok"
    assert res_mod.score == int(round(PROB_MODERATE_STRESS * 100))  # 45
    assert res_mod.band == "medium"

    # Baseline = 0.50, current = 0.35 -> drop = 30.0% (Acute: drop >= 25%)
    row_acute = _make_sample_row(
        ndvi_pre_cutoff_baseline=0.50,
        ndvi_pre_cutoff_mean=0.35,
        irrigation="tube_well",
    )
    res_acute = score_plot_season(row_acute)
    assert res_acute.status == "ok"
    assert res_acute.score == int(round(PROB_ACUTE_STRESS * 100))  # 85
    assert res_acute.band == "high"


def test_differentiated_rainfall_treatment_irrigated_vs_rainfed() -> None:
    """Irrigated plot buffers winter rainfall deficit; rainfed plot flags distress."""
    # Irrigated plot with winter rainfall deficit of -90% (normal winter rain is only 10.5 mm)
    row_irrigated = _make_sample_row(
        ndvi_pre_cutoff_baseline=0.50,
        ndvi_pre_cutoff_mean=0.50,  # drop = 0.0%
        rain_pre_cutoff_deficit_pct=-90.0,
        irrigation="tube_well",
    )
    res_irr = score_plot_season(row_irrigated)
    # Irrigation buffers winter rain deficit -> score remains 10 (low)
    assert res_irr.status == "ok"
    assert res_irr.score == int(round(PROB_NORMAL * 100))  # 10
    assert res_irr.band == "low"

    # Rainfed plot with winter rainfall deficit of -40% (<= -25% threshold)
    row_rainfed = _make_sample_row(
        ndvi_pre_cutoff_baseline=0.50,
        ndvi_pre_cutoff_mean=0.50,  # drop = 0.0%
        rain_pre_cutoff_deficit_pct=-40.0,
        irrigation="rainfed",
    )
    res_rf = score_plot_season(row_rainfed)
    # Rainfed without irrigation suffers moisture stress -> score = 45 (medium)
    assert res_rf.status == "ok"
    assert res_rf.score == int(round(PROB_MODERATE_STRESS * 100))  # 45
    assert res_rf.band == "medium"

    # Compound distress: Rainfed plot with BOTH moderate vegetative lag AND rain deficit
    row_compound = _make_sample_row(
        ndvi_pre_cutoff_baseline=0.50,
        ndvi_pre_cutoff_mean=0.41,  # drop = 18.0% (moderate lag)
        rain_pre_cutoff_deficit_pct=-40.0,  # rain deficit
        irrigation="rainfed",
    )
    res_comp = score_plot_season(row_compound)
    assert res_comp.status == "ok"
    assert res_comp.score == int(round(PROB_ACUTE_STRESS * 100))  # 85
    assert res_comp.band == "high"


def test_thresholds_come_strictly_from_config() -> None:
    """Verify that all baseline and scorer thresholds derive from central config."""
    model = AgronomicRulesBaseline()
    assert model.ndvi_drop_moderate_pct == NDVI_DROP_MODERATE_PCT == 15.0
    assert model.ndvi_drop_acute_pct == NDVI_DROP_ACUTE_PCT == 25.0
    assert model.rain_deficit_moderate_pct == RAIN_DEFICIT_MODERATE_PCT == -25.0
    assert model.prob_high == PROB_ACUTE_STRESS == 0.85
    assert model.prob_medium == PROB_MODERATE_STRESS == 0.45
    assert model.prob_low == PROB_NORMAL == 0.10

    assert config.RULES_BASELINE_VERSION == "satbhoomi-rules-v2.0-relative-20261114"
    assert config.BAND_LOW_MAX == 34
    assert config.BAND_MEDIUM_MAX == 69
    assert config.BAND_HIGH_MIN == 70


def test_scoring_determinism() -> None:
    """Repeated calls with identical input produce bit-for-bit identical results."""
    row = _make_sample_row()
    res1 = score_plot_season(row)
    res2 = score_plot_season(row)
    assert res1 == res2
    assert res1.model_dump() == res2.model_dump()


def test_banned_wording_and_zero_pii() -> None:
    """Outputs must have zero PII and zero banned mental health or blame wording."""
    row = _make_sample_row()
    res = score_plot_season(row)

    payload = json.loads(res.model_dump_json())
    for key in payload:
        assert key.lower() not in PII_KEYS

    all_text = " ".join(res.reasons + [res.interpretation, res.reliability_note]).lower()
    for word in BANNED_WORDS:
        assert word not in all_text, f"Banned word {word!r} found in score explanation!"
