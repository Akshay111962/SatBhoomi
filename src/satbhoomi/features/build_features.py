"""Feature engineering pipeline for SatBhoomi Score + Raksha (T-04).

Builds predictive features strictly on or before the in-season cut-off date (January 31).
Guarantees zero look-ahead leakage and clear separation between:
- Metadata columns (plot, season, geography)
- Feature columns (inputs available on or before cutoff date)
- Label columns (outcome proxy label and diagnostics)
"""

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from satbhoomi.connectors.satellite.base import SeasonWindow
from satbhoomi.connectors.satellite.seasons import (
    get_rabi_season_window,
    sort_seasons_chronologically,
)
from satbhoomi.features.config import (
    EXCLUDED_LEAKAGE_COLUMNS,
    FEATURE_COLUMNS,
    METADATA_COLUMNS,
    FeaturePipelineConfig,
)
from satbhoomi.features.label import compute_proxy_labels


def compute_linear_trend(dates: list[date], values: list[float]) -> float | None:
    """Compute linear regression slope (change per day) for a time series.

    Returns None if fewer than 2 valid observations are available.
    """
    if len(dates) < 2 or len(values) < 2 or len(dates) != len(values):
        return None

    # Reference day 0
    t0 = dates[0]
    x = np.array([(d - t0).days for d in dates], dtype=float)
    y = np.array(values, dtype=float)

    # If all x are identical (same day)
    x_var = np.var(x)
    if x_var == 0:
        return 0.0

    slope, _ = np.polyfit(x, y, 1)
    return round(float(slope), 6)


def extract_pre_cutoff_satellite_features(
    raw_obs: list[dict[str, Any]],
    cutoff_date: date,
    window_start: date,
) -> dict[str, float | None]:
    """Extract NDVI statistics strictly for observations on or before cutoff_date."""
    valid_obs: list[tuple[date, float]] = []

    for item in raw_obs:
        d_val = item.get("date")
        if not d_val:
            continue
        if isinstance(d_val, str):
            obs_d = datetime.strptime(d_val[:10], "%Y-%m-%d").date()
        elif isinstance(d_val, date):
            obs_d = d_val
        else:
            continue

        if obs_d > cutoff_date or obs_d < window_start:
            continue

        if not item.get("is_valid", True):
            continue

        ndvi = item.get("ndvi")
        if ndvi is not None and not pd.isna(ndvi):
            valid_obs.append((obs_d, float(ndvi)))

    if not valid_obs:
        return {
            "ndvi_pre_cutoff_mean": None,
            "ndvi_pre_cutoff_std": None,
            "ndvi_trend_pre_cutoff": None,
        }

    valid_obs.sort(key=lambda x: x[0])
    obs_dates = [x[0] for x in valid_obs]
    obs_ndvis = [x[1] for x in valid_obs]

    mean_val = round(float(np.mean(obs_ndvis)), 4)
    std_val = round(float(np.std(obs_ndvis, ddof=1)), 4) if len(obs_ndvis) > 1 else 0.0
    trend_val = compute_linear_trend(obs_dates, obs_ndvis)

    return {
        "ndvi_pre_cutoff_mean": mean_val,
        "ndvi_pre_cutoff_std": std_val,
        "ndvi_trend_pre_cutoff": trend_val,
    }


def compute_mandi_cv(prices: list[float]) -> float | None:
    """Compute sample coefficient of variation (stdev / mean) for pre-cutoff modal prices."""
    valid_prices = [p for p in prices if p is not None and not pd.isna(p) and p > 0]
    if len(valid_prices) < 2:
        return None

    mean_p = float(np.mean(valid_prices))
    if mean_p <= 0:
        return None

    stdev_p = float(np.std(valid_prices, ddof=1))
    return round(stdev_p / mean_p, 4)


def build_feature_dataset(
    season_df: pd.DataFrame,
    config: FeaturePipelineConfig | None = None,
    raw_satellite_dir: Path | None = None,
) -> pd.DataFrame:
    """Build feature dataset and outcome proxy labels strictly respecting the in-season cut-off.

    Parameters
    ----------
    season_df : pd.DataFrame
        Joined multi-source seasonal dataset (e.g. from data/processed/season_dataset.csv).
    config : FeaturePipelineConfig, optional
        Configuration holding cutoff date, label thresholds, and baselines.
    raw_satellite_dir : Path, optional
        Optional path to raw satellite JSON observation cache for detailed scene-level stats.

    Returns
    -------
    pd.DataFrame
        Combined dataset containing metadata, pre-cutoff features, and proxy labels.
    """
    if config is None:
        config = FeaturePipelineConfig()

    # Verify input DataFrame
    required_cols = {"plot_code", "season", "district", "crop", "lat", "lon"}
    missing_req = required_cols - set(season_df.columns)
    if missing_req:
        raise ValueError(f"Input season_df is missing required columns: {sorted(missing_req)}")

    # Sort chronologically by plot_code and season
    unique_seasons = list(season_df["season"].unique())
    sorted_seasons = sort_seasons_chronologically(unique_seasons)
    season_rank = {s: i for i, s in enumerate(sorted_seasons)}

    df = season_df.copy()
    df["_season_rank"] = df["season"].map(season_rank)
    df = df.sort_values(["plot_code", "_season_rank"]).reset_index(drop=True)

    # 1. Validate Cutoff Dates against Season Windows
    for season_name in unique_seasons:
        window: SeasonWindow = get_rabi_season_window(season_name)
        cutoff_d = config.get_cutoff_date(season_name)
        if not window.contains(cutoff_d):
            raise ValueError(
                f"Cut-off date {cutoff_d} falls outside season window "
                f"[{window.start_date} to {window.end_date}] for season '{season_name}'."
            )

    # 2. Compute Outcome Proxy Labels (Option 1: Expanding prior baseline)
    label_df = compute_proxy_labels(
        df,
        drop_threshold_pct=config.drop_threshold_pct,
        min_prior_seasons=config.min_prior_seasons,
    )

    # 3. Construct Features for Each Row
    feature_rows: list[dict[str, Any]] = []

    # Map previous season peaks and past stressed counts per plot
    for plot_code, plot_group in df.groupby("plot_code", sort=False):
        plot_group = plot_group.sort_values("_season_rank")

        # Track history for expanding window features
        past_stressed_count = 0
        prev_peak: float | None = None

        for _, row in plot_group.iterrows():
            season_name = str(row["season"])
            cutoff_d = config.get_cutoff_date(season_name)
            window = get_rabi_season_window(season_name)

            # Metadata
            row_dict: dict[str, Any] = {
                "plot_code": plot_code,
                "season": season_name,
                "district": row.get("district", "Anand"),
                "crop": row.get("crop", "wheat"),
                "lat": row.get("lat"),
                "lon": row.get("lon"),
            }

            # Assigned plot attributes
            # Compute area_acre from buffer_m if area_acre column not directly present
            if "area_acre" in row and not pd.isna(row["area_acre"]):
                area_val = float(row["area_acre"])
            elif "buffer_m" in row and not pd.isna(row["buffer_m"]):
                buf_m = float(row["buffer_m"])
                # Area in acres of circular buffer: pi * r^2 / 4046.86
                area_val = round(math.pi * (buf_m**2) / 4046.86, 2)
            else:
                area_val = 1.94  # Standard default 50m buffer in acres

            row_dict["area_acre"] = area_val
            row_dict["irrigation"] = row.get("irrigation", "tube_well")
            row_dict["insured"] = int(row.get("insured", 0))

            # Historical track record features (strictly prior seasons)
            row_dict["past_stressed_seasons_count"] = past_stressed_count
            row_dict["prev_season_ndvi_peak"] = prev_peak

            # Satellite Vegetative Features (<= Jan 31)
            # ndvi_early is always strictly pre-cutoff (first 6 weeks = Nov 1 to Dec 13)
            row_dict["ndvi_early"] = (
                float(row["ndvi_early"])
                if "ndvi_early" in row and not pd.isna(row["ndvi_early"])
                else None
            )

            # Scene-level pre-cutoff NDVI stats from raw files if available
            sat_stats = {
                "ndvi_pre_cutoff_mean": None,
                "ndvi_pre_cutoff_std": None,
                "ndvi_trend_pre_cutoff": None,
            }
            if raw_satellite_dir and raw_satellite_dir.is_dir():
                # Check for cached JSON: {plot_code}_{season_name}.json or planetary_...
                candidates = [
                    raw_satellite_dir / f"{plot_code}_{season_name}_v2_pb_offset_corrected.json",
                    raw_satellite_dir / f"{plot_code}_{season_name}.json",
                    raw_satellite_dir / f"planetary_{plot_code}_{season_name}.json",
                ]
                for c_file in candidates:
                    if c_file.is_file():
                        try:
                            with open(c_file, encoding="utf-8") as f:
                                raw_scenes = json.load(f)
                            sat_stats = extract_pre_cutoff_satellite_features(
                                raw_scenes, cutoff_d, window.start_date
                            )
                            break
                        except Exception:
                            pass

            # Fallback if raw JSON not parsed: use summary metrics if available
            if sat_stats["ndvi_pre_cutoff_mean"] is None:
                # In summary files where only mean is available and valid
                if "ndvi_mean" in row and not pd.isna(row["ndvi_mean"]):
                    sat_stats["ndvi_pre_cutoff_mean"] = float(row["ndvi_mean"])
                    sat_stats["ndvi_pre_cutoff_std"] = (
                        float(row["ndvi_std"])
                        if "ndvi_std" in row and not pd.isna(row["ndvi_std"])
                        else 0.0
                    )
                    sat_stats["ndvi_trend_pre_cutoff"] = 0.0

            row_dict.update(sat_stats)

            # Rainfall Features (strictly pre-cutoff: Nov, Dec, Jan)
            r_nov = (
                float(row["rain_nov_mm"])
                if "rain_nov_mm" in row and not pd.isna(row["rain_nov_mm"])
                else 0.0
            )
            r_dec = (
                float(row["rain_dec_mm"])
                if "rain_dec_mm" in row and not pd.isna(row["rain_dec_mm"])
                else 0.0
            )
            r_jan = (
                float(row["rain_jan_mm"])
                if "rain_jan_mm" in row and not pd.isna(row["rain_jan_mm"])
                else 0.0
            )

            rain_pre = round(r_nov + r_dec + r_jan, 2)
            row_dict["rain_pre_cutoff_total_mm"] = rain_pre

            # Pre-cutoff rain deficit vs Anand Nov-Jan normal baseline (10.5 mm)
            base_rain = config.baseline_normal_rain_mm
            if base_rain > 0:
                deficit_pct = round(((rain_pre - base_rain) / base_rain) * 100.0, 2)
            else:
                deficit_pct = 0.0
            row_dict["rain_pre_cutoff_deficit_pct"] = deficit_pct

            # Mandi Price Volatility (strictly pre-cutoff: Nov, Dec, Jan modal prices)
            p_nov = (
                float(row["price_nov"])
                if "price_nov" in row and not pd.isna(row["price_nov"])
                else None
            )
            p_dec = (
                float(row["price_dec"])
                if "price_dec" in row and not pd.isna(row["price_dec"])
                else None
            )
            p_jan = (
                float(row["price_jan"])
                if "price_jan" in row and not pd.isna(row["price_jan"])
                else None
            )

            pre_prices = [p for p in [p_nov, p_dec, p_jan] if p is not None]
            row_dict["mandi_pre_cutoff_volatility"] = compute_mandi_cv(pre_prices)

            feature_rows.append(row_dict)

            # Update prior season history trackers for the next season
            # Find the outcome label of the current season from label_df
            match_lbl = label_df[
                (label_df["plot_code"] == plot_code) & (label_df["season"] == season_name)
            ]
            if not match_lbl.empty:
                s_val = match_lbl["stressed"].iloc[0]
                if s_val == 1:
                    past_stressed_count += 1

            if "ndvi_peak" in row and not pd.isna(row["ndvi_peak"]):
                prev_peak = float(row["ndvi_peak"])

    feat_df = pd.DataFrame(feature_rows)

    # Merge labels with features
    final_df = feat_df.merge(label_df, on=["plot_code", "season"], how="inner")

    # Verify no excluded leakage columns leaked into the features dataset
    for col in EXCLUDED_LEAKAGE_COLUMNS:
        if col in FEATURE_COLUMNS:
            raise RuntimeError(
                f"CRITICAL LEAKAGE ERROR: Excluded column '{col}' is present in FEATURE_COLUMNS!"
            )

    # Ensure final column order: Metadata -> Features -> Labels
    final_columns = (
        METADATA_COLUMNS
        + FEATURE_COLUMNS
        + [c for c in label_df.columns if c not in ["plot_code", "season"]]
    )
    return final_df[final_columns]
