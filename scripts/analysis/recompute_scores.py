#!/usr/bin/env python3
"""Recompute risk scores, bands, loan suggestions, and what-if downstream outputs (Stage B).

Usage:
    python scripts/analysis/recompute_scores.py [--features-csv PATH] [--output-json PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import pandas as pd

from satbhoomi.features.config import RABI_SEASONS_ORDER
from satbhoomi.risk.config import (
    BAND_HIGH_MIN,
    BAND_LOW_MAX,
    BAND_MEDIUM_MAX,
    NDVI_DROP_ACUTE_PCT,
    NDVI_DROP_MODERATE_PCT,
    RAIN_DEFICIT_MODERATE_PCT,
    RULES_BASELINE_VERSION,
)
from satbhoomi.risk.loan_suggestions import generate_loan_suggestion
from satbhoomi.risk.scoring import score_plot_season
from satbhoomi.risk.what_if import simulate_what_if

EXCLUDED_PLOTS: frozenset[str] = frozenset({"ANAND_WHEAT_07", "PETLAD_WHEAT_01", "THASRA_WHEAT_06"})


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def run_recomputation(
    features_csv: Path,
    output_json: Path,
) -> dict[str, Any]:
    """Score all active plot-seasons and compile downstream reports."""
    df = pd.read_csv(features_csv)
    file_hash = compute_file_sha256(features_csv)

    all_plots = sorted(df["plot_code"].unique())
    active_plots = [p for p in all_plots if p not in EXCLUDED_PLOTS]

    active_df = df[df["plot_code"].isin(active_plots)].sort_values(["plot_code", "season"])

    scores_records: list[dict[str, Any]] = []
    season_band_counts: dict[str, dict[str, int]] = {
        s: {"low": 0, "medium": 0, "high": 0, "insufficient_data": 0} for s in RABI_SEASONS_ORDER
    }
    plot_flags_count: dict[str, int] = dict.fromkeys(active_plots, 0)

    for _, row in active_df.iterrows():
        p = str(row["plot_code"])
        s = str(row["season"])
        res = score_plot_season(row)

        band_str = res.band if res.status == "ok" and res.band else "insufficient_data"
        season_band_counts[s][band_str] = season_band_counts[s].get(band_str, 0) + 1

        if res.status == "ok" and res.band in ("medium", "high"):
            plot_flags_count[p] += 1

        rec = {
            "plot_code": p,
            "season": s,
            "status": res.status,
            "score": res.score,
            "band": res.band,
            "reasons": res.reasons,
            "protective_factor": res.protective_factor,
            "insufficient_data_reason": res.insufficient_data_reason,
            "data_warnings": res.data_warnings,
        }
        scores_records.append(rec)

    # Compile flag frequency across 4 evaluable seasons
    flag_frequency = {
        "flagged_0_seasons": sum(1 for c in plot_flags_count.values() if c == 0),
        "flagged_1_season": sum(1 for c in plot_flags_count.values() if c == 1),
        "flagged_2_seasons": sum(1 for c in plot_flags_count.values() if c == 2),
        "flagged_3_seasons": sum(1 for c in plot_flags_count.values() if c == 3),
        "flagged_4_seasons": sum(1 for c in plot_flags_count.values() if c == 4),
    }

    # Downstream examples: Loan Suggestions
    # 1. Low risk irrigated plot (ANAND_WHEAT_01, 2024-25)
    row_low = active_df[
        (active_df["plot_code"] == "ANAND_WHEAT_01") & (active_df["season"] == "2024-25")
    ].iloc[0]
    res_low = score_plot_season(row_low)
    loan_low = generate_loan_suggestion(
        res_low,
        area_acre=float(row_low["area_acre"]),
        crop="wheat",
        irrigation=str(row_low["irrigation"]),
        insured=bool(row_low["insured"]),
    )

    # 2. Insufficient data season 1 plot (ANAND_WHEAT_01, 2020-21)
    row_s1 = active_df[
        (active_df["plot_code"] == "ANAND_WHEAT_01") & (active_df["season"] == "2020-21")
    ].iloc[0]
    res_s1 = score_plot_season(row_s1)
    loan_s1 = generate_loan_suggestion(
        res_s1,
        area_acre=float(row_s1["area_acre"]),
        crop="wheat",
        irrigation=str(row_s1["irrigation"]),
        insured=bool(row_s1["insured"]),
    )

    # 3. High risk acute drop plot (if any) or medium risk plot
    flagged_rows = [r for r in scores_records if r["band"] in ("medium", "high")]
    loan_flagged = None
    if flagged_rows:
        sample_flag = flagged_rows[0]
        row_fl = active_df[
            (active_df["plot_code"] == sample_flag["plot_code"])
            & (active_df["season"] == sample_flag["season"])
        ].iloc[0]
        res_fl = score_plot_season(row_fl)
        loan_flagged = generate_loan_suggestion(
            res_fl,
            area_acre=float(row_fl["area_acre"]),
            crop="wheat",
            irrigation=str(row_fl["irrigation"]),
            insured=bool(row_fl["insured"]),
        )

    # Downstream examples: What-If Simulations
    # 1. Insurance intervention on medium risk plot
    what_if_examples = []
    if flagged_rows:
        sample_p = flagged_rows[0]["plot_code"]
        sample_s = flagged_rows[0]["season"]
        target_row = active_df[
            (active_df["plot_code"] == sample_p) & (active_df["season"] == sample_s)
        ].iloc[0]

        # Test insurance
        wi_ins = simulate_what_if(target_row, changed_input="insured", new_value=1)
        what_if_examples.append(wi_ins.model_dump(mode="json"))

        # Test irrigation
        wi_irr = simulate_what_if(target_row, changed_input="irrigation", new_value="drip")
        what_if_examples.append(wi_irr.model_dump(mode="json"))

    # Test zero-delta behavior: low-risk irrigated plot tested with supplementary irrigation
    wi_zero = simulate_what_if(
        row_low, changed_input="supplementary_irrigation", new_value="applied"
    )
    what_if_examples.append(wi_zero.model_dump(mode="json"))

    summary: dict[str, Any] = {
        "metadata": {
            "title": "SatBhoomi v2.0 Relative Rules Downstream Recomputation Report",
            "model_version": RULES_BASELINE_VERSION,
            "features_csv_path": str(features_csv),
            "features_csv_sha256": file_hash,
            "total_active_plots": len(active_plots),
            "total_plot_seasons": len(active_df),
            "evaluation_note": (
                "Descriptive recomputation only. ML training remains frozen under Feasibility Gate."
            ),
        },
        "thresholds": {
            "ndvi_drop_moderate_pct": NDVI_DROP_MODERATE_PCT,
            "ndvi_drop_acute_pct": NDVI_DROP_ACUTE_PCT,
            "rain_deficit_moderate_pct": RAIN_DEFICIT_MODERATE_PCT,
            "band_low_max": BAND_LOW_MAX,
            "band_medium_max": BAND_MEDIUM_MAX,
            "band_high_min": BAND_HIGH_MIN,
        },
        "band_distribution_by_season": season_band_counts,
        "overall_band_totals": {
            "insufficient_data": sum(c["insufficient_data"] for c in season_band_counts.values()),
            "low": sum(c["low"] for c in season_band_counts.values()),
            "medium": sum(c["medium"] for c in season_band_counts.values()),
            "high": sum(c["high"] for c in season_band_counts.values()),
            "total_evaluable_plot_seasons": sum(
                c["low"] + c["medium"] + c["high"] for c in season_band_counts.values()
            ),
        },
        "plot_flag_persistence": flag_frequency,
        "census_of_flagged_plot_seasons": flagged_rows,
        "sample_loan_suggestions": {
            "low_risk_example": loan_low.model_dump(mode="json"),
            "insufficient_data_season1_example": loan_s1.model_dump(mode="json"),
            "elevated_risk_example": loan_flagged.model_dump(mode="json") if loan_flagged else None,
        },
        "sample_what_if_simulations": what_if_examples,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Recompute downstream scores and reports.")
    parser.add_argument(
        "--features-csv",
        type=Path,
        default=Path("data/processed/features.csv"),
        help="Path to features CSV",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=Path("reports/scores_summary.json"),
        help="Path to output JSON summary",
    )
    args = parser.parse_args()

    if not args.features_csv.is_file():
        print(f"Error: features CSV not found at {args.features_csv}", file=sys.stderr)
        return 1

    summary = run_recomputation(args.features_csv, args.output_json)
    print(f"Successfully generated {args.output_json}")
    print(f"Active plots: {summary['metadata']['total_active_plots']}")
    print(f"Total rows:   {summary['metadata']['total_plot_seasons']}")
    print(f"Overall bands: {summary['overall_band_totals']}")
    print(f"Plot flag persistence: {summary['plot_flag_persistence']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
