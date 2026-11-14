"""Unit tests for scorer_review analysis script and strict label blindness."""

from pathlib import Path

import pandas as pd
import pytest

from scripts.analysis.scorer_review import generate_scorer_review


@pytest.fixture
def synthetic_scorer_review_fixture(tmp_path: Path) -> dict[str, Path]:
    """Create minimal synthetic fixture for scorer review analysis."""
    plots_csv = tmp_path / "sample_plots.csv"
    plots_df = pd.DataFrame(
        [
            {"plot_code": "PLOT_01", "status": "active"},
            {"plot_code": "PLOT_02", "status": "active"},
        ]
    )
    plots_df.to_csv(plots_csv, index=False)

    features_csv = tmp_path / "features.csv"
    features_df = pd.DataFrame(
        [
            {
                "plot_code": "PLOT_01",
                "season": "2020-21",
                "ndvi_early": 0.40,
                "ndvi_pre_cutoff_mean": 0.50,
                "ndvi_pre_cutoff_std": 0.10,
                "ndvi_trend_pre_cutoff": 0.005,
                "rain_pre_cutoff_total_mm": 5.0,
                "rain_pre_cutoff_deficit_pct": -52.4,
                "mandi_pre_cutoff_volatility": 0.02,
                "past_stressed_seasons_count": 0,
                "prev_season_ndvi_peak": None,
                "area_acre": 2.5,
                "irrigation": "tube_well",
                "insured": 1,
                # Label columns to verify they get dropped
                "stressed": 0,
                "label_unavailable": True,
                "peak_drop_pct": None,
                "historical_baseline_ndvi": None,
                "ndvi_peak": 0.65,
            },
            {
                "plot_code": "PLOT_01",
                "season": "2021-22",
                "ndvi_early": 0.30,  # <= 0.35 flag
                "ndvi_pre_cutoff_mean": 0.45,
                "ndvi_pre_cutoff_std": 0.08,
                "ndvi_trend_pre_cutoff": -0.002,  # <= 0.0 flag
                "rain_pre_cutoff_total_mm": 20.0,
                "rain_pre_cutoff_deficit_pct": 90.5,
                "mandi_pre_cutoff_volatility": 0.04,
                "past_stressed_seasons_count": 0,
                "prev_season_ndvi_peak": 0.65,
                "area_acre": 2.5,
                "irrigation": "tube_well",
                "insured": 1,
                # Label columns
                "stressed": 1,
                "label_unavailable": False,
                "peak_drop_pct": 18.0,
                "historical_baseline_ndvi": 0.65,
                "ndvi_peak": 0.53,
            },
            {
                "plot_code": "PLOT_02",
                "season": "2020-21",
                "ndvi_early": 0.32,
                "ndvi_pre_cutoff_mean": 0.38,
                "ndvi_pre_cutoff_std": 0.05,
                "ndvi_trend_pre_cutoff": 0.001,
                "rain_pre_cutoff_total_mm": 5.0,
                "rain_pre_cutoff_deficit_pct": -52.4,
                "mandi_pre_cutoff_volatility": 0.02,
                "past_stressed_seasons_count": 0,
                "prev_season_ndvi_peak": None,
                "area_acre": 3.0,
                "irrigation": "rainfed",
                "insured": 0,
                # Label columns
                "stressed": 0,
                "label_unavailable": True,
                "peak_drop_pct": None,
                "historical_baseline_ndvi": None,
                "ndvi_peak": 0.42,
            },
            {
                "plot_code": "PLOT_02",
                "season": "2021-22",
                "ndvi_early": 0.28,
                "ndvi_pre_cutoff_mean": 0.35,
                "ndvi_pre_cutoff_std": 0.04,
                "ndvi_trend_pre_cutoff": -0.001,
                "rain_pre_cutoff_total_mm": 0.0,
                "rain_pre_cutoff_deficit_pct": -100.0,  # <= -20% flag
                "mandi_pre_cutoff_volatility": 0.04,
                "past_stressed_seasons_count": 0,
                "prev_season_ndvi_peak": 0.42,
                "area_acre": 3.0,
                "irrigation": "rainfed",
                "insured": 0,
                # Label columns
                "stressed": 1,
                "label_unavailable": False,
                "peak_drop_pct": 20.0,
                "historical_baseline_ndvi": 0.42,
                "ndvi_peak": 0.34,
            },
        ]
    )
    features_df.to_csv(features_csv, index=False)

    return {
        "plots_csv": plots_csv,
        "features_csv": features_csv,
    }


def test_scorer_review_label_blindness_and_determinism(
    tmp_path: Path, synthetic_scorer_review_fixture: dict[str, Path]
) -> None:
    """Verify that generate_scorer_review drops labels and is deterministic."""
    fix = synthetic_scorer_review_fixture
    out1 = tmp_path / "rev1.json"
    out2 = tmp_path / "rev2.json"

    res1 = generate_scorer_review(fix["features_csv"], fix["plots_csv"], output_path=out1)
    res2 = generate_scorer_review(fix["features_csv"], fix["plots_csv"], output_path=out2)

    # Exclude dynamic timestamp before comparison
    del res1["metadata"]["generated_at_utc"]
    del res2["metadata"]["generated_at_utc"]

    assert res1 == res2

    # Verify Label Blindness hard rule
    meta = res1["metadata"]
    assert meta["label_blindness_verified"] is True
    assert "stressed" in meta["dropped_columns"]
    assert "label_unavailable" in meta["dropped_columns"]

    # Structural keys
    assert "input_distributions" in res1
    assert "current_rules_flags" in res1
    assert "permanent_flags" in res1
    assert "same_date_natural_variability" in res1

    # Verify flag calculations
    flags = res1["current_rules_flags"]["overall_summary"]
    assert flags["total_plot_seasons"] == 4
    # Condition 1a (ndvi_early <= 0.35): 3 plot-seasons flagged
    assert flags["cond1a_ndvi_early_le_035"]["flagged_count"] == 3
    # Condition 2 (rain_deficit <= -20%): 3 plot-seasons flagged
    assert flags["cond2_rain_deficit_le_minus20"]["flagged_count"] == 3


def test_scorer_review_real_data(tmp_path: Path) -> None:
    """Verify generate_scorer_review on real active dataset if present in environment."""
    features_csv = Path("data/processed/features.csv")
    plots_csv = Path("data/synthetic/sample_plots.csv")
    sat_dir = Path("data/raw/satellite")

    if not (features_csv.is_file() and plots_csv.is_file()):
        pytest.skip("Features CSV not present in environment (e.g. CI runner)")

    out = tmp_path / "review_real.json"
    res = generate_scorer_review(
        features_csv,
        plots_csv,
        satellite_dir=sat_dir,
        output_path=out,
    )

    meta = res["metadata"]
    assert meta["active_plots_count"] == 21
    assert meta["total_plot_seasons"] == 105
    assert meta["label_blindness_verified"] is True
    assert "stressed" in meta["dropped_columns"]

    # Verify input distributions present
    num_dist = res["input_distributions"]["numeric"]
    assert "ndvi_early" in num_dist
    assert "rain_pre_cutoff_deficit_pct" in num_dist
    assert num_dist["ndvi_early"]["count"] == 105
