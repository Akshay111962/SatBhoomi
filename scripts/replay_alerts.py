#!/usr/bin/env python3
"""CLI runner for Raksha Alert Engine and Historical Season Replay (T-09, FR-008).

Usage:
    python scripts/replay_alerts.py [--dataset-csv PATH] [--season SEASON]
                                   [--synthetic-only] [--json]

Examples:
    python scripts/replay_alerts.py --synthetic-only
    python scripts/replay_alerts.py --dataset-csv data/processed/season_dataset.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from satbhoomi.alerts.replay import (
    generate_synthetic_stress_scenario,
    replay_single_plot_season,
    run_full_replay,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Raksha In-Season Stress Alert Replay Engine.")
    parser.add_argument(
        "--dataset-csv",
        type=Path,
        default=Path("data/processed/season_dataset.csv"),
        help="Path to processed multi-source season dataset CSV.",
    )
    parser.add_argument(
        "--raw-satellite-dir",
        type=Path,
        default=Path("data/raw/satellite"),
        help="Path to directory containing raw Sentinel-2 scene JSON files.",
    )
    parser.add_argument(
        "--season",
        type=str,
        default=None,
        help="Specific season to replay (e.g., '2023-24'). If omitted, replays all seasons.",
    )
    parser.add_argument(
        "--plot-code",
        type=str,
        default=None,
        help="Specific plot code to replay. If omitted, replays all plots.",
    )
    parser.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Run only the TC-007 synthetic stress scenario test.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of human-readable summary table.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Synthetic-only branch
    if args.synthetic_only:
        synth_res = generate_synthetic_stress_scenario(
            plot_code=args.plot_code or "ANAND_WHEAT_01",
            base_season=args.season or "2023-24",
            raw_satellite_dir=args.raw_satellite_dir if args.raw_satellite_dir.is_dir() else None,
        )
        if args.json:
            # Serialise results
            out_data = dict(synth_res)
            out_data["checkpoint_results"] = [
                r.model_dump(mode="json") for r in synth_res["checkpoint_results"]
            ]
            print(json.dumps(out_data, indent=2))
        else:
            print("\n========================================================")
            print("  Raksha Alert Engine: Synthetic Stress Scenario (TC-007)")
            print("========================================================")
            print(f"Target Plot:         {synth_res['plot_code']}")
            print(f"Season:              {synth_res['base_season']}")
            print(f"First Alert Date:    {synth_res['first_alert_date']}")
            print(f"Harvest Start Date:  {synth_res['harvest_start_date']}")
            print(f"Lead Time to Harvest:{synth_res['lead_time_weeks']} weeks")
            print(f"TC-007 Passed (>=6w):{synth_res['tc007_passed']}")
            print(f"Total Alerts Fired:  {synth_res['alerts_count']}")
            print("--------------------------------------------------------")
            for r in synth_res["checkpoint_results"]:
                print(f"[{r.checkpoint_label}] Status: {r.status}")
                for a in r.alerts:
                    print(f"  * [{a.severity.upper()}] {a.type}: {a.headline}")
                    print(f"    Action: {a.supportive_action}")
            print("========================================================\n")
        return 0 if synth_res["tc007_passed"] else 1

    # Full or single plot/season replay branch
    if not args.dataset_csv.is_file():
        print(f"Error: Dataset CSV file not found at {args.dataset_csv}", file=sys.stderr)
        return 1

    df = pd.read_csv(args.dataset_csv)

    if args.plot_code and args.season:
        # Replay single plot season
        results = replay_single_plot_season(
            plot_code=args.plot_code,
            season=args.season,
            plot_df=df,
            full_df=df,
            raw_satellite_dir=args.raw_satellite_dir if args.raw_satellite_dir.is_dir() else None,
        )
        if args.json:
            print(json.dumps([r.model_dump(mode="json") for r in results], indent=2))
        else:
            print(f"\nReplay Results for {args.plot_code} ({args.season}):")
            for r in results:
                print(f"[{r.checkpoint_label}] Status: {r.status} (alerts: {len(r.alerts)})")
                for a in r.alerts:
                    print(f"  * [{a.severity.upper()}] {a.type}: {a.headline}")
                    print(f"    Detail: {a.detail}")
                    print(f"    Action: {a.supportive_action}")
        return 0

    # Full replay across dataset
    report = run_full_replay(
        dataset_df=df,
        raw_satellite_dir=args.raw_satellite_dir if args.raw_satellite_dir.is_dir() else None,
    )

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print("\n========================================================")
        print("     Raksha Alert Engine: Historical Season Replay      ")
        print("========================================================")
        print(f"Total Plots:                 {report.total_plots}")
        print(f"Seasons Replayed:            {', '.join(report.seasons_replayed)}")
        print(f"Unflagged False Alert Rate:  {report.false_alert_rate_unflagged * 100:.2f}%")
        print(f"TC-007 Synthetic Passed:     {report.tc007_passed}")
        print("--------------------------------------------------------")
        print("Alert Counts by Season:")
        for s, c in report.alert_counts_by_season.items():
            print(f"  - {s:10s}: {c:3d} alerts")
        print("Alert Counts by Rule Type:")
        for t, c in report.alert_counts_by_type.items():
            print(f"  - {t:20s}: {c:3d} alerts")
        print("Alert Counts by Severity:")
        for sev, c in report.alert_counts_by_severity.items():
            print(f"  - {sev:10s}: {c:3d} alerts")
        print("--------------------------------------------------------")
        print("Agronomic & Disclosure Notes:")
        for n in report.notes:
            print(f"  * {n}")
        print("========================================================\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
