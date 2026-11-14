"""Deterministic NDVI summary generator for SatBhoomi (Rule 10 Traceability).

Generates reports/ndvi_summary.json containing:
1. Per-season peak NDVI before and after PB 04.00 offset correction.
2. Offset rule distribution and processing baseline shares per season.
3. Per-plot min/mean/max peak NDVI across 5 rabi seasons with suspect flags.
4. Seasonal peak NDVI means excluding suspect and borderline cohorts.
5. Stress label incidence and threshold sensitivity under unchanged rules.
6. Same-window January heading check (1-24 Jan vs 25-31 Jan) across 5 seasons.
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


def generate_ndvi_summary(
    season_dataset_path: Path,
    features_path: Path,
    satellite_dir: Path,
    plots_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Deterministically generate the complete NDVI summary metrics dictionary."""
    plots_df = pd.read_csv(plots_path)
    approved_plots = sorted(plots_df["plot_code"].unique().tolist())

    season_df = pd.read_csv(season_dataset_path)
    features_df = pd.read_csv(features_path)

    # 1. Parse raw/cached observations
    # Look for v2 corrected files first
    v2_files = sorted(satellite_dir.glob("*_v2_pb_offset_corrected.json"))
    legacy_files = sorted(
        [
            f
            for f in satellite_dir.glob("*.json")
            if not f.name.endswith("_v2_pb_offset_corrected.json")
        ]
    )

    v2_obs: list[dict[str, Any]] = []
    for f in v2_files:
        fname = f.name.replace("_v2_pb_offset_corrected.json", "")
        plot_code, season = fname.rsplit("_", 1)
        if plot_code not in approved_plots:
            continue
        with open(f, encoding="utf-8") as fp:
            items = json.load(fp)
        for item in items:
            v2_obs.append(
                {
                    "plot_code": plot_code,
                    "season": season,
                    "date": item["date"],
                    "ndvi": item["ndvi"],
                    "is_valid": item.get("is_valid", True),
                    "scl_class": item.get("scl_class"),
                    "processing_baseline": item.get("processing_baseline"),
                    "offset_applied": item.get("offset_applied"),
                    "offset_rule": item.get("offset_rule"),
                }
            )
    df_v2 = pd.DataFrame(v2_obs)

    # Legacy pre-correction peak NDVI
    legacy_peaks: list[dict[str, Any]] = []
    for f in legacy_files:
        fname = f.name.replace(".json", "")
        if "_" not in fname:
            continue
        plot_code, season = fname.rsplit("_", 1)
        if plot_code not in approved_plots:
            continue
        with open(f, encoding="utf-8") as fp:
            items = json.load(fp)
        ndvis = [
            it["ndvi"] for it in items if it.get("is_valid", True) and it.get("ndvi") is not None
        ]
        peak = max(ndvis) if ndvis else np.nan
        legacy_peaks.append({"plot_code": plot_code, "season": season, "legacy_peak": peak})
    df_legacy_peaks = pd.DataFrame(legacy_peaks)

    # 2. Per-Season Peak NDVI Comparison (Pre vs Post)
    seasons = sorted(season_df["season"].unique().tolist())
    peak_comp_rows: list[dict[str, Any]] = []
    for s in seasons:
        post_mean = float(season_df[season_df["season"] == s]["ndvi_peak"].mean())
        if not df_legacy_peaks.empty and "season" in df_legacy_peaks.columns:
            s_leg = df_legacy_peaks[df_legacy_peaks["season"] == s]["legacy_peak"]
            pre_mean = float(s_leg.mean()) if not s_leg.empty else post_mean
        else:
            pre_mean = post_mean
        diff = post_mean - pre_mean
        rel_change = (diff / pre_mean * 100.0) if pre_mean != 0 else 0.0
        peak_comp_rows.append(
            {
                "season": s,
                "pre_correction_mean_peak_ndvi": round(pre_mean, 4),
                "post_correction_mean_peak_ndvi": round(post_mean, 4),
                "absolute_change": round(diff, 4),
                "relative_change_pct": round(rel_change, 2),
            }
        )

    all_post_mean = float(season_df["ndvi_peak"].mean())
    all_pre_mean = (
        float(df_legacy_peaks["legacy_peak"].mean()) if not df_legacy_peaks.empty else all_post_mean
    )
    overall_diff = all_post_mean - all_pre_mean
    overall_rel = (overall_diff / all_pre_mean * 100.0) if all_pre_mean != 0 else 0.0

    peak_ndvi_summary = {
        "by_season": peak_comp_rows,
        "overall": {
            "pre_correction_mean_peak_ndvi": round(all_pre_mean, 4),
            "post_correction_mean_peak_ndvi": round(all_post_mean, 4),
            "absolute_change": round(overall_diff, 4),
            "relative_change_pct": round(overall_rel, 2),
        },
    }

    # 3. Offset Rules & Processing Baseline Distribution
    offset_rules_by_season: list[dict[str, Any]] = []
    baseline_dist_by_season: list[dict[str, Any]] = []
    if not df_v2.empty:
        for s in seasons:
            s_obs = df_v2[df_v2["season"] == s]
            total_s = len(s_obs)
            rule_counts = s_obs["offset_rule"].value_counts().to_dict()
            baseline_counts = s_obs["processing_baseline"].fillna("None").value_counts().to_dict()

            offset_rules_by_season.append(
                {
                    "season": s,
                    "total_observations": total_s,
                    "counts": {
                        "baseline": int(rule_counts.get("baseline", 0)),
                        "metadata": int(rule_counts.get("metadata", 0)),
                        "date_fallback": int(rule_counts.get("date_fallback", 0)),
                    },
                    "shares_pct": {
                        "baseline": round(rule_counts.get("baseline", 0) / total_s * 100.0, 2)
                        if total_s > 0
                        else 0.0,
                        "metadata": round(rule_counts.get("metadata", 0) / total_s * 100.0, 2)
                        if total_s > 0
                        else 0.0,
                        "date_fallback": round(
                            rule_counts.get("date_fallback", 0) / total_s * 100.0, 2
                        )
                        if total_s > 0
                        else 0.0,
                    },
                }
            )

            baseline_dist_by_season.append(
                {
                    "season": s,
                    "total_observations": total_s,
                    "counts": {k: int(v) for k, v in baseline_counts.items()},
                    "shares_pct": {
                        k: round(v / total_s * 100.0, 2) for k, v in baseline_counts.items()
                    }
                    if total_s > 0
                    else {},
                }
            )

    # 4. Per-Plot Summary Table (N=24)
    plot_rows: list[dict[str, Any]] = []
    for p in approved_plots:
        p_df = season_df[season_df["plot_code"] == p]
        min_p = float(p_df["ndvi_peak"].min()) if not p_df.empty else 0.0
        mean_p = float(p_df["ndvi_peak"].mean()) if not p_df.empty else 0.0
        max_p = float(p_df["ndvi_peak"].max()) if not p_df.empty else 0.0
        plot_rows.append(
            {
                "plot_code": p,
                "min_peak": round(min_p, 4),
                "mean_peak": round(mean_p, 4),
                "max_peak": round(max_p, 4),
                "max_peak_category": "below_0.30"
                if max_p < 0.30
                else ("0.30_to_0.40" if max_p <= 0.40 else "above_0.40"),
                "non_crop_suspect": max_p < 0.30,
                "has_any_peak_below_030": min_p < 0.30,
                "borderline_mean_below_040": mean_p < 0.40,
            }
        )

    df_p_summary = pd.DataFrame(plot_rows)
    non_crop_plots = df_p_summary[df_p_summary["non_crop_suspect"]]["plot_code"].tolist()
    borderline_plots = df_p_summary[df_p_summary["borderline_mean_below_040"]]["plot_code"].tolist()
    two_suspect = ["UMRETH_WHEAT_09", "KHAMBHAT_WHEAT_12"]

    cohort_means: dict[str, dict[str, float]] = {
        "all_24_plots": season_df.groupby("season")["ndvi_peak"].mean().round(4).to_dict(),
        "excluding_two_suspect": season_df[~season_df["plot_code"].isin(two_suspect)]
        .groupby("season")["ndvi_peak"]
        .mean()
        .round(4)
        .to_dict(),
        "excluding_non_crop_suspect": season_df[~season_df["plot_code"].isin(non_crop_plots)]
        .groupby("season")["ndvi_peak"]
        .mean()
        .round(4)
        .to_dict(),
        "excluding_borderline": season_df[~season_df["plot_code"].isin(borderline_plots)]
        .groupby("season")["ndvi_peak"]
        .mean()
        .round(4)
        .to_dict(),
    }

    # 5. Stress Label Counts (Unchanged Rule tau=15%)
    labelled = features_df[features_df["label_unavailable"] == False]  # noqa: E712
    stressed = labelled[labelled["stressed"] == 1]
    s24 = labelled[labelled["season"] == "2024-25"]
    s24_str = s24[s24["stressed"] == 1]

    labelled_no_2 = labelled[~labelled["plot_code"].isin(two_suspect)]
    stressed_no_2 = labelled_no_2[labelled_no_2["stressed"] == 1]
    s24_no_2 = labelled_no_2[labelled_no_2["season"] == "2024-25"]
    s24_str_no_2 = s24_no_2[s24_no_2["stressed"] == 1]

    labelled_no_nc = labelled[~labelled["plot_code"].isin(non_crop_plots)]
    stressed_no_nc = labelled_no_nc[labelled_no_nc["stressed"] == 1]
    s24_no_nc = labelled_no_nc[labelled_no_nc["season"] == "2024-25"]
    s24_str_no_nc = s24_no_nc[s24_no_nc["stressed"] == 1]

    stress_label_summary = {
        "all_24_plots": {
            "overall_labelled_rows": len(labelled),
            "overall_stressed_count": len(stressed),
            "overall_stressed_rate_pct": round(len(stressed) / len(labelled) * 100.0, 2)
            if len(labelled) > 0
            else 0.0,
            "season_2024_25_labelled_rows": len(s24),
            "season_2024_25_stressed_count": len(s24_str),
            "season_2024_25_stressed_rate_pct": round(len(s24_str) / len(s24) * 100.0, 2)
            if len(s24) > 0
            else 0.0,
        },
        "excluding_two_suspect_plots": {
            "excluded_plots": two_suspect,
            "overall_labelled_rows": len(labelled_no_2),
            "overall_stressed_count": len(stressed_no_2),
            "overall_stressed_rate_pct": round(len(stressed_no_2) / len(labelled_no_2) * 100.0, 2)
            if len(labelled_no_2) > 0
            else 0.0,
            "season_2024_25_labelled_rows": len(s24_no_2),
            "season_2024_25_stressed_count": len(s24_str_no_2),
            "season_2024_25_stressed_rate_pct": round(len(s24_str_no_2) / len(s24_no_2) * 100.0, 2)
            if len(s24_no_2) > 0
            else 0.0,
        },
        "excluding_all_non_crop_suspect": {
            "excluded_plots": non_crop_plots,
            "overall_labelled_rows": len(labelled_no_nc),
            "overall_stressed_count": len(stressed_no_nc),
            "overall_stressed_rate_pct": round(len(stressed_no_nc) / len(labelled_no_nc) * 100.0, 2)
            if len(labelled_no_nc) > 0
            else 0.0,
            "season_2024_25_labelled_rows": len(s24_no_nc),
            "season_2024_25_stressed_count": len(s24_str_no_nc),
            "season_2024_25_stressed_rate_pct": round(
                len(s24_str_no_nc) / len(s24_no_nc) * 100.0, 2
            )
            if len(s24_no_nc) > 0
            else 0.0,
        },
    }

    # 6. Threshold Sensitivity Table (Drops >= tau)
    drops = labelled["peak_drop_pct"]
    threshold_rows: list[dict[str, Any]] = []
    for tau in [5.0, 10.0, 15.0, 20.0, 25.0, 30.0]:
        cnt = int((drops >= tau).sum())
        rate = round(cnt / len(drops) * 100.0, 2) if len(drops) > 0 else 0.0
        threshold_rows.append(
            {
                "threshold_drop_pct": tau,
                "stressed_count": cnt,
                "share_of_labelled_dataset_pct": rate,
            }
        )

    # 7. Same-Window Multi-Season January Analysis
    jan_rows: list[dict[str, Any]] = []
    if not df_v2.empty:
        df_valid = df_v2[df_v2["is_valid"] == True].copy()  # noqa: E712
        df_valid["md"] = df_valid["date"].apply(lambda d: d[5:])
        for s in seasons:
            s_valid = df_valid[df_valid["season"] == s]

            early = s_valid[(s_valid["md"] >= "01-01") & (s_valid["md"] <= "01-24")]
            n_early = len(early)
            m_early = float(early["ndvi"].mean()) if n_early > 0 else 0.0
            d_early = int(early["date"].nunique())

            late = s_valid[(s_valid["md"] >= "01-25") & (s_valid["md"] <= "01-31")]
            n_late = len(late)
            m_late = float(late["ndvi"].mean()) if n_late > 0 else 0.0
            d_late = int(late["date"].nunique())

            jan_rows.append(
                {
                    "season": s,
                    "window_01_24_jan": {
                        "n_observations": n_early,
                        "mean_corrected_ndvi": round(m_early, 4),
                        "distinct_acquisition_dates": d_early,
                    },
                    "window_25_31_jan": {
                        "n_observations": n_late,
                        "mean_corrected_ndvi": round(m_late, 4),
                        "distinct_acquisition_dates": d_late,
                    },
                }
            )

    # Construct final root payload
    summary_data = {
        "metadata": {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "generator_command": "python scripts/analysis/ndvi_summary.py",
            "rule": "Rule 10 (Strict Numerical Traceability)",
            "data_hashes": {
                "season_dataset_csv_sha256": compute_file_sha256(season_dataset_path),
                "features_csv_sha256": compute_file_sha256(features_path),
                "plots_csv_sha256": compute_file_sha256(plots_path),
            },
            "sample_plot_count": len(approved_plots),
            "season_count": len(seasons),
        },
        "peak_ndvi_comparison": peak_ndvi_summary,
        "offset_rules_by_season": offset_rules_by_season,
        "processing_baselines_by_season": baseline_dist_by_season,
        "per_plot_summary": plot_rows,
        "cohort_seasonal_means": cohort_means,
        "stress_label_counts": stress_label_summary,
        "threshold_sensitivity": threshold_rows,
        "january_same_window_analysis": jan_rows,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fp:
        json.dump(summary_data, fp, indent=2)

    return summary_data


def main() -> int:
    """CLI entry point for ndvi_summary generator."""
    parser = argparse.ArgumentParser(
        description="Deterministically generate reports/ndvi_summary.json"
    )
    parser.add_argument(
        "--season-dataset",
        type=Path,
        default=Path("data/processed/season_dataset.csv"),
        help="Path to processed season dataset CSV",
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/features.csv"),
        help="Path to processed features CSV",
    )
    parser.add_argument(
        "--satellite-dir",
        type=Path,
        default=Path("data/raw/satellite"),
        help="Path to raw satellite cache JSON directory",
    )
    parser.add_argument(
        "--plots",
        type=Path,
        default=Path("data/synthetic/sample_plots.csv"),
        help="Path to approved sample plots CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/ndvi_summary.json"),
        help="Path to output JSON artifact",
    )

    args = parser.parse_args()
    summary = generate_ndvi_summary(
        season_dataset_path=args.season_dataset,
        features_path=args.features,
        satellite_dir=args.satellite_dir,
        plots_path=args.plots,
        output_path=args.output,
    )
    print(f"Successfully generated {args.output} (SHA-256 traceable)")
    plots_count = summary["metadata"]["sample_plot_count"]
    season_count = summary["metadata"]["season_count"]
    print(f"Plots analyzed: {plots_count} | Seasons: {season_count}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
