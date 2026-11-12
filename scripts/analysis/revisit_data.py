"""Read-only data revisit analysis for SatBhoomi (post T-06).

Inspects data/processed/season_dataset.csv, data/processed/features.csv,
data/external/district_yield_wheat.csv, and data/raw/satellite/*.json without
modifying any data, label rule, threshold, feature, or model artifact.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from satbhoomi.features.config import FEATURE_COLUMNS


@dataclass(frozen=True)
class AnalysisPaths:
    """Input paths for the read-only data revisit analysis."""

    season_dataset_csv: Path = Path("data/processed/season_dataset.csv")
    features_csv: Path = Path("data/processed/features.csv")
    district_yield_csv: Path = Path("data/external/district_yield_wheat.csv")
    satellite_dir: Path = Path("data/raw/satellite")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometers between two WGS84 points."""
    r_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    return 2.0 * r_km * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def analyze_coverage(season_df: pd.DataFrame, features_df: pd.DataFrame) -> dict[str, Any]:
    """Compute plot, location, season, label, gap-rate, and pairwise distance stats."""
    plots = season_df[["plot_code", "lat", "lon", "district", "crop"]].drop_duplicates()
    distinct_locs = plots[["lat", "lon"]].drop_duplicates()
    seasons = sorted(season_df["season"].unique().tolist())

    coords = list(zip(plots["lat"], plots["lon"], strict=True))
    pair_distances_km: list[float] = []
    within_10m_pairs = 0
    within_100m_pairs = 0
    within_1km_pairs = 0
    plots_with_1km_neighbor: set[int] = set()

    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            d_km = haversine_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
            pair_distances_km.append(d_km)
            if d_km <= 0.01:
                within_10m_pairs += 1
            if d_km <= 0.1:
                within_100m_pairs += 1
            if d_km <= 1.0:
                within_1km_pairs += 1
                plots_with_1km_neighbor.add(i)
                plots_with_1km_neighbor.add(j)

    gap_cols = [
        "data_gap_ndvi",
        "data_gap_rainfall",
        "data_gap_price",
        "data_gap_yield",
        "data_gap_any",
    ]
    gap_rates = {
        col: float(season_df[col].astype(bool).mean())
        for col in gap_cols
        if col in season_df.columns
    }

    labelled_rows = int((~features_df["label_unavailable"].astype(bool)).sum())
    unlabelled_rows = int(features_df["label_unavailable"].astype(bool).sum())
    stressed_rows = int((features_df["stressed"] == 1).sum())

    return {
        "n_plots": int(len(plots)),
        "n_distinct_locations": int(len(distinct_locs)),
        "seasons": seasons,
        "n_seasons": int(len(seasons)),
        "total_rows": int(len(features_df)),
        "labelled_rows": labelled_rows,
        "unlabelled_rows": unlabelled_rows,
        "stressed_rows": stressed_rows,
        "gap_rates_season_dataset": gap_rates,
        "n_pairs": len(pair_distances_km),
        "distance_km": {
            "min": round(float(np.min(pair_distances_km)), 4) if pair_distances_km else None,
            "median": round(float(np.median(pair_distances_km)), 4) if pair_distances_km else None,
            "max": round(float(np.max(pair_distances_km)), 4) if pair_distances_km else None,
        },
        "pairs_within_10m": within_10m_pairs,
        "pairs_within_100m": within_100m_pairs,
        "pairs_within_1km": within_1km_pairs,
        "plots_with_neighbor_within_1km": len(plots_with_1km_neighbor),
    }


def analyze_crop_cycles(season_df: pd.DataFrame, satellite_dir: Path) -> dict[str, Any]:
    """Inspect per plot-season raw satellite NDVI curves for rise-peak-fall shape."""
    per_row: list[dict[str, Any]] = []
    flat_count = 0
    low_peak_count = 0
    missing_raw_count = 0

    for _, row in season_df.iterrows():
        plot_code = str(row["plot_code"])
        season = str(row["season"])
        raw_path = satellite_dir / f"{plot_code}_{season}.json"
        if not raw_path.exists():
            missing_raw_count += 1
            per_row.append(
                {
                    "plot_code": plot_code,
                    "season": season,
                    "raw_exists": False,
                    "n_total": 0,
                    "n_valid": 0,
                    "valid_ratio": 0.0,
                    "ndvi_min": None,
                    "ndvi_peak": None,
                    "ndvi_std": None,
                    "peak_date": None,
                    "flags": ["missing_raw_json"],
                }
            )
            continue

        records = json.loads(raw_path.read_text(encoding="utf-8"))
        valid_recs = [r for r in records if r.get("is_valid") and r.get("ndvi") is not None]
        ndvis = [float(r["ndvi"]) for r in valid_recs]
        dates = [str(r["date"]) for r in valid_recs]

        flags: list[str] = []
        if not ndvis:
            flags.append("no_valid_obs")
            ndvi_min = ndvi_peak = ndvi_std = None
            peak_date = None
        else:
            ndvi_min = float(np.min(ndvis))
            ndvi_peak = float(np.max(ndvis))
            ndvi_std = float(np.std(ndvis))
            peak_idx = int(np.argmax(ndvis))
            peak_date = dates[peak_idx]

            if ndvi_peak - ndvi_min < 0.05 or ndvi_std < 0.02:
                flags.append("flat_curve")
                flat_count += 1
            if ndvi_peak < 0.35:
                flags.append("low_peak")
                low_peak_count += 1

        per_row.append(
            {
                "plot_code": plot_code,
                "season": season,
                "raw_exists": True,
                "n_total": len(records),
                "n_valid": len(valid_recs),
                "valid_ratio": round(len(valid_recs) / len(records), 4) if records else 0.0,
                "ndvi_min": round(ndvi_min, 4) if ndvi_min is not None else None,
                "ndvi_peak": round(ndvi_peak, 4) if ndvi_peak is not None else None,
                "ndvi_std": round(ndvi_std, 4) if ndvi_std is not None else None,
                "peak_date": peak_date,
                "flags": flags,
            }
        )

    valid_ratios = [r["valid_ratio"] for r in per_row if r["raw_exists"]]
    return {
        "total_plot_seasons": len(per_row),
        "missing_raw_count": missing_raw_count,
        "flat_curve_count": flat_count,
        "low_peak_count": low_peak_count,
        "raw_valid_ratio_summary": {
            "min": round(float(np.min(valid_ratios)), 4) if valid_ratios else None,
            "median": round(float(np.median(valid_ratios)), 4) if valid_ratios else None,
            "max": round(float(np.max(valid_ratios)), 4) if valid_ratios else None,
        },
        "sample_rows": per_row[:5],
    }


def _distribution_stats(series: pd.Series) -> dict[str, float | int | None]:
    clean = series.dropna().astype(float)
    if clean.empty:
        return {"count": 0, "min": None, "p25": None, "median": None, "p75": None, "max": None}
    return {
        "count": int(len(clean)),
        "min": round(float(clean.min()), 4),
        "p25": round(float(clean.quantile(0.25)), 4),
        "median": round(float(clean.median()), 4),
        "p75": round(float(clean.quantile(0.75)), 4),
        "max": round(float(clean.max()), 4),
    }


def analyze_variability_and_zero_positives(features_df: pd.DataFrame) -> dict[str, Any]:
    """Summarize peak_drop_pct overall and per season, plus margin to 15% threshold."""
    labelled = features_df[~features_df["label_unavailable"].astype(bool)].copy()
    overall = _distribution_stats(labelled["peak_drop_pct"])
    per_season = {
        str(season): _distribution_stats(grp["peak_drop_pct"])
        for season, grp in labelled.groupby("season", sort=True)
    }
    max_drop = float(labelled["peak_drop_pct"].max()) if not labelled.empty else None
    return {
        "overall_peak_drop_pct": overall,
        "per_season_peak_drop_pct": per_season,
        "label_threshold_pct": 15.0,
        "max_observed_drop_pct": max_drop,
        "gap_to_threshold_pct": round(15.0 - max_drop, 4) if max_drop is not None else None,
    }


def analyze_external_checks(
    season_df: pd.DataFrame,
    district_yield_df: pd.DataFrame,
) -> dict[str, Any]:
    """Summarize district wheat yield and seasonal rainfall/price variation."""
    dy = district_yield_df.sort_values("season").copy()
    dy["yoy_yield_change_pct"] = dy["yield_kg_per_ha"].pct_change() * 100.0
    mean_yield = float(dy["yield_kg_per_ha"].mean())
    dy["vs_5yr_mean_pct"] = ((dy["yield_kg_per_ha"] - mean_yield) / mean_yield) * 100.0

    season_weather = (
        season_df.groupby("season", as_index=False)
        .agg(
            rain_total_mm_mean=("rain_total_mm", "mean"),
            rain_deficit_pct_mean=("rain_deficit_pct", "mean"),
            price_mean=("price_mean", "mean"),
            price_volatility=("price_volatility", "mean"),
            ndvi_peak_mean=("ndvi_peak", "mean"),
        )
        .sort_values("season")
    )

    merged = dy.merge(season_weather, on="season", how="left")
    return {
        "district_yield_mean_kg_per_ha": round(mean_yield, 2),
        "seasons": merged.round(4).to_dict(orient="records"),
    }


def analyze_feature_quality(features_df: pd.DataFrame) -> list[dict[str, Any]]:
    """Profile missingness, uniqueness, and summary stats for all 12 model features."""
    rows: list[dict[str, Any]] = []
    n = len(features_df)
    for col in FEATURE_COLUMNS:
        s = features_df[col]
        n_missing = int(s.isna().sum())
        non_null = s.dropna()
        n_unique = int(non_null.nunique())
        is_numeric = bool(pd.api.types.is_numeric_dtype(s))
        rows.append(
            {
                "feature": col,
                "dtype": str(s.dtype),
                "missing_count": n_missing,
                "missing_pct": round((n_missing / n) * 100.0, 2) if n else 0.0,
                "non_null_unique": n_unique,
                "is_constant_non_null": n_unique <= 1,
                "min": round(float(non_null.min()), 4)
                if is_numeric and not non_null.empty
                else None,
                "median": (
                    round(float(non_null.median()), 4)
                    if is_numeric and not non_null.empty
                    else None
                ),
                "max": round(float(non_null.max()), 4)
                if is_numeric and not non_null.empty
                else None,
            }
        )
    return rows


def run_analysis(paths: AnalysisPaths) -> dict[str, Any]:
    """Execute all read-only data revisit checks and return structured summary."""
    season_df = pd.read_csv(paths.season_dataset_csv)
    features_df = pd.read_csv(paths.features_csv)
    district_yield_df = pd.read_csv(paths.district_yield_csv)

    return {
        "coverage": analyze_coverage(season_df, features_df),
        "crop_cycles": analyze_crop_cycles(season_df, paths.satellite_dir),
        "variability": analyze_variability_and_zero_positives(features_df),
        "external_checks": analyze_external_checks(season_df, district_yield_df),
        "feature_quality": analyze_feature_quality(features_df),
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the read-only data revisit analysis."""
    parser = argparse.ArgumentParser(description="SatBhoomi read-only data revisit analysis.")
    parser.add_argument(
        "--season-dataset",
        type=Path,
        default=Path("data/processed/season_dataset.csv"),
    )
    parser.add_argument(
        "--features-csv",
        type=Path,
        default=Path("data/processed/features.csv"),
    )
    parser.add_argument(
        "--district-yield-csv",
        type=Path,
        default=Path("data/external/district_yield_wheat.csv"),
    )
    parser.add_argument(
        "--satellite-dir",
        type=Path,
        default=Path("data/raw/satellite"),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to write structured JSON results.",
    )
    args = parser.parse_args(argv)

    paths = AnalysisPaths(
        season_dataset_csv=args.season_dataset,
        features_csv=args.features_csv,
        district_yield_csv=args.district_yield_csv,
        satellite_dir=args.satellite_dir,
    )
    result = run_analysis(paths)
    payload = json.dumps(result, indent=2)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
