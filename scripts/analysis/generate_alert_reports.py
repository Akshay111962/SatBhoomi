#!/usr/bin/env python3
"""Generate structured alert replay report (Stage B, reports/replay_alerts.json).

Usage:
    python scripts/analysis/generate_alert_reports.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

import pandas as pd

from satbhoomi.alerts.replay import (
    generate_synthetic_stress_scenario,
    run_full_replay,
)


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    dataset_csv = Path("data/processed/season_dataset.csv")
    raw_sat_dir = Path("data/raw/satellite")
    output_json = Path("reports/replay_alerts.json")

    if not dataset_csv.is_file():
        print(f"Error: dataset CSV not found at {dataset_csv}", file=sys.stderr)
        return 1

    file_hash = compute_file_sha256(dataset_csv)
    df = pd.read_csv(dataset_csv)

    print("Running full historical season alert replay across active plots...")
    replay_report = run_full_replay(
        dataset_df=df,
        raw_satellite_dir=raw_sat_dir if raw_sat_dir.is_dir() else None,
    )

    print("Running TC-007 synthetic early warning scenario...")
    synth_res = generate_synthetic_stress_scenario(
        plot_code="ANAND_WHEAT_01",
        base_season="2023-24",
        raw_satellite_dir=raw_sat_dir if raw_sat_dir.is_dir() else None,
    )

    # Serialize synthetic results
    synth_dict = dict(synth_res)
    synth_dict["checkpoint_results"] = [
        r.model_dump(mode="json") for r in synth_res["checkpoint_results"]
    ]

    combined_report = {
        "metadata": {
            "title": "Raksha Alert Engine Historical Replay and Synthetic Scenario Report",
            "dataset_csv": str(dataset_csv),
            "dataset_csv_sha256": file_hash,
            "total_plots": replay_report.total_plots,
            "seasons_replayed": replay_report.seasons_replayed,
            "unflagged_false_alert_rate": replay_report.false_alert_rate_unflagged,
            "tc007_passed": replay_report.tc007_passed,
        },
        "historical_replay_summary": replay_report.model_dump(mode="json"),
        "tc007_synthetic_stress_scenario": synth_dict,
    }

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(combined_report, f, indent=2)

    print(f"Saved {output_json} successfully.")
    print(f"Alerts by season: {replay_report.alert_counts_by_season}")
    print(f"Alerts by type:   {replay_report.alert_counts_by_type}")
    print(f"Alerts by severity: {replay_report.alert_counts_by_severity}")
    print(
        f"TC-007 lead time: {synth_res['lead_time_weeks']} weeks "
        f"(Passed: {synth_res['tc007_passed']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
