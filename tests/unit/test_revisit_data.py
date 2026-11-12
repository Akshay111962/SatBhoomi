"""Smoke tests for scripts/analysis/revisit_data.py."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.analysis.revisit_data import AnalysisPaths, haversine_km, main, run_analysis


def test_haversine_km_zero_and_positive() -> None:
    """Verify haversine distance is zero for identical points and positive otherwise."""
    assert haversine_km(22.5, 72.9, 22.5, 72.9) == 0.0
    assert haversine_km(22.5, 72.9, 22.51, 72.9) > 1.0


def test_revisit_data_smoke_on_synthetic_fixture(tmp_path: Path) -> None:
    """Verify run_analysis and CLI main run offline on synthetic tmp_path inputs."""
    sat_dir = tmp_path / "satellite"
    sat_dir.mkdir(parents=True, exist_ok=True)

    for season, peak in [("2020-21", 0.65), ("2021-22", 0.65)]:
        for plot_code in ["P1", "P2"]:
            recs = [
                {"date": f"{season[:4]}-11-15", "ndvi": 0.25, "is_valid": True},
                {"date": f"{season[:4]}-12-20", "ndvi": peak, "is_valid": True},
            ]
            (sat_dir / f"{plot_code}_{season}.json").write_text(
                json.dumps(recs),
                encoding="utf-8",
            )

    season_df = pd.DataFrame(
        [
            {
                "plot_code": "P1",
                "season": "2020-21",
                "district": "Anand",
                "crop": "wheat",
                "lat": 22.50,
                "lon": 72.90,
                "ndvi_peak": 0.65,
                "rain_total_mm": 120.0,
                "rain_deficit_pct": 515.0,
                "price_mean": 2000.0,
                "price_volatility": 0.01,
                "data_gap_ndvi": False,
                "data_gap_rainfall": False,
                "data_gap_price": False,
                "data_gap_yield": False,
                "data_gap_any": False,
            },
            {
                "plot_code": "P2",
                "season": "2020-21",
                "district": "Anand",
                "crop": "wheat",
                "lat": 22.55,
                "lon": 72.95,
                "ndvi_peak": 0.65,
                "rain_total_mm": 120.0,
                "rain_deficit_pct": 515.0,
                "price_mean": 2000.0,
                "price_volatility": 0.01,
                "data_gap_ndvi": False,
                "data_gap_rainfall": False,
                "data_gap_price": False,
                "data_gap_yield": False,
                "data_gap_any": False,
            },
            {
                "plot_code": "P1",
                "season": "2021-22",
                "district": "Anand",
                "crop": "wheat",
                "lat": 22.50,
                "lon": 72.90,
                "ndvi_peak": 0.65,
                "rain_total_mm": 110.0,
                "rain_deficit_pct": 464.0,
                "price_mean": 2100.0,
                "price_volatility": 0.01,
                "data_gap_ndvi": False,
                "data_gap_rainfall": False,
                "data_gap_price": False,
                "data_gap_yield": False,
                "data_gap_any": False,
            },
            {
                "plot_code": "P2",
                "season": "2021-22",
                "district": "Anand",
                "crop": "wheat",
                "lat": 22.55,
                "lon": 72.95,
                "ndvi_peak": 0.65,
                "rain_total_mm": 110.0,
                "rain_deficit_pct": 464.0,
                "price_mean": 2100.0,
                "price_volatility": 0.01,
                "data_gap_ndvi": False,
                "data_gap_rainfall": False,
                "data_gap_price": False,
                "data_gap_yield": False,
                "data_gap_any": False,
            },
        ]
    )
    season_csv = tmp_path / "season_dataset.csv"
    season_df.to_csv(season_csv, index=False)

    features_df = pd.DataFrame(
        [
            {
                "plot_code": "P1",
                "season": "2020-21",
                "ndvi_early": 0.25,
                "ndvi_pre_cutoff_mean": 0.45,
                "ndvi_pre_cutoff_std": 0.20,
                "ndvi_trend_pre_cutoff": 0.01,
                "rain_pre_cutoff_total_mm": 60.0,
                "rain_pre_cutoff_deficit_pct": 470.0,
                "mandi_pre_cutoff_volatility": 0.005,
                "past_stressed_seasons_count": 0,
                "prev_season_ndvi_peak": None,
                "area_acre": 1.94,
                "irrigation": "tube_well",
                "insured": 1,
                "stressed": None,
                "label_unavailable": True,
                "peak_drop_pct": None,
            },
            {
                "plot_code": "P1",
                "season": "2021-22",
                "ndvi_early": 0.25,
                "ndvi_pre_cutoff_mean": 0.45,
                "ndvi_pre_cutoff_std": 0.20,
                "ndvi_trend_pre_cutoff": 0.01,
                "rain_pre_cutoff_total_mm": 55.0,
                "rain_pre_cutoff_deficit_pct": 420.0,
                "mandi_pre_cutoff_volatility": 0.005,
                "past_stressed_seasons_count": 0,
                "prev_season_ndvi_peak": 0.65,
                "area_acre": 1.94,
                "irrigation": "tube_well",
                "insured": 1,
                "stressed": 0.0,
                "label_unavailable": False,
                "peak_drop_pct": 0.0,
            },
        ]
    )
    features_csv = tmp_path / "features.csv"
    features_df.to_csv(features_csv, index=False)

    yield_df = pd.DataFrame(
        [
            {
                "district": "Anand",
                "season": "2020-21",
                "area_ha": 48200,
                "production_tonnes": 168700,
                "yield_kg_per_ha": 3500,
                "source_name": "Test",
                "source_url": "https://example.org",
                "retrieved_on": "2026-11-04",
            },
            {
                "district": "Anand",
                "season": "2021-22",
                "area_ha": 51400,
                "production_tonnes": 174760,
                "yield_kg_per_ha": 3400,
                "source_name": "Test",
                "source_url": "https://example.org",
                "retrieved_on": "2026-11-04",
            },
        ]
    )
    yield_csv = tmp_path / "district_yield_wheat.csv"
    yield_df.to_csv(yield_csv, index=False)

    out_json = tmp_path / "summary.json"
    summary = run_analysis(
        AnalysisPaths(
            season_dataset_csv=season_csv,
            features_csv=features_csv,
            district_yield_csv=yield_csv,
            satellite_dir=sat_dir,
        )
    )
    assert summary["coverage"]["n_plots"] == 2
    assert summary["variability"]["max_observed_drop_pct"] == 0.0

    rc = main(
        [
            "--season-dataset",
            str(season_csv),
            "--features-csv",
            str(features_csv),
            "--district-yield-csv",
            str(yield_csv),
            "--satellite-dir",
            str(sat_dir),
            "--output-json",
            str(out_json),
        ]
    )
    assert rc == 0
    assert out_json.exists()
