"""Deterministic, label-blind analysis script reviewing scoring thresholds (Stage A).

Strictly enforces Label Blindness (Hard Rule):
- Drops 'stressed' and 'label_unavailable' columns immediately on load.
- Evaluates feature distributions, current threshold flag rates, and same-date natural
  variability without reference to any stress label or evaluation target.
- Generates reports/scorer_review.json with input data hashes under Rule 10.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file if it exists, else return empty string."""
    if not path.is_file():
        return ""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_quantiles(series: pd.Series) -> dict[str, float | None]:
    """Compute standard summary statistics and quantiles for a numeric series."""
    valid = series.dropna()
    if valid.empty:
        return {
            "count": 0,
            "missing_count": int(series.isna().sum()),
            "mean": None,
            "std": None,
            "min": None,
            "p10": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p90": None,
            "max": None,
        }
    return {
        "count": int(len(valid)),
        "missing_count": int(series.isna().sum()),
        "mean": round(float(valid.mean()), 4),
        "std": round(float(valid.std()), 4) if len(valid) > 1 else 0.0,
        "min": round(float(valid.min()), 4),
        "p10": round(float(np.percentile(valid, 10)), 4),
        "p25": round(float(np.percentile(valid, 25)), 4),
        "median": round(float(np.percentile(valid, 50)), 4),
        "p75": round(float(np.percentile(valid, 75)), 4),
        "p90": round(float(np.percentile(valid, 90)), 4),
        "max": round(float(valid.max()), 4),
    }


def compute_natural_variability(
    obs_df: pd.DataFrame,
    metric_name: str,
    active_plots: list[str],
) -> dict[str, Any]:
    """Compute distribution of relative difference vs plot's strictly earlier seasons."""
    diff_records = []
    for p in active_plots:
        p_df = obs_df[obs_df["plot_code"] == p].sort_values("season")
        history: list[float] = []
        for _, row in p_df.iterrows():
            val = row.get(metric_name)
            s = row["season"]
            if history and val is not None and not pd.isna(val):
                baseline = float(np.mean(history))
                if baseline > 0.05:  # Avoid division by trivial baseline
                    rel_diff_pct = (val - baseline) / baseline * 100.0
                    rel_drop_pct = (baseline - val) / baseline * 100.0
                    diff_records.append(
                        {
                            "plot_code": p,
                            "season": s,
                            "n_prior": len(history),
                            "val": val,
                            "baseline": baseline,
                            "rel_diff_pct": rel_diff_pct,
                            "rel_drop_pct": rel_drop_pct,
                        }
                    )
            if val is not None and not pd.isna(val):
                history.append(float(val))

    if not diff_records:
        return {"n_evaluations": 0, "overall": {}, "by_prior_season_count": {}}

    res_df = pd.DataFrame(diff_records)
    all_diffs = res_df["rel_diff_pct"]
    med = float(np.median(all_diffs))
    mad = float(np.median(np.abs(all_diffs - med)))

    overall = {
        "n_transitions": len(all_diffs),
        "min": round(float(all_diffs.min()), 2),
        "p10": round(float(np.percentile(all_diffs, 10)), 2),
        "p25": round(float(np.percentile(all_diffs, 25)), 2),
        "median": round(med, 2),
        "p75": round(float(np.percentile(all_diffs, 75)), 2),
        "p90": round(float(np.percentile(all_diffs, 90)), 2),
        "max": round(float(all_diffs.max()), 2),
        "mad": round(mad, 2),
    }

    by_k: dict[str, Any] = {}
    for k in sorted(res_df["n_prior"].unique()):
        sub = res_df[res_df["n_prior"] == k]["rel_diff_pct"]
        k_med = float(np.median(sub))
        k_mad = float(np.median(np.abs(sub - k_med)))
        by_k[f"prior_seasons_{k}"] = {
            "n_transitions": len(sub),
            "min": round(float(sub.min()), 2),
            "p10": round(float(np.percentile(sub, 10)), 2),
            "median": round(k_med, 2),
            "p90": round(float(np.percentile(sub, 90)), 2),
            "max": round(float(sub.max()), 2),
            "mad": round(k_mad, 2),
        }

    return {
        "metric": metric_name,
        "n_evaluations": len(res_df),
        "overall": overall,
        "by_prior_season_count": by_k,
    }


def generate_scorer_review(
    features_path: Path,
    plots_path: Path,
    satellite_dir: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Execute label-blind review of current rules baseline and input distributions."""
    raw_features_df = pd.read_csv(features_path)
    plots_df = pd.read_csv(plots_path)

    # -----------------------------------------------------------------------
    # LABEL BLINDNESS ENFORCEMENT (Hard Rule)
    # -----------------------------------------------------------------------
    # Immediately drop all label and outcome proxy columns upon load.
    forbidden_label_columns = [
        "stressed",
        "label_unavailable",
        "peak_drop_pct",
        "historical_baseline_ndvi",
        "ndvi_peak",
    ]
    blind_features_df = raw_features_df.drop(
        columns=[c for c in forbidden_label_columns if c in raw_features_df.columns]
    ).copy()

    # Assert that no label columns exist in the working DataFrame
    for col in forbidden_label_columns:
        if col in blind_features_df.columns:
            raise ValueError(f"Label blindness violation: column '{col}' retained in working frame")

    # Filter to active plots
    active_plots = (
        plots_df[plots_df["status"] == "active"]["plot_code"].tolist()
        if "status" in plots_df.columns
        else plots_df["plot_code"].tolist()
    )
    active_plots = sorted(active_plots)
    features_active = blind_features_df[blind_features_df["plot_code"].isin(active_plots)].copy()

    # -----------------------------------------------------------------------
    # A2. Distributions of Scorer Inputs on Corrected Data (All 105 Rows)
    # -----------------------------------------------------------------------
    numeric_inputs = [
        "ndvi_early",
        "ndvi_pre_cutoff_mean",
        "ndvi_pre_cutoff_std",
        "ndvi_trend_pre_cutoff",
        "rain_pre_cutoff_total_mm",
        "rain_pre_cutoff_deficit_pct",
        "mandi_pre_cutoff_volatility",
        "past_stressed_seasons_count",
        "prev_season_ndvi_peak",
        "area_acre",
    ]

    input_distributions: dict[str, Any] = {}
    for col in numeric_inputs:
        if col in features_active.columns:
            input_distributions[col] = compute_quantiles(features_active[col])

    # Categorical distributions
    categoricals: dict[str, Any] = {}
    if "irrigation" in features_active.columns:
        categoricals["irrigation"] = features_active["irrigation"].value_counts().to_dict()
    if "insured" in features_active.columns:
        categoricals["insured"] = features_active["insured"].value_counts().to_dict()

    # -----------------------------------------------------------------------
    # Flag Counts under CURRENT AgronomicRulesBaseline Thresholds
    # -----------------------------------------------------------------------
    # Current Thresholds:
    # Condition 1a: ndvi_early <= 0.35
    # Condition 1b: ndvi_trend_pre_cutoff <= 0.0
    # Condition 1 (Vegetative Lag): 1a OR 1b
    # Condition 2 (Rain Deficit): rain_pre_cutoff_deficit_pct <= -20.0
    # Compound: Cond 1 AND Cond 2 (p=0.85 -> high band)
    # Partial: (Cond 1 OR Cond 2) & ~Compound (p=0.45 -> medium band)
    # Normal: ~Cond 1 & ~Cond 2 (p=0.10 -> low band)

    cond1a = features_active["ndvi_early"] <= 0.35
    cond1b = features_active["ndvi_trend_pre_cutoff"] <= 0.0
    cond1 = cond1a | cond1b
    cond2 = features_active["rain_pre_cutoff_deficit_pct"] <= -20.0
    compound = cond1 & cond2
    partial = (cond1 | cond2) & ~compound
    normal = ~cond1 & ~cond2

    total_rows = len(features_active)
    seasons = sorted(features_active["season"].unique().tolist())

    current_rules_flags = {
        "overall_summary": {
            "total_plot_seasons": total_rows,
            "cond1a_ndvi_early_le_035": {
                "flagged_count": int(cond1a.sum()),
                "flagged_pct": round(float(cond1a.sum()) / total_rows * 100.0, 2),
            },
            "cond1b_ndvi_trend_le_0": {
                "flagged_count": int(cond1b.sum()),
                "flagged_pct": round(float(cond1b.sum()) / total_rows * 100.0, 2),
            },
            "cond1_vegetative_lag_combined": {
                "flagged_count": int(cond1.sum()),
                "flagged_pct": round(float(cond1.sum()) / total_rows * 100.0, 2),
            },
            "cond2_rain_deficit_le_minus20": {
                "flagged_count": int(cond2.sum()),
                "flagged_pct": round(float(cond2.sum()) / total_rows * 100.0, 2),
            },
            "compound_stress_high_band": {
                "flagged_count": int(compound.sum()),
                "flagged_pct": round(float(compound.sum()) / total_rows * 100.0, 2),
            },
            "partial_stress_medium_band": {
                "flagged_count": int(partial.sum()),
                "flagged_pct": round(float(partial.sum()) / total_rows * 100.0, 2),
            },
            "normal_growth_low_band": {
                "flagged_count": int(normal.sum()),
                "flagged_pct": round(float(normal.sum()) / total_rows * 100.0, 2),
            },
        },
        "by_season": [],
    }

    # Per-season breakdown
    for s in seasons:
        s_mask = features_active["season"] == s
        s_n = int(s_mask.sum())
        current_rules_flags["by_season"].append(
            {
                "season": s,
                "n_rows": s_n,
                "cond1a_flagged": int((s_mask & cond1a).sum()),
                "cond1b_flagged": int((s_mask & cond1b).sum()),
                "cond1_flagged": int((s_mask & cond1).sum()),
                "cond2_flagged": int((s_mask & cond2).sum()),
                "band_high": int((s_mask & compound).sum()),
                "band_medium": int((s_mask & partial).sum()),
                "band_low": int((s_mask & normal).sum()),
            }
        )

    # Permanent flags: plots flagged in EVERY season (5 out of 5 seasons)
    n_seasons_total = len(seasons)
    permanent_cond1a_plots = []
    permanent_cond1b_plots = []
    permanent_cond1_plots = []
    permanent_cond2_plots = []
    permanent_non_low_plots = []

    for p in active_plots:
        p_mask = features_active["plot_code"] == p
        if (p_mask & cond1a).sum() == n_seasons_total:
            permanent_cond1a_plots.append(p)
        if (p_mask & cond1b).sum() == n_seasons_total:
            permanent_cond1b_plots.append(p)
        if (p_mask & cond1).sum() == n_seasons_total:
            permanent_cond1_plots.append(p)
        if (p_mask & cond2).sum() == n_seasons_total:
            permanent_cond2_plots.append(p)
        if (p_mask & (compound | partial)).sum() == n_seasons_total:
            permanent_non_low_plots.append(p)

    permanent_flags = {
        "n_active_plots": len(active_plots),
        "total_seasons": n_seasons_total,
        "plots_flagged_every_season_cond1a": permanent_cond1a_plots,
        "plots_flagged_every_season_cond1b": permanent_cond1b_plots,
        "plots_flagged_every_season_cond1_vegetative": permanent_cond1_plots,
        "plots_flagged_every_season_cond2_rainfall": permanent_cond2_plots,
        "plots_flagged_every_season_non_low_band": permanent_non_low_plots,
    }

    # -----------------------------------------------------------------------
    # A3. Same-Date Natural Variability at Cut-off Window
    # -----------------------------------------------------------------------
    # Compile cut-off window observations from raw corrected satellite caches
    sat_records = []
    sat_p = satellite_dir or Path("data/raw/satellite")
    if sat_p.exists():
        for p in active_plots:
            for s in seasons:
                cfile = sat_p / f"{p}_{s}_v2_pb_offset_corrected.json"
                if cfile.exists():
                    with open(cfile, encoding="utf-8") as f:
                        obs_list = json.load(f)
                    valid_obs = [
                        o for o in obs_list if o.get("is_valid") and o.get("ndvi") is not None
                    ]
                    # Window 15-31 January (mid-late January cut-off window)
                    mid_late_jan = [o for o in valid_obs if "01-15" <= o["date"][5:10] <= "01-31"]
                    # Window 25-31 January (late January window)
                    late_jan = [o for o in valid_obs if "01-25" <= o["date"][5:10] <= "01-31"]
                    # Pre-cutoff mean (all <= Jan 31)
                    pre_cutoff = [o for o in valid_obs if o["date"][5:10] <= "01-31"]
                    sat_records.append(
                        {
                            "plot_code": p,
                            "season": s,
                            "ndvi_15_31_jan": float(np.mean([o["ndvi"] for o in mid_late_jan]))
                            if mid_late_jan
                            else None,
                            "ndvi_late_jan": float(np.mean([o["ndvi"] for o in late_jan]))
                            if late_jan
                            else None,
                            "ndvi_pre_cutoff": float(np.mean([o["ndvi"] for o in pre_cutoff]))
                            if pre_cutoff
                            else None,
                        }
                    )

    sat_df = pd.DataFrame(sat_records) if sat_records else pd.DataFrame()

    variability_15_31_jan = (
        compute_natural_variability(sat_df, "ndvi_15_31_jan", active_plots)
        if not sat_df.empty
        else {}
    )
    variability_pre_cutoff = (
        compute_natural_variability(sat_df, "ndvi_pre_cutoff", active_plots)
        if not sat_df.empty
        else {}
    )

    # Also compute natural variability of ndvi_early from features_active
    variability_ndvi_early = compute_natural_variability(
        features_active[["plot_code", "season", "ndvi_early"]],
        "ndvi_early",
        active_plots,
    )

    # -----------------------------------------------------------------------
    # Final Payload Assembly
    # -----------------------------------------------------------------------
    result: dict[str, Any] = {
        "metadata": {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "generator_command": "python scripts/analysis/scorer_review.py",
            "rule": "Rule 10 (Strict Numerical Traceability) & Label Blindness",
            "data_hashes": {
                "features_csv_sha256": compute_file_sha256(features_path),
                "plots_csv_sha256": compute_file_sha256(plots_path),
            },
            "active_plots_count": len(active_plots),
            "total_plot_seasons": total_rows,
            "label_blindness_verified": True,
            "dropped_columns": forbidden_label_columns,
        },
        "input_distributions": {
            "numeric": input_distributions,
            "categorical": categoricals,
        },
        "current_rules_flags": current_rules_flags,
        "permanent_flags": permanent_flags,
        "same_date_natural_variability": {
            "window_15_31_jan": variability_15_31_jan,
            "pre_cutoff_mean": variability_pre_cutoff,
            "ndvi_early": variability_ndvi_early,
        },
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)

    return result


def main() -> None:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Deterministic label-blind scorer review analysis."
    )
    parser.add_argument(
        "--features-path",
        type=Path,
        default=Path("data/processed/features.csv"),
        help="Path to processed features CSV.",
    )
    parser.add_argument(
        "--plots-path",
        type=Path,
        default=Path("data/synthetic/sample_plots.csv"),
        help="Path to sample plots CSV.",
    )
    parser.add_argument(
        "--satellite-dir",
        type=Path,
        default=Path("data/raw/satellite"),
        help="Path to raw satellite observation cache directory.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("reports/scorer_review.json"),
        help="Path to output JSON report.",
    )
    args = parser.parse_args()

    result = generate_scorer_review(
        features_path=args.features_path,
        plots_path=args.plots_path,
        satellite_dir=args.satellite_dir,
        output_path=args.output_path,
    )
    print(
        f"Scorer review generated: {args.output_path} "
        f"({result['metadata']['active_plots_count']} plots, "
        f"{result['metadata']['total_plot_seasons']} plot-seasons, label-blindness verified)."
    )


if __name__ == "__main__":
    main()
