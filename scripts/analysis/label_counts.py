"""Deterministic analysis script computing label counts, feasibility gate, and metrics."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from satbhoomi.risk.baseline import AgronomicRulesBaseline


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hash of a file if it exists, else return empty string."""
    if not path.is_file():
        return ""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_label_counts(
    features_path: Path,
    plots_path: Path,
    season_dataset_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    """Compute label counts and evaluation feasibility gate status."""
    features_df = pd.read_csv(features_path)
    plots_df = pd.read_csv(plots_path)

    active_plots = (
        plots_df[plots_df["status"] == "active"]["plot_code"].tolist()
        if "status" in plots_df.columns
        else plots_df["plot_code"].tolist()
    )

    # 1. Total and seasonal breakdown
    total_rows = len(features_df)
    unlabelled_rows = len(features_df[features_df["label_unavailable"] == True])  # noqa: E712
    labelled_df = features_df[features_df["label_unavailable"] == False]  # noqa: E712
    total_labelled = len(labelled_df)
    total_stressed = int((labelled_df["stressed"] == 1).sum())
    total_normal = int((labelled_df["stressed"] == 0).sum())

    seasonal_counts: list[dict[str, Any]] = []
    seasons = sorted(features_df["season"].unique().tolist())
    for s in seasons:
        s_all = features_df[features_df["season"] == s]
        s_lab = s_all[s_all["label_unavailable"] == False]  # noqa: E712
        s_pos = int((s_lab["stressed"] == 1).sum())
        s_neg = int((s_lab["stressed"] == 0).sum())
        seasonal_counts.append(
            {
                "season": s,
                "total_rows": len(s_all),
                "labelled_rows": len(s_lab),
                "stressed_count": s_pos,
                "normal_count": s_neg,
                "stressed_rate_pct": round(s_pos / len(s_lab) * 100.0, 2)
                if len(s_lab) > 0
                else 0.0,
            }
        )

    # 2. Evaluation Set (Newest Season: 2024-25)
    s24 = labelled_df[labelled_df["season"] == "2024-25"]
    eval_pos = int((s24["stressed"] == 1).sum())
    eval_neg = int((s24["stressed"] == 0).sum())

    # 3. Feasibility Gate Check
    # Gate Rules:
    # 1. Evaluation set must have >= 5 positives
    # 2. Evaluation set must have >= 5 negatives
    # 3. Pooled forward-chaining folds must contain >= 10 positives in total
    min_eval_positives_required = 5
    min_eval_negatives_required = 5
    min_pooled_positives_required = 10

    eval_pos_passed = eval_pos >= min_eval_positives_required
    eval_neg_passed = eval_neg >= min_eval_negatives_required
    pooled_pos_passed = total_stressed >= min_pooled_positives_required

    gate_passed = eval_pos_passed and eval_neg_passed and pooled_pos_passed
    gate_status = "EVALUABLE" if gate_passed else "NOT EVALUABLE"

    feasibility_gate = {
        "status": gate_status,
        "gate_passed": gate_passed,
        "criteria": {
            "eval_season": "2024-25",
            "eval_positives_observed": eval_pos,
            "eval_positives_required": min_eval_positives_required,
            "eval_positives_passed": eval_pos_passed,
            "eval_negatives_observed": eval_neg,
            "eval_negatives_required": min_eval_negatives_required,
            "eval_negatives_passed": eval_neg_passed,
            "pooled_forward_chaining_positives_observed": total_stressed,
            "pooled_forward_chaining_positives_required": min_pooled_positives_required,
            "pooled_positives_passed": pooled_pos_passed,
        },
        "ml_action": "FREEZE_ML_TRAINING" if not gate_passed else "ALLOW_EVALUATION",
        "active_scorer": "AgronomicRulesBaseline",
    }

    # 4. Descriptive evaluation of AgronomicRulesBaseline on the 4 stressed rows
    baseline = AgronomicRulesBaseline()
    stressed_rows = labelled_df[labelled_df["stressed"] == 1].sort_values(["season", "plot_code"])
    rules_eval_rows: list[dict[str, Any]] = []
    if not stressed_rows.empty:
        probs = baseline.predict_proba(stressed_rows)[:, 1]
        for (_, r), p in zip(stressed_rows.iterrows(), probs, strict=False):
            band = "high" if p >= 0.70 else ("medium" if p >= 0.30 else "low")
            rules_eval_rows.append(
                {
                    "plot_code": str(r["plot_code"]),
                    "season": str(r["season"]),
                    "drop_pct": round(float(r["peak_drop_pct"]), 2),
                    "baseline_predicted_prob": round(float(p), 2),
                    "baseline_risk_band": band,
                    "ndvi_early": round(float(r["ndvi_early"]), 4)
                    if pd.notna(r.get("ndvi_early"))
                    else None,
                    "rain_deficit_pct": round(float(r["rain_pre_cutoff_deficit_pct"]), 2)
                    if pd.notna(r.get("rain_pre_cutoff_deficit_pct"))
                    else None,
                }
            )

    # 5. Robustness / Sensitivity Analysis
    # A. Threshold sensitivity (10%, 15%, 20%)
    # Note: drop_pct >= threshold denotes stress
    tau_10_count = int((labelled_df["peak_drop_pct"] >= 10.0).sum())
    tau_15_count = int((labelled_df["peak_drop_pct"] >= 15.0).sum())
    tau_20_count = int((labelled_df["peak_drop_pct"] >= 20.0).sum())

    # B. Baseline depth >= 2 prior seasons (seasons 2022-23 to 2024-25)
    seasons_depth_ge_2 = ["2022-23", "2023-24", "2024-25"]
    depth_ge_2_df = labelled_df[labelled_df["season"].isin(seasons_depth_ge_2)]
    depth_ge_2_pos = int((depth_ge_2_df["stressed"] == 1).sum())

    # C. Excluding borderline plots (ANAND_WHEAT_13, ANAND_WHEAT_14, TARAPUR_WHEAT_11)
    borderline_plots = ["ANAND_WHEAT_13", "ANAND_WHEAT_14", "TARAPUR_WHEAT_11"]
    clear_plots_df = labelled_df[~labelled_df["plot_code"].isin(borderline_plots)]
    clear_plots_pos = int((clear_plots_df["stressed"] == 1).sum())

    robustness = {
        "disclaimer": "Descriptive only: no label is being chosen here",
        "threshold_sensitivity": [
            {
                "threshold_drop_pct": 10.0,
                "stressed_count": tau_10_count,
                "share_pct": round(tau_10_count / total_labelled * 100.0, 2)
                if total_labelled > 0
                else 0.0,
            },
            {
                "threshold_drop_pct": 15.0,
                "stressed_count": tau_15_count,
                "share_pct": round(tau_15_count / total_labelled * 100.0, 2)
                if total_labelled > 0
                else 0.0,
            },
            {
                "threshold_drop_pct": 20.0,
                "stressed_count": tau_20_count,
                "share_pct": round(tau_20_count / total_labelled * 100.0, 2)
                if total_labelled > 0
                else 0.0,
            },
        ],
        "depth_at_least_2_seasons": {
            "seasons_included": seasons_depth_ge_2,
            "total_labelled": len(depth_ge_2_df),
            "stressed_count": depth_ge_2_pos,
            "stressed_rate_pct": round(depth_ge_2_pos / len(depth_ge_2_df) * 100.0, 2)
            if len(depth_ge_2_df) > 0
            else 0.0,
        },
        "excluding_borderline_plots": {
            "borderline_plots_excluded": borderline_plots,
            "total_labelled": len(clear_plots_df),
            "stressed_count": clear_plots_pos,
            "stressed_rate_pct": round(clear_plots_pos / len(clear_plots_df) * 100.0, 2)
            if len(clear_plots_df) > 0
            else 0.0,
        },
    }

    result = {
        "metadata": {
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "generator_command": "python scripts/analysis/label_counts.py",
            "rule": "Rule 10 (Strict Numerical Traceability)",
            "data_hashes": {
                "features_csv_sha256": compute_file_sha256(features_path),
                "plots_csv_sha256": compute_file_sha256(plots_path),
                "season_dataset_csv_sha256": compute_file_sha256(season_dataset_path),
            },
            "sample_plot_count": len(active_plots),
            "total_rows": total_rows,
            "unlabelled_rows": unlabelled_rows,
            "labelled_rows": total_labelled,
        },
        "label_counts": {
            "active_plots_count": len(active_plots),
            "total_labelled_rows": total_labelled,
            "total_stressed_count": total_stressed,
            "total_normal_count": total_normal,
            "overall_stressed_rate_pct": round(total_stressed / total_labelled * 100.0, 2),
            "seasonal_breakdown": seasonal_counts,
        },
        "feasibility_gate": feasibility_gate,
        "rules_baseline_descriptive_on_stressed": {
            "disclaimer": "n = 4, descriptive only, no inference",
            "rows": rules_eval_rows,
        },
        "robustness": robustness,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


def main() -> int:
    """CLI entry point for label_counts analysis."""
    parser = argparse.ArgumentParser(
        description="Compute label counts, feasibility gate status, and robustness metrics."
    )
    parser.add_argument(
        "--features",
        type=Path,
        default=Path("data/processed/features.csv"),
        help="Path to features CSV",
    )
    parser.add_argument(
        "--plots",
        type=Path,
        default=Path("data/synthetic/sample_plots.csv"),
        help="Path to sample plots CSV",
    )
    parser.add_argument(
        "--season-dataset",
        type=Path,
        default=Path("data/processed/season_dataset.csv"),
        help="Path to seasonal dataset CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/label_counts.json"),
        help="Path to output JSON report",
    )

    args = parser.parse_args()
    summary = generate_label_counts(
        features_path=args.features,
        plots_path=args.plots,
        season_dataset_path=args.season_dataset,
        output_path=args.output,
    )

    print(f"Generated {args.output}")
    print(
        f"Plots: {summary['label_counts']['active_plots_count']} | "
        f"Labelled: {summary['label_counts']['total_labelled_rows']} | "
        f"Stressed: {summary['label_counts']['total_stressed_count']} "
        f"({summary['label_counts']['overall_stressed_rate_pct']}%)"
    )
    print(f"Feasibility Gate: {summary['feasibility_gate']['status']}")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
