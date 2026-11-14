"""Unit test for NDVI summary generator determinism and integrity (Rule 10)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.analysis.ndvi_summary import generate_ndvi_summary


@pytest.fixture
def sample_summary_fixture(tmp_path: Path):
    """Create a minimal synthetic fixture for ndvi_summary generator."""
    # 1. Plots CSV
    plots_csv = tmp_path / "sample_plots.csv"
    plots_df = pd.DataFrame(
        [
            {"plot_code": "PLOT_A", "lat": 22.5, "lon": 72.9, "district": "Anand", "crop": "wheat"},
            {"plot_code": "PLOT_B", "lat": 22.6, "lon": 73.0, "district": "Anand", "crop": "wheat"},
        ]
    )
    plots_df.to_csv(plots_csv, index=False)

    # 2. Season Dataset CSV
    season_csv = tmp_path / "season_dataset.csv"
    season_df = pd.DataFrame(
        [
            {"plot_code": "PLOT_A", "season": "2020-21", "ndvi_peak": 0.60},
            {"plot_code": "PLOT_A", "season": "2021-22", "ndvi_peak": 0.65},
            {"plot_code": "PLOT_B", "season": "2020-21", "ndvi_peak": 0.20},
            {"plot_code": "PLOT_B", "season": "2021-22", "ndvi_peak": 0.22},
        ]
    )
    season_df.to_csv(season_csv, index=False)

    # 3. Features CSV
    features_csv = tmp_path / "features.csv"
    features_df = pd.DataFrame(
        [
            {
                "plot_code": "PLOT_A",
                "season": "2021-22",
                "label_unavailable": False,
                "stressed": 0,
                "peak_drop_pct": -8.33,
            },
            {
                "plot_code": "PLOT_B",
                "season": "2021-22",
                "label_unavailable": False,
                "stressed": 1,
                "peak_drop_pct": 18.0,
            },
        ]
    )
    features_df.to_csv(features_csv, index=False)

    # 4. Satellite Cache JSONs
    sat_dir = tmp_path / "satellite"
    sat_dir.mkdir()

    # V2 files
    obs_a = [
        {
            "date": "2022-01-15",
            "ndvi": 0.55,
            "is_valid": True,
            "processing_baseline": "03.00",
            "offset_applied": 0,
            "offset_rule": "baseline",
        },
        {
            "date": "2022-01-27",
            "ndvi": 0.65,
            "is_valid": True,
            "processing_baseline": "04.00",
            "offset_applied": -1000,
            "offset_rule": "baseline",
        },
    ]
    with open(sat_dir / "PLOT_A_2021-22_v2_pb_offset_corrected.json", "w", encoding="utf-8") as f:
        json.dump(obs_a, f)

    obs_b = [
        {
            "date": "2022-01-15",
            "ndvi": 0.18,
            "is_valid": True,
            "processing_baseline": "03.00",
            "offset_applied": 0,
            "offset_rule": "baseline",
        },
        {
            "date": "2022-01-27",
            "ndvi": 0.22,
            "is_valid": True,
            "processing_baseline": "04.00",
            "offset_applied": -1000,
            "offset_rule": "baseline",
        },
    ]
    with open(sat_dir / "PLOT_B_2021-22_v2_pb_offset_corrected.json", "w", encoding="utf-8") as f:
        json.dump(obs_b, f)

    return {
        "season_csv": season_csv,
        "features_csv": features_csv,
        "plots_csv": plots_csv,
        "sat_dir": sat_dir,
        "output_json": tmp_path / "summary.json",
    }


def test_ndvi_summary_determinism_and_structure(sample_summary_fixture: dict[str, Path]):
    """Assert ndvi_summary runs deterministically and populates all required sections."""
    fix = sample_summary_fixture

    out1 = fix["sat_dir"].parent / "out1.json"
    out2 = fix["sat_dir"].parent / "out2.json"

    res1 = generate_ndvi_summary(
        season_dataset_path=fix["season_csv"],
        features_path=fix["features_csv"],
        satellite_dir=fix["sat_dir"],
        plots_path=fix["plots_csv"],
        output_path=out1,
    )

    res2 = generate_ndvi_summary(
        season_dataset_path=fix["season_csv"],
        features_path=fix["features_csv"],
        satellite_dir=fix["sat_dir"],
        plots_path=fix["plots_csv"],
        output_path=out2,
    )

    # Exclude dynamic timestamp before comparison
    del res1["metadata"]["generated_at_utc"]
    del res2["metadata"]["generated_at_utc"]

    # Assert exact bit-for-bit equivalence (determinism)
    assert res1 == res2

    # Assert required top-level keys
    assert "metadata" in res1
    assert "peak_ndvi_comparison" in res1
    assert "offset_rules_by_season" in res1
    assert "per_plot_summary" in res1
    assert "cohort_seasonal_means" in res1
    assert "stress_label_counts" in res1
    assert "threshold_sensitivity" in res1
    assert "january_same_window_analysis" in res1

    # Assert specific data assertions
    assert res1["metadata"]["sample_plot_count"] == 2
    assert len(res1["per_plot_summary"]) == 2

    # Check plot B classified as non_crop_suspect (all peaks < 0.30)
    plot_b = next(p for p in res1["per_plot_summary"] if p["plot_code"] == "PLOT_B")
    assert plot_b["non_crop_suspect"] is True
    assert plot_b["max_peak"] == 0.22

    # Check stress counts
    counts = res1["stress_label_counts"]["all_24_plots"]
    assert counts["overall_labelled_rows"] == 2
    assert counts["overall_stressed_count"] == 1
    assert counts["overall_stressed_rate_pct"] == 50.0

    # Check January window
    jan_data = res1["january_same_window_analysis"]
    assert len(jan_data) > 0
