#!/usr/bin/env python3
"""Import active plot definitions and pre-cutoff seasonal features into the database.

Usage (PowerShell):
    python scripts/import_plots_features.py --features-path data/processed/features.csv
    python scripts/import_plots_features.py --dry-run
    python scripts/import_plots_features.py --allow-fixture

Integrity & Privacy Rules:
- Only ACTIVE plots are imported (excluded non-crop plots under Rule R1 are strictly skipped).
- Label columns (stressed, label_unavailable, peak_drop_pct) are dropped immediately upon load.
- Synthetic farmer records use anonymous codes only (SAMPLE-FARMER-<plot_code>); no PII.
- Validates plot records using PlotCreateRequest schema before database writes.
- Rows with fixture provenance are rejected unless --allow-fixture is explicitly passed.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.api.schemas.plots import PlotCreateRequest
from satbhoomi.connectors.satellite.loader import load_sample_plots
from satbhoomi.db.models.farmer import Farmer
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_features import PlotSeasonFeatures
from satbhoomi.db.session import create_db_engine
from satbhoomi.features.config import (
    DEFAULT_CUTOFF_DAY,
    DEFAULT_CUTOFF_MONTH,
    FEATURE_SET_VERSION,
    get_season_cutoff_iso_date,
)
from satbhoomi.features.provenance import SOURCE_COLUMNS

LABEL_COLUMNS_TO_DROP: frozenset[str] = frozenset(
    {
        "stressed",
        "label_unavailable",
        "peak_drop_pct",
        "historical_baseline_ndvi",
    }
)

METADATA_NON_FEATURE_COLUMNS: frozenset[str] = frozenset(
    {
        "plot_code",
        "season",
        "district",
        "village",
        "crop",
        "lat",
        "lon",
        "area_acre",
        "irrigation",
        "insured",
        "status",
        "exclusion_reason",
        "exclusion_date",
        "buffer_m",
    }
) | frozenset(SOURCE_COLUMNS)


def sanitize_json_value(val: Any) -> Any:
    """Convert pandas/numpy types to clean JSON-serializable primitives (None for NaN)."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        return float(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    return str(val)


def import_plots_and_features(
    session: Session,
    features_path: Path,
    sample_plots_path: Path,
    *,
    allow_fixture: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute plot and feature snapshot ingestion with strict validation.

    Args:
        session: SQLAlchemy database session.
        features_path: Path to features CSV file.
        sample_plots_path: Path to sample_plots.csv.
        allow_fixture: Whether to allow rows with fixture provenance.
        dry_run: If True, validate and execute but rollback without committing.

    Returns:
        Summary dictionary with counts of created, updated, unchanged, and rejected records.
    """
    if not features_path.is_file():
        raise FileNotFoundError(f"Features file not found: {features_path}")
    if not sample_plots_path.is_file():
        raise FileNotFoundError(f"Sample plots file not found: {sample_plots_path}")

    # 1. Load active plots from sample plot loader
    active_sample_plots = load_sample_plots(sample_plots_path, active_only=True)
    active_plot_codes = {p.plot_code for p in active_sample_plots}
    sample_plot_meta = {p.plot_code: p for p in active_sample_plots}

    # 2. Read features CSV and DROP label columns immediately
    raw_df = pd.read_csv(features_path)
    cols_to_drop = [
        c
        for c in raw_df.columns
        if c in LABEL_COLUMNS_TO_DROP or "label" in c.lower() or "stressed" in c.lower()
    ]
    df = raw_df.drop(columns=cols_to_drop)

    plots_created = 0
    plots_updated = 0
    plots_unchanged = 0
    features_upserted = 0
    rejections: list[dict[str, Any]] = []

    # Map of processed plot objects in this session to avoid redundant queries
    cached_plots: dict[str, Plot] = {}

    # Group dataframe rows by plot_code to enforce all-or-nothing plot integrity
    for plot_code, plot_group in df.groupby("plot_code", sort=True):
        if plot_code not in active_plot_codes:
            # Excluded or unrecognized plot: strictly skipped
            continue

        plot_rejections: list[dict[str, Any]] = []
        plot_records_to_upsert: list[dict[str, Any]] = []

        sample_p = sample_plot_meta[str(plot_code)]

        # Validate plot attributes from first row / sample metadata
        first_row = plot_group.iloc[0]
        try:
            area_val = float(first_row.get("area_acre", 2.0))
            lat_val = float(first_row.get("lat", sample_p.lat))
            lon_val = float(first_row.get("lon", sample_p.lon))
            irrigation_val = str(first_row.get("irrigation") or sample_p.irrigation or "tube_well")
            insured_val = int(first_row.get("insured", sample_p.insured))
            crop_val = str(first_row.get("crop") or sample_p.crop or "wheat")
            district_val = str(first_row.get("district") or sample_p.district or "Anand")
            village_val = "Boriavi"

            # Use PlotCreateRequest schema for exact validation
            PlotCreateRequest(
                farmer_id=1,  # Temporary check
                crop=crop_val,
                area_acre=area_val,
                district=district_val,
                village=village_val,
                lat=lat_val,
                lon=lon_val,
                irrigation=irrigation_val,
                insured=insured_val,
            )
        except (ValidationError, ValueError, TypeError) as exc:
            for idx in plot_group.index:
                row_num = idx + 2
                plot_rejections.append(
                    {
                        "row": row_num,
                        "plot_code": plot_code,
                        "reason": f"Plot validation error: {exc}",
                    }
                )
            rejections.extend(plot_rejections)
            continue

        # Inspect all season rows for this plot
        for idx, row in plot_group.iterrows():
            row_num = idx + 2  # 1-based header offset
            season_str = str(row.get("season", "")).strip()

            # Validate cut-off date helper
            try:
                iso_cutoff = get_season_cutoff_iso_date(
                    season_str, DEFAULT_CUTOFF_MONTH, DEFAULT_CUTOFF_DAY
                )
                cutoff_dt = date.fromisoformat(iso_cutoff)
            except ValueError as exc:
                plot_rejections.append(
                    {"row": row_num, "plot_code": plot_code, "reason": f"Cutoff date error: {exc}"}
                )
                continue

            # Provenance & fixture check
            row_provenance: dict[str, Any] = {}
            has_fixture = False
            for col in SOURCE_COLUMNS:
                if col in row and pd.notna(row[col]):
                    val_str = str(row[col]).strip()
                    row_provenance[col] = val_str
                    if val_str.lower() == "fixture":
                        has_fixture = True

            if has_fixture:
                if not allow_fixture:
                    plot_rejections.append(
                        {
                            "row": row_num,
                            "plot_code": plot_code,
                            "reason": "Fixture provenance detected without --allow-fixture",
                        }
                    )
                    continue
                else:
                    print(f"Warning: Row {row_num} for plot {plot_code} has fixture provenance.")

            # Extract feature dict: strictly non-label, non-metadata columns
            feat_dict: dict[str, Any] = {}
            for col in df.columns:
                if col not in METADATA_NON_FEATURE_COLUMNS and col not in LABEL_COLUMNS_TO_DROP:
                    feat_dict[col] = sanitize_json_value(row[col])

            plot_records_to_upsert.append(
                {
                    "season": season_str,
                    "cutoff_date": cutoff_dt,
                    "feature_set_version": FEATURE_SET_VERSION,
                    "features": feat_dict,
                    "provenance": row_provenance,
                }
            )

        # Atomic plot safety: if any row from this plot failed, reject all rows for this plot
        if plot_rejections:
            rejections.extend(plot_rejections)
            continue

        # Check or create Farmer
        farmer_display = f"SAMPLE-FARMER-{plot_code}"
        farmer_stmt = select(Farmer).where(Farmer.display_name == farmer_display)
        farmer = session.execute(farmer_stmt).scalar_one_or_none()
        if farmer is None:
            farmer = Farmer(
                display_name=farmer_display,
                village=village_val,
                district=district_val,
            )
            session.add(farmer)
            session.flush()

        # Check or create Plot
        plot_stmt = select(Plot).where(Plot.plot_code == plot_code)
        plot = session.execute(plot_stmt).scalar_one_or_none()
        if plot is None:
            plot = Plot(
                plot_code=plot_code,
                farmer_id=farmer.id,
                crop=crop_val,
                area_acre=area_val,
                lat=lat_val,
                lon=lon_val,
                irrigation=irrigation_val,
                insured=insured_val,
            )
            if hasattr(Plot, "status"):
                plot.status = getattr(sample_p, "status", "active")
            if hasattr(Plot, "crop_basis"):
                plot.crop_basis = "synthetic"

            session.add(plot)
            session.flush()
            plots_created += 1
        else:
            # Check for attribute updates
            is_changed = False
            if plot.area_acre != area_val:
                plot.area_acre = area_val
                is_changed = True
            if plot.lat != lat_val:
                plot.lat = lat_val
                is_changed = True
            if plot.lon != lon_val:
                plot.lon = lon_val
                is_changed = True
            if plot.irrigation != irrigation_val:
                plot.irrigation = irrigation_val
                is_changed = True
            if plot.insured != insured_val:
                plot.insured = insured_val
                is_changed = True

            if is_changed:
                plots_updated += 1
                session.flush()
            else:
                plots_unchanged += 1

        cached_plots[str(plot_code)] = plot

        # Upsert PlotSeasonFeatures
        for item in plot_records_to_upsert:
            feat_stmt = select(PlotSeasonFeatures).where(
                PlotSeasonFeatures.plot_id == plot.id,
                PlotSeasonFeatures.season == item["season"],
            )
            psf = session.execute(feat_stmt).scalar_one_or_none()
            if psf is None:
                psf = PlotSeasonFeatures(
                    plot_id=plot.id,
                    season=item["season"],
                    cutoff_date=item["cutoff_date"],
                    feature_set_version=item["feature_set_version"],
                    features=item["features"],
                    provenance=item["provenance"],
                    imported_at=datetime.now(UTC),
                )
                session.add(psf)
            else:
                psf.cutoff_date = item["cutoff_date"]
                psf.feature_set_version = item["feature_set_version"]
                psf.features = item["features"]
                psf.provenance = item["provenance"]
                psf.imported_at = datetime.now(UTC)

            features_upserted += 1

        session.flush()

    if dry_run:
        session.rollback()
    else:
        session.commit()

    return {
        "plots_created": plots_created,
        "plots_updated": plots_updated,
        "plots_unchanged": plots_unchanged,
        "features_upserted": features_upserted,
        "rejections": rejections,
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import active plots and pre-cutoff seasonal features into the database."
    )
    parser.add_argument(
        "--features-path",
        type=Path,
        default=Path("data/processed/features.csv"),
        help="Path to features CSV file (default: data/processed/features.csv)",
    )
    parser.add_argument(
        "--sample-plots-path",
        type=Path,
        default=Path("data/synthetic/sample_plots.csv"),
        help="Path to sample_plots.csv (default: data/synthetic/sample_plots.csv)",
    )
    parser.add_argument(
        "--allow-fixture",
        action="store_true",
        help="Allow rows with fixture provenance (prints a warning).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Execute parsing and validation in transaction but rollback without saving.",
    )
    args = parser.parse_args()

    engine = create_db_engine()
    with Session(bind=engine) as session:
        summary = import_plots_and_features(
            session,
            features_path=args.features_path,
            sample_plots_path=args.sample_plots_path,
            allow_fixture=args.allow_fixture,
            dry_run=args.dry_run,
        )

    print("\n=== Plot and Features Import Summary ===")
    print(f"Dry Run:           {summary['dry_run']}")
    print(f"Plots Created:     {summary['plots_created']}")
    print(f"Plots Updated:     {summary['plots_updated']}")
    print(f"Plots Unchanged:   {summary['plots_unchanged']}")
    print(f"Features Upserted: {summary['features_upserted']}")
    print(f"Rows Rejected:     {len(summary['rejections'])}")

    if summary["rejections"]:
        print("\nRejections detail:")
        for r in summary["rejections"]:
            print(f"  - Row {r['row']} (plot {r['plot_code']}): {r['reason']}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
