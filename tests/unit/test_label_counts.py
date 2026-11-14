"""Unit test for label_counts analysis script and feasibility gate logic."""

from pathlib import Path

import pandas as pd
import pytest

from scripts.analysis.label_counts import generate_label_counts


@pytest.fixture
def synthetic_label_counts_fixture(tmp_path: Path) -> dict[str, Path]:
    """Create a minimal synthetic fixture for label counts testing."""
    plots_csv = tmp_path / "sample_plots.csv"
    plots_df = pd.DataFrame(
        [
            {"plot_code": "PLOT_01", "status": "active"},
            {"plot_code": "PLOT_02", "status": "active"},
            {"plot_code": "PLOT_03", "status": "borderline"},
        ]
    )
    plots_df.to_csv(plots_csv, index=False)

    season_csv = tmp_path / "season_dataset.csv"
    season_df = pd.DataFrame(
        [
            {"plot_code": "PLOT_01", "season": "2020-21"},
            {"plot_code": "PLOT_01", "season": "2021-22"},
            {"plot_code": "PLOT_02", "season": "2020-21"},
            {"plot_code": "PLOT_02", "season": "2021-22"},
            {"plot_code": "PLOT_03", "season": "2020-21"},
            {"plot_code": "PLOT_03", "season": "2021-22"},
        ]
    )
    season_df.to_csv(season_csv, index=False)

    features_csv = tmp_path / "features.csv"
    features_df = pd.DataFrame(
        [
            {
                "plot_code": "PLOT_01",
                "season": "2020-21",
                "label_unavailable": True,
                "stressed": None,
                "peak_drop_pct": None,
                "ndvi_early": 0.40,
                "rain_pre_cutoff_deficit_pct": 0.0,
            },
            {
                "plot_code": "PLOT_01",
                "season": "2021-22",
                "label_unavailable": False,
                "stressed": 0,
                "peak_drop_pct": 5.0,
                "ndvi_early": 0.45,
                "rain_pre_cutoff_deficit_pct": 10.0,
            },
            {
                "plot_code": "PLOT_02",
                "season": "2020-21",
                "label_unavailable": True,
                "stressed": None,
                "peak_drop_pct": None,
                "ndvi_early": 0.35,
                "rain_pre_cutoff_deficit_pct": 0.0,
            },
            {
                "plot_code": "PLOT_02",
                "season": "2021-22",
                "label_unavailable": False,
                "stressed": 1,
                "peak_drop_pct": 18.0,
                "ndvi_early": 0.25,
                "rain_pre_cutoff_deficit_pct": -25.0,
            },
            {
                "plot_code": "PLOT_03",
                "season": "2020-21",
                "label_unavailable": True,
                "stressed": None,
                "peak_drop_pct": None,
                "ndvi_early": 0.38,
                "rain_pre_cutoff_deficit_pct": 0.0,
            },
            {
                "plot_code": "PLOT_03",
                "season": "2021-22",
                "label_unavailable": False,
                "stressed": 0,
                "peak_drop_pct": 2.0,
                "ndvi_early": 0.42,
                "rain_pre_cutoff_deficit_pct": 5.0,
            },
        ]
    )
    features_df.to_csv(features_csv, index=False)

    return {
        "plots_csv": plots_csv,
        "season_csv": season_csv,
        "features_csv": features_csv,
    }


def test_generate_label_counts_synthetic(
    tmp_path: Path, synthetic_label_counts_fixture: dict[str, Path]
) -> None:
    """Verify generate_label_counts logic and determinism on synthetic fixture."""
    fix = synthetic_label_counts_fixture
    out1 = tmp_path / "counts1.json"
    out2 = tmp_path / "counts2.json"

    res1 = generate_label_counts(fix["features_csv"], fix["plots_csv"], fix["season_csv"], out1)
    res2 = generate_label_counts(fix["features_csv"], fix["plots_csv"], fix["season_csv"], out2)

    # Exclude dynamic timestamp before comparison
    del res1["metadata"]["generated_at_utc"]
    del res2["metadata"]["generated_at_utc"]

    assert res1 == res2

    # Structural assertions
    assert "label_counts" in res1
    assert "feasibility_gate" in res1
    assert "rules_baseline_descriptive_on_stressed" in res1
    assert "robustness" in res1

    counts = res1["label_counts"]
    assert counts["active_plots_count"] == 2
    assert counts["total_labelled_rows"] == 3
    assert counts["total_stressed_count"] == 1
    assert counts["total_normal_count"] == 2

    gate = res1["feasibility_gate"]
    assert gate["status"] == "NOT EVALUABLE"
    assert gate["gate_passed"] is False
    assert gate["ml_action"] == "FREEZE_ML_TRAINING"
    assert gate["active_scorer"] == "AgronomicRulesBaseline"

    rules = res1["rules_baseline_descriptive_on_stressed"]
    assert rules["disclaimer"] == "n = 4, descriptive only, no inference"
    assert len(rules["rows"]) == 1
    assert rules["rows"][0]["plot_code"] == "PLOT_02"
    assert rules["rows"][0]["baseline_risk_band"] == "high"


def test_generate_label_counts_real_data(tmp_path: Path) -> None:
    """Verify generate_label_counts against real active dataset if present in environment."""
    features_csv = Path("data/processed/features.csv")
    plots_csv = Path("data/synthetic/sample_plots.csv")
    season_csv = Path("data/processed/season_dataset.csv")

    if not (features_csv.is_file() and plots_csv.is_file() and season_csv.is_file()):
        pytest.skip("Processed dataset CSVs not present in environment (e.g. CI runner)")

    out = tmp_path / "counts_real.json"
    res = generate_label_counts(features_csv, plots_csv, season_csv, out)

    # Exact data assertions
    counts = res["label_counts"]
    assert counts["active_plots_count"] == 21
    assert counts["total_labelled_rows"] == 84
    assert counts["total_stressed_count"] == 4
    assert counts["total_normal_count"] == 80
    assert counts["overall_stressed_rate_pct"] == 4.76

    # Feasibility gate assertions
    gate = res["feasibility_gate"]
    assert gate["status"] == "NOT EVALUABLE"
    assert gate["gate_passed"] is False
    assert gate["ml_action"] == "FREEZE_ML_TRAINING"
    assert gate["active_scorer"] == "AgronomicRulesBaseline"

    # Rules baseline assertions
    rules = res["rules_baseline_descriptive_on_stressed"]
    assert rules["disclaimer"] == "n = 4, descriptive only, no inference"
    assert len(rules["rows"]) == 4
