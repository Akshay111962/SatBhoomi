#!/usr/bin/env python3
"""Farmer data erasure CLI script (blueprint FR-013, ADR-8, DPDP Act compliance).

Permanently deletes a farmer record and cascades erasure across all linked
plots, consents, observations, assessments, what-if simulations, alerts, and action logs,
while maintaining an immutable compliance entry in audit_log without personal data.

Usage:
    python scripts/delete_farmer.py --farmer-code SAMPLE-FARMER-ANAND_WHEAT_01 --db ./data/satbhoomi.db
    python scripts/delete_farmer.py --farmer-code SAMPLE-FARMER-ANAND_WHEAT_01 --db ./data/satbhoomi.db --confirm
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import select
from sqlalchemy.orm import Session

from satbhoomi.db.audit import write_audit_log
from satbhoomi.db.models.action_log import ActionLog
from satbhoomi.db.models.alert import Alert
from satbhoomi.db.models.assessment import Assessment
from satbhoomi.db.models.consent import Consent
from satbhoomi.db.models.farmer import Farmer
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_features import PlotSeasonFeatures
from satbhoomi.db.models.plot_season_timeline import PlotSeasonTimeline
from satbhoomi.db.models.season_observation import SeasonObservation
from satbhoomi.db.models.what_if import WhatIf
from satbhoomi.db.session import create_db_engine


def inspect_farmer_cascade_counts(session: Session, farmer: Farmer) -> dict[str, int]:
    """Calculate the exact number of cascading entities linked to this farmer."""
    plots = session.execute(select(Plot).where(Plot.farmer_id == farmer.id)).scalars().all()
    plot_ids = [p.id for p in plots]

    consents_count = session.query(Consent).filter(Consent.farmer_id == farmer.id).count()

    if not plot_ids:
        return {
            "farmers": 1,
            "plots": 0,
            "consents": consents_count,
            "assessments": 0,
            "what_ifs": 0,
            "alerts": 0,
            "action_logs": 0,
            "season_observations": 0,
            "plot_season_features": 0,
            "plot_season_timelines": 0,
        }

    assessments = (
        session.execute(select(Assessment).where(Assessment.plot_id.in_(plot_ids))).scalars().all()
    )
    asm_ids = [a.id for a in assessments]

    alerts = session.execute(select(Alert).where(Alert.plot_id.in_(plot_ids))).scalars().all()
    alert_ids = [al.id for al in alerts]

    what_if_count = (
        session.query(WhatIf).filter(WhatIf.assessment_id.in_(asm_ids)).count() if asm_ids else 0
    )
    action_log_count = (
        session.query(ActionLog).filter(ActionLog.alert_id.in_(alert_ids)).count()
        if alert_ids
        else 0
    )
    obs_count = (
        session.query(SeasonObservation).filter(SeasonObservation.plot_id.in_(plot_ids)).count()
    )
    features_count = (
        session.query(PlotSeasonFeatures).filter(PlotSeasonFeatures.plot_id.in_(plot_ids)).count()
    )
    timelines_count = (
        session.query(PlotSeasonTimeline).filter(PlotSeasonTimeline.plot_id.in_(plot_ids)).count()
    )

    return {
        "farmers": 1,
        "plots": len(plots),
        "consents": consents_count,
        "assessments": len(assessments),
        "what_ifs": what_if_count,
        "alerts": len(alerts),
        "action_logs": action_log_count,
        "season_observations": obs_count,
        "plot_season_features": features_count,
        "plot_season_timelines": timelines_count,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Purge a farmer record and all cascading data.")
    parser.add_argument(
        "--farmer-code", required=True, help="Farmer code or display name to delete"
    )
    parser.add_argument("--db", default=None, help="Target SQLite database file path or URL")
    parser.add_argument(
        "--confirm", action="store_true", help="Explicit confirmation to execute deletion"
    )
    args = parser.parse_args(argv)

    db_arg = args.db
    env_db = os.environ.get("DATABASE_URL")

    # Safety check: Refuse if database URL points to something other than explicit --db unless --confirm is passed
    if not db_arg and not args.confirm:
        print(
            "ERROR: Target database was not explicitly provided with --db. "
            "Refusing execution without explicit database path.",
            file=sys.stderr,
        )
        return 1

    target_url = db_arg or env_db or "sqlite:///./data/satbhoomi.db"
    if not target_url.startswith("sqlite:///") and not target_url.startswith("postgresql"):
        target_url = f"sqlite:///{Path(target_url).resolve().as_posix()}"

    engine = create_db_engine(target_url)

    with Session(engine) as session:
        # Lookup farmer
        farmer_stmt = select(Farmer).where(
            (Farmer.display_name == args.farmer_code)
            | (Farmer.id == int(args.farmer_code) if args.farmer_code.isdigit() else False)
        )
        farmer = session.execute(farmer_stmt).scalar_one_or_none()
        if not farmer:
            print(f"ERROR: Farmer '{args.farmer_code}' not found in database.", file=sys.stderr)
            return 1

        counts = inspect_farmer_cascade_counts(session, farmer)

        print(
            f"\n--- Cascade Erasure Inspection for Farmer: {farmer.display_name} (ID #{farmer.id}) ---"
        )
        for entity_name, count in counts.items():
            print(f"  • {entity_name:25s}: {count}")

        if not args.confirm:
            print("\n[DRY RUN] No records were modified or deleted.")
            print(
                "To permanently delete this farmer and all associated records, re-run with --confirm.\n"
            )
            return 0

        # Execute cascading deletion under ADR-8
        farmer_id = farmer.id
        session.delete(farmer)
        session.flush()

        # Record audit log without personal data
        write_audit_log(
            db=session,
            user_id=None,
            event="farmer_deleted",
            entity="farmer",
            entity_id=farmer_id,
            at=datetime.now(UTC),
        )
        session.commit()

        print(
            f"\n[SUCCESS] Farmer #{farmer_id} ({args.farmer_code}) and all cascading records successfully deleted."
        )
        print("Audit ledger updated with event='farmer_deleted'. No personal data retained.\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
