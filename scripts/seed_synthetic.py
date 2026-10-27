"""Seed script inserting a small synthetic dataset for local development and testing.

*** SYNTHETIC DATA ONLY ***
No real farmer records, bank account numbers, or national identification data are stored.
All identities and plot geometries in this script are entirely fictional and for testing purposes.

Safe to execute multiple times (idempotent).
"""

import sys
from datetime import UTC, datetime

from sqlalchemy import select

from satbhoomi.db.models import (
    ActionLog,
    Alert,
    Assessment,
    AuditLog,
    Consent,
    Farmer,
    Plot,
    SeasonObservation,
    User,
    WhatIf,
)
from satbhoomi.db.session import SessionLocal


def seed_synthetic_data() -> tuple[int, int, int, int]:
    """Insert synthetic demo data idempotently.

    Returns:
        Tuple of (users_added, farmers_added, plots_added, observations_added)
    """
    session = SessionLocal()
    users_added = 0
    farmers_added = 0
    plots_added = 0
    obs_added = 0

    try:
        # 1. Synthetic System Users (Bank Loan Officer and Branch Admin)
        user_specs = [
            {
                "name": "Officer Demo (Synthetic)",
                "role": "officer",
                "password_hash": "$2b$12$synthetic_officer_demo_hash_not_for_prod",
            },
            {
                "name": "Admin Demo (Synthetic)",
                "role": "admin",
                "password_hash": "$2b$12$synthetic_admin_demo_hash_not_for_prod",
            },
        ]

        users: dict[str, User] = {}
        for spec in user_specs:
            existing_user = session.execute(
                select(User).where(User.name == spec["name"])
            ).scalar_one_or_none()
            if existing_user is None:
                user = User(
                    name=spec["name"],
                    role=spec["role"],
                    password_hash=spec["password_hash"],
                    created_at=datetime.now(UTC),
                )
                session.add(user)
                session.flush()
                users[spec["role"]] = user
                users_added += 1
            else:
                users[spec["role"]] = existing_user

        # 2. Synthetic Farmers (Only synthetic codes, no phone or ID numbers)
        farmer_specs = [
            {"code": "Farmer-001", "village": "Kadi", "district": "Mehsana"},
            {"code": "Farmer-002", "village": "Visnagar", "district": "Mehsana"},
            {"code": "Farmer-003", "village": "Unjha", "district": "Mehsana"},
            {"code": "Farmer-004", "village": "Petlad", "district": "Anand"},
            {"code": "Farmer-005", "village": "Khambhat", "district": "Anand"},
        ]

        farmers: dict[str, Farmer] = {}
        for f_spec in farmer_specs:
            existing_farmer = session.execute(
                select(Farmer).where(Farmer.display_name == f_spec["code"])
            ).scalar_one_or_none()

            if existing_farmer is None:
                farmer = Farmer(
                    display_name=f_spec["code"],
                    village=f_spec["village"],
                    district=f_spec["district"],
                    created_at=datetime.now(UTC),
                )
                session.add(farmer)
                session.flush()

                # Add synthetic consent
                consent = Consent(
                    farmer_id=farmer.id,
                    purpose="Synthetic demo for farm credit scoring (DPDP mock)",
                    given_on=datetime.now(UTC),
                )
                session.add(consent)
                session.flush()

                farmer.consent_id = consent.id
                farmers[f_spec["code"]] = farmer
                farmers_added += 1
            else:
                farmers[f_spec["code"]] = existing_farmer

        # 3. Synthetic Farm Plots (8 plots across the 5 synthetic farmers)
        plot_specs = [
            # Farmer-001
            {
                "farmer": "Farmer-001",
                "crop": "wheat",
                "area": 3.5,
                "irrigation": "drip",
                "insured": 1,
                "lat": 23.298,
                "lon": 72.331,
            },
            {
                "farmer": "Farmer-001",
                "crop": "wheat",
                "area": 2.0,
                "irrigation": "flood",
                "insured": 0,
                "lat": 23.301,
                "lon": 72.335,
            },
            # Farmer-002
            {
                "farmer": "Farmer-002",
                "crop": "wheat",
                "area": 4.2,
                "irrigation": "canal",
                "insured": 1,
                "lat": 23.698,
                "lon": 72.551,
            },
            # Farmer-003
            {
                "farmer": "Farmer-003",
                "crop": "wheat",
                "area": 1.8,
                "irrigation": "tube-well",
                "insured": 0,
                "lat": 23.801,
                "lon": 72.399,
            },
            {
                "farmer": "Farmer-003",
                "crop": "wheat",
                "area": 2.5,
                "irrigation": "drip",
                "insured": 1,
                "lat": 23.805,
                "lon": 72.404,
            },
            # Farmer-004
            {
                "farmer": "Farmer-004",
                "crop": "wheat",
                "area": 5.0,
                "irrigation": "tube-well",
                "insured": 1,
                "lat": 22.474,
                "lon": 72.802,
            },
            {
                "farmer": "Farmer-004",
                "crop": "wheat",
                "area": 1.5,
                "irrigation": "rainfed",
                "insured": 0,
                "lat": 22.480,
                "lon": 72.810,
            },
            # Farmer-005
            {
                "farmer": "Farmer-005",
                "crop": "wheat",
                "area": 3.0,
                "irrigation": "canal",
                "insured": 1,
                "lat": 22.312,
                "lon": 72.619,
            },
        ]

        plots = []
        for p_spec in plot_specs:
            farmer = farmers[p_spec["farmer"]]
            existing_plot = session.execute(
                select(Plot).where(
                    Plot.farmer_id == farmer.id,
                    Plot.lat == p_spec["lat"],
                    Plot.lon == p_spec["lon"],
                )
            ).scalar_one_or_none()

            if existing_plot is None:
                plot = Plot(
                    farmer_id=farmer.id,
                    crop=p_spec["crop"],
                    area_acre=p_spec["area"],
                    irrigation=p_spec["irrigation"],
                    insured=p_spec["insured"],
                    lat=p_spec["lat"],
                    lon=p_spec["lon"],
                    created_at=datetime.now(UTC),
                )
                session.add(plot)
                session.flush()
                plots.append(plot)
                plots_added += 1
            else:
                plots.append(existing_plot)

        # 4. Synthetic Season Observations (2 seasons for each plot: 2023-rabi and 2024-rabi)
        seasons = [
            {
                "season": "2023-rabi",
                "ndvi_mean": 0.58,
                "ndvi_peak": 0.76,
                "ndvi_std": 0.12,
                "rain_total_mm": 165.0,
                "rain_deficit_pct": 8.0,
                "price_mean": 2180.0,
                "yield_district": 3450.0,
            },
            {
                "season": "2024-rabi",
                "ndvi_mean": 0.62,
                "ndvi_peak": 0.81,
                "ndvi_std": 0.11,
                "rain_total_mm": 172.0,
                "rain_deficit_pct": 4.5,
                "price_mean": 2275.0,
                "yield_district": 3580.0,
            },
        ]

        for plot in plots:
            for s_data in seasons:
                existing_obs = session.execute(
                    select(SeasonObservation).where(
                        SeasonObservation.plot_id == plot.id,
                        SeasonObservation.season == s_data["season"],
                    )
                ).scalar_one_or_none()

                if existing_obs is None:
                    # Slight variation based on whether plot is rainfed or irrigated
                    is_rainfed = plot.irrigation == "rainfed"
                    ndvi_adj = -0.15 if is_rainfed else 0.0
                    deficit_adj = 20.0 if is_rainfed else 0.0

                    obs = SeasonObservation(
                        plot_id=plot.id,
                        season=s_data["season"],
                        ndvi_mean=max(0.1, s_data["ndvi_mean"] + ndvi_adj),
                        ndvi_peak=max(0.2, s_data["ndvi_peak"] + ndvi_adj),
                        ndvi_std=s_data["ndvi_std"],
                        rain_total_mm=s_data["rain_total_mm"],
                        rain_deficit_pct=s_data["rain_deficit_pct"] + deficit_adj,
                        price_mean=s_data["price_mean"],
                        yield_district=s_data["yield_district"],
                        created_at=datetime.now(UTC),
                    )
                    session.add(obs)
                    obs_added += 1

        # 5. Sample Credit Assessment & What-If
        if plots:
            p1 = plots[0]
            existing_ass = session.execute(
                select(Assessment).where(Assessment.plot_id == p1.id)
            ).scalar_one_or_none()

            if existing_ass is None:
                ass1 = Assessment(
                    plot_id=p1.id,
                    model_version="rules_baseline_v0.1",
                    score=82.0,
                    band="low",
                    reasons_json={
                        "top_reasons": [
                            "High seasonal peak NDVI (> 0.75) indicates healthy vegetative growth",
                            "Adequate rainfall with low deficit (< 10%)",
                            "Drip irrigation installed mitigating moisture stress",
                        ]
                    },
                    loan_suggestion_json={
                        "suggested_limit_inr": 157500,
                        "scale_of_finance_per_acre": 45000,
                        "repayment_month": "April",
                        "crop_insurance_required": True,
                    },
                    created_by=users.get("officer", None).id if users.get("officer") else None,
                    created_at=datetime.now(UTC),
                )
                session.add(ass1)
                session.flush()

                # Sample What-If
                what_if = WhatIf(
                    assessment_id=ass1.id,
                    changed_input="insured",
                    old_value="1",
                    new_value="0",
                    new_score=71.5,
                    created_at=datetime.now(UTC),
                )
                session.add(what_if)

        # 6. Sample Stress Alert and Action Log (Raksha Module)
        # Find rainfed plot (or plot with lowest area) to attach stress alert
        rainfed_plots = [p for p in plots if p.irrigation == "rainfed"]
        target_alert_plot = rainfed_plots[0] if rainfed_plots else plots[-1]

        existing_alert = session.execute(
            select(Alert).where(Alert.plot_id == target_alert_plot.id)
        ).scalar_one_or_none()

        if existing_alert is None:
            alert = Alert(
                plot_id=target_alert_plot.id,
                type="rainfall_deficit",
                severity="high",
                status="acknowledged",
                detected_on=datetime.now(UTC),
            )
            session.add(alert)
            session.flush()

            # Supportive action log
            action = ActionLog(
                alert_id=alert.id,
                action_type="field_visit",
                note=(
                    "Contacted farmer regarding soil moisture conservation; "
                    "exploring rescheduling support."
                ),
                done_by=users.get("officer", None).id if users.get("officer") else None,
                done_on=datetime.now(UTC),
            )
            session.add(action)

        # 7. Audit Log
        audit = AuditLog(
            user_id=users.get("officer", None).id if users.get("officer") else None,
            event="seed_synthetic_completed",
            entity="system",
            entity_id=0,
            at=datetime.now(UTC),
        )
        session.add(audit)

        session.commit()
        print(
            f"Synthetic seed finished: {users_added} users, {farmers_added} farmers, "
            f"{plots_added} plots, {obs_added} observations created."
        )
        return users_added, farmers_added, plots_added, obs_added

    except Exception as e:
        session.rollback()
        print(f"Error seeding synthetic data: {e}", file=sys.stderr)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_synthetic_data()
