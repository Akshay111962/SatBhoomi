#!/usr/bin/env python3
r"""Import Raksha historical seasonal alert replay and timeline observations into database (T-11C).

Usage (PowerShell):
    # Preview import in dry-run mode (no database writes):
    .venv\Scripts\python scripts/import_alert_replay.py --dry-run

    # Execute full idempotent import into active database:
    .venv\Scripts\python scripts/import_alert_replay.py

    # Override dataset path:
    .venv\Scripts\python scripts/import_alert_replay.py `
        --dataset-csv data/processed/season_dataset.csv

Integrity & Decisional Rules:
- Only ACTIVE plots from database are processed (excluded non-crop plots are skipped).
- Alerts are deduplicated per (plot_id, season, type): exactly one alert per plot-season-type,
  preserving the first checkpoint date where the condition was detected, escalating severity
  if a later checkpoint reaches higher severity, and never creating duplicate rows.
- Checkpoints with status 'data_gap' are stored in plot_season_timeline.data_gaps_json, not alerts.
- Synthetic stress scenarios (e.g. TC-007 simulation) are strictly excluded from DB import.
- Timelines store compact per-plot-season checkpoint observations (date, NDVI, rainfall, data_gap).
- Script is fully idempotent: running repeatedly updates or preserves records with zero drift.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.alerts.replay import (
    extract_checkpoint_ndvi_from_scenes,
    load_raw_scenes_cache,
    replay_single_plot_season,
    sort_seasons_chronologically,
)
from satbhoomi.db.models.alert import Alert
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_timeline import PlotSeasonTimeline
from satbhoomi.db.session import create_db_engine

SEVERITY_ORDER: dict[str, int] = {"low": 1, "medium": 2, "high": 3}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import Raksha historical season replay alerts and timelines into database.",
    )
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
        "--db-url",
        type=str,
        default=None,
        help="Database connection URL override (defaults to application settings).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run replay and validate records without committing changes to database.",
    )
    return parser.parse_args()


def build_compact_timeline(
    checkpoint_results: list[Any],
    curr_scenes: list[dict[str, Any]],
    curr_row: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build compact sequential timeline observation points for a plot-season."""
    timeline: list[dict[str, Any]] = []

    for cp in checkpoint_results:
        cp_date = cp.evaluation_date
        ndvi_val: float | None = None
        if curr_scenes:
            raw_ndvi, _ = extract_checkpoint_ndvi_from_scenes(curr_scenes, cp_date)
            if raw_ndvi is not None:
                ndvi_val = round(float(raw_ndvi), 4)

        # Cumulative rainfall up to checkpoint
        if cp_date.month == 12:
            r_cum = float(curr_row.get("rain_nov_mm", 0.0) or 0.0) + 0.5 * float(
                curr_row.get("rain_dec_mm", 0.0) or 0.0
            )
        elif cp_date.month == 1 and cp_date.day == 15:
            r_cum = (
                float(curr_row.get("rain_nov_mm", 0.0) or 0.0)
                + float(curr_row.get("rain_dec_mm", 0.0) or 0.0)
                + 0.5 * float(curr_row.get("rain_jan_mm", 0.0) or 0.0)
            )
        else:
            r_cum = (
                float(curr_row.get("rain_nov_mm", 0.0) or 0.0)
                + float(curr_row.get("rain_dec_mm", 0.0) or 0.0)
                + float(curr_row.get("rain_jan_mm", 0.0) or 0.0)
            )

        timeline.append(
            {
                "date": cp_date.isoformat(),
                "checkpoint_label": cp.checkpoint_label,
                "ndvi": ndvi_val,
                "rainfall_mm": round(r_cum, 2),
                "data_gap": (cp.status == "data_gap"),
                "data_gap_reason": cp.data_gap_reason,
            }
        )
    return timeline


def run_import(
    dataset_csv: Path,
    raw_satellite_dir: Path,
    db_session: Session,
    dry_run: bool = False,
) -> dict[str, int]:
    """Execute historical alert replay and import into active database."""
    if not dataset_csv.is_file():
        print(f"ERROR: Dataset CSV not found at {dataset_csv}", file=sys.stderr)
        sys.exit(1)

    dataset_df = pd.read_csv(dataset_csv)

    # 1. Fetch active plots with plot_code from DB
    plots = (
        db_session.execute(select(Plot).where(Plot.plot_code.isnot(None)).order_by(Plot.id))
        .scalars()
        .all()
    )

    if not plots:
        print(
            "ERROR: No active plots found in database. Run import_plots_features.py first.",
            file=sys.stderr,
        )
        sys.exit(1)

    all_seasons = sort_seasons_chronologically(list(dataset_df["season"].unique()))

    stats = {
        "active_plots": len(plots),
        "seasons_evaluated": len(all_seasons),
        "timelines_created": 0,
        "timelines_updated": 0,
        "alerts_created": 0,
        "alerts_updated": 0,
        "data_gaps_recorded": 0,
        "rejected_rows": 0,
    }

    import_time = datetime.now(UTC)

    for plot in plots:
        plot_code = plot.plot_code
        if not plot_code:
            print(f"ERROR: Plot id={plot.id} has no plot_code.", file=sys.stderr)
            stats["rejected_rows"] += 1
            sys.exit(1)

        plot_dataset = dataset_df[dataset_df["plot_code"] == plot_code]
        if plot_dataset.empty:
            continue

        for season in all_seasons:
            season_df = plot_dataset[plot_dataset["season"] == season]
            if season_df.empty:
                continue

            curr_row = season_df.iloc[0].to_dict()
            curr_scenes = load_raw_scenes_cache(plot_code, season, raw_satellite_dir)

            # Replay historical season checkpoints
            checkpoint_results = replay_single_plot_season(
                plot_code=plot_code,
                season=season,
                plot_df=season_df,
                full_df=dataset_df,
                raw_satellite_dir=raw_satellite_dir,
            )

            # Compact timeline
            timeline_list = build_compact_timeline(checkpoint_results, curr_scenes, curr_row)
            data_gaps_list = [
                {
                    "checkpoint_label": cp.checkpoint_label,
                    "date": cp.evaluation_date.isoformat(),
                    "reason": cp.data_gap_reason,
                }
                for cp in checkpoint_results
                if cp.status == "data_gap" and cp.data_gap_reason
            ]
            if data_gaps_list:
                stats["data_gaps_recorded"] += len(data_gaps_list)

            # Upsert timeline
            existing_timeline = (
                db_session.execute(
                    select(PlotSeasonTimeline).where(
                        PlotSeasonTimeline.plot_id == plot.id,
                        PlotSeasonTimeline.season == season,
                    )
                )
                .scalars()
                .first()
            )

            if existing_timeline:
                existing_timeline.timeline_json = timeline_list
                existing_timeline.data_gaps_json = data_gaps_list
                existing_timeline.checkpoint_count = len(timeline_list)
                existing_timeline.imported_at = import_time
                stats["timelines_updated"] += 1
            else:
                new_timeline = PlotSeasonTimeline(
                    plot_id=plot.id,
                    season=season,
                    timeline_json=timeline_list,
                    data_gaps_json=data_gaps_list,
                    checkpoint_count=len(timeline_list),
                    imported_at=import_time,
                )
                db_session.add(new_timeline)
                stats["timelines_created"] += 1

            # Deduplicate alerts across checkpoints for this plot-season
            # Rule: One per (plot_id, season, type) with highest severity and first checkpoint date
            best_alerts_by_type: dict[str, dict[str, Any]] = {}

            for cp in checkpoint_results:
                for al in cp.alerts:
                    # Data gaps are stored as data gap records, never as Alert rows
                    if al.status == "data_gap" or al.type == "data_gap":
                        continue

                    a_type = al.type
                    a_sev = al.severity
                    a_sev_val = SEVERITY_ORDER.get(a_sev, 1)

                    if a_type not in best_alerts_by_type:
                        best_alerts_by_type[a_type] = {
                            "type": a_type,
                            "severity": a_sev,
                            "severity_val": a_sev_val,
                            "first_date": al.detected_on,
                            "first_label": al.checkpoint_label,
                            "headline": al.headline,
                            "detail": al.detail,
                            "supportive_action": al.supportive_action,
                            "data_gap_warning": al.data_gap_warning,
                        }
                    else:
                        existing = best_alerts_by_type[a_type]
                        # Escalate severity if a later checkpoint was more acute
                        if a_sev_val > existing["severity_val"]:
                            existing["severity"] = a_sev
                            existing["severity_val"] = a_sev_val
                            existing["headline"] = al.headline
                            existing["detail"] = al.detail
                            existing["supportive_action"] = al.supportive_action
                            existing["data_gap_warning"] = al.data_gap_warning
                        # Keep earliest detected_on/first_label unchanged

            # Upsert deduplicated alerts into DB
            for a_type, al_info in best_alerts_by_type.items():
                existing_alert = (
                    db_session.execute(
                        select(Alert).where(
                            Alert.plot_id == plot.id,
                            Alert.season == season,
                            Alert.type == a_type,
                        )
                    )
                    .scalars()
                    .first()
                )

                det_datetime = (
                    datetime.combine(al_info["first_date"], datetime.min.time(), tzinfo=UTC)
                    if hasattr(al_info["first_date"], "year")
                    else import_time
                )

                if existing_alert:
                    # Update fields while preserving officer status if already progressed
                    existing_alert.severity = al_info["severity"]
                    existing_alert.checkpoint_label = al_info["first_label"]
                    existing_alert.headline = al_info["headline"]
                    existing_alert.detail = al_info["detail"]
                    existing_alert.supportive_action = al_info["supportive_action"]
                    existing_alert.data_gap_warning = al_info["data_gap_warning"]
                    existing_alert.is_replay = True
                    stats["alerts_updated"] += 1
                else:
                    new_alert = Alert(
                        plot_id=plot.id,
                        season=season,
                        type=a_type,
                        severity=al_info["severity"],
                        status="open",
                        detected_on=det_datetime,
                        checkpoint_label=al_info["first_label"],
                        headline=al_info["headline"],
                        detail=al_info["detail"],
                        supportive_action=al_info["supportive_action"],
                        data_gap_warning=al_info["data_gap_warning"],
                        is_replay=True,
                    )
                    db_session.add(new_alert)
                    stats["alerts_created"] += 1

    if dry_run:
        db_session.rollback()
        print("\n--- DRY-RUN SUMMARY (No database modifications committed) ---")
    else:
        db_session.commit()
        print("\n--- IMPORT COMPLETED AND COMMITTED ---")

    print(f"Active plots processed:     {stats['active_plots']}")
    print(f"Seasons evaluated:          {stats['seasons_evaluated']}")
    print(
        f"Timelines created/updated:  {stats['timelines_created']} / {stats['timelines_updated']}"
    )
    print(f"Alerts created/updated:     {stats['alerts_created']} / {stats['alerts_updated']}")
    print(f"Data gap checkpoints:       {stats['data_gaps_recorded']}")
    print(f"Rejected rows:              {stats['rejected_rows']}")

    if stats["rejected_rows"] > 0:
        sys.exit(1)

    return stats


def main() -> None:
    args = parse_args()
    engine = create_db_engine(args.db_url)
    with Session(engine) as session:
        run_import(
            dataset_csv=args.dataset_csv,
            raw_satellite_dir=args.raw_satellite_dir,
            db_session=session,
            dry_run=args.dry_run,
        )


if __name__ == "__main__":
    main()
