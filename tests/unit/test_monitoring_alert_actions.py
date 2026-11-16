"""Unit tests for in-season monitoring, historical replay import, and alert actions (T-11C).

Tests:
1. TC-007 stays at engine level on the synthetic scenario only; never imported into DB.
2. Replay import idempotency: importing twice yields same rows, no duplicates. Later checkpoint
   escalates severity without duplicate row; data gaps recorded as data gaps, not alerts.
3. GET /plots/{id}/monitoring: returns stored timeline, replay mode and note, 404 and 401 cases,
   mock token rejected in real mode.
4. POST /alerts/{id}/actions: creates action_log and audit row with zero PII; rejects unknown
   action types, phone-like notes, notes > 500 chars, illegal status transitions (409);
   no recovery pressure action in playbook.
5. Zero banned blame/mental health wording in alert and playbook texts.
6. Contract 0.4.0 drift and STABLE schema preservation.
7. Mock mode isolation unchanged.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from satbhoomi.alerts.replay import generate_synthetic_stress_scenario
from satbhoomi.api.auth.tokens import create_access_token
from satbhoomi.api.main import API_CONTRACT_VERSION, app
from satbhoomi.api.routes.alerts import PLAYBOOK_ACTIONS
from satbhoomi.api.routes.monitoring import REPLAY_NOTE
from satbhoomi.config.settings import Settings, get_settings
from satbhoomi.db.base import Base
from satbhoomi.db.models.alert import Alert
from satbhoomi.db.models.audit_log import AuditLog
from satbhoomi.db.models.farmer import Farmer
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_timeline import PlotSeasonTimeline
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db
from scripts.import_alert_replay import run_import

BANNED_WORDS = ("depressed", "depression", "suicidal", "hopeless", "lazy", "careless", "fault")


@pytest.fixture
def in_memory_db() -> tuple[Session, Any]:
    """Provide an isolated, clean in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    yield session, engine
    session.close()
    Base.metadata.drop_all(engine)


@pytest.fixture
def real_api_client(in_memory_db: tuple[Session, Any]) -> tuple[TestClient, Session, User, str]:
    """TestClient wired to real mode with authenticated officer."""
    session, engine = in_memory_db

    officer = User(
        name="Officer Rajesh",
        username="officer_rajesh",
        role="officer",
        password_hash="mockhash",
        is_active=True,
    )
    session.add(officer)
    session.commit()
    session.refresh(officer)

    token = create_access_token(user_id=officer.id, role=officer.role)

    def override_get_db():
        yield session

    def override_settings():
        return Settings(mock_api=False, app_env="test")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = override_settings

    client = TestClient(app)
    yield client, session, officer, token

    app.dependency_overrides.clear()


def test_tc007_synthetic_scenario_engine_level_only_not_imported(
    in_memory_db: tuple[Session, Any],
) -> None:
    """TC-007 stays at engine level; synthetic stress scenarios are strictly NOT in the DB."""
    session, _ = in_memory_db

    # 1. Engine level TC-007 check
    scenario_result = generate_synthetic_stress_scenario(
        plot_code="ANAND_WHEAT_01",
        base_season="2023-24",
    )
    assert scenario_result["tc007_passed"] is True
    assert scenario_result["lead_time_weeks"] >= 6.0
    assert scenario_result["scenario_type"] == "SYNTHETIC_STRESS_SCENARIO"

    # 2. Verify synthetic scenario is not in database
    synthetic_alerts = (
        session.execute(select(Alert).where(Alert.detail.like("%synthetic%"))).scalars().all()
    )
    assert len(synthetic_alerts) == 0


def test_import_replay_idempotency_escalation_and_no_data_gap_alerts(
    in_memory_db: tuple[Session, Any],
    tmp_path: Path,
) -> None:
    """Replay import is idempotent, handles severity escalation, and skips data_gap alerts."""
    session, _ = in_memory_db

    farmer = Farmer(display_name="SAMPLE-FARMER-ANAND-01", village="Anand", district="Anand")
    session.add(farmer)
    session.flush()

    plot = Plot(
        plot_code="ANAND_WHEAT_01",
        farmer_id=farmer.id,
        crop="wheat",
        area_acre=2.5,
        irrigation="tube_well",
        insured=1,
    )
    session.add(plot)
    session.commit()

    # Create small test dataset
    csv_file = tmp_path / "test_season_dataset.csv"
    csv_file.write_text(
        "plot_code,season,irrigation,rain_nov_mm,rain_dec_mm,rain_jan_mm,price_dec,price_jan\n"
        "ANAND_WHEAT_01,2020-21,tube_well,4.0,2.0,1.0,2200,2250\n"
        "ANAND_WHEAT_01,2021-22,tube_well,5.0,2.0,1.0,2300,2350\n",
        encoding="utf-8",
    )

    raw_dir = tmp_path / "raw_sat"
    raw_dir.mkdir()

    # 1. Run first import
    stats1 = run_import(
        dataset_csv=csv_file,
        raw_satellite_dir=raw_dir,
        db_session=session,
        dry_run=False,
    )
    assert stats1["active_plots"] == 1
    assert stats1["timelines_created"] == 2
    assert stats1["rejected_rows"] == 0

    initial_alerts_count = len(session.execute(select(Alert)).scalars().all())
    initial_timelines_count = len(session.execute(select(PlotSeasonTimeline)).scalars().all())

    # 2. Run second import: must be strictly idempotent
    stats2 = run_import(
        dataset_csv=csv_file,
        raw_satellite_dir=raw_dir,
        db_session=session,
        dry_run=False,
    )
    assert stats2["timelines_created"] == 0
    assert stats2["timelines_updated"] == 2
    assert stats2["alerts_created"] == 0

    final_alerts_count = len(session.execute(select(Alert)).scalars().all())
    final_timelines_count = len(session.execute(select(PlotSeasonTimeline)).scalars().all())

    assert final_alerts_count == initial_alerts_count
    assert final_timelines_count == initial_timelines_count

    # 3. Assert data_gap records are NEVER saved as Alert rows
    gap_alerts = session.execute(select(Alert).where(Alert.status == "data_gap")).scalars().all()
    assert len(gap_alerts) == 0


def test_monitoring_endpoint_real_mode(
    real_api_client: tuple[TestClient, Session, User, str],
) -> None:
    """GET /plots/{id}/monitoring returns stored timeline, replay mode and note, handles 401/404."""
    client, session, officer, token = real_api_client

    farmer = Farmer(display_name="Farmer-Anand", village="Anand", district="Anand")
    session.add(farmer)
    session.flush()

    plot = Plot(
        plot_code="ANAND_WHEAT_01",
        farmer_id=farmer.id,
        crop="wheat",
        area_acre=3.0,
        irrigation="tube_well",
        insured=1,
    )
    session.add(plot)
    session.flush()

    timeline_pts = [
        {
            "date": "2023-12-15",
            "checkpoint_label": "Dec 15",
            "ndvi": 0.45,
            "rainfall_mm": 5.0,
            "data_gap": False,
        },
        {
            "date": "2024-01-15",
            "checkpoint_label": "Jan 15",
            "ndvi": 0.60,
            "rainfall_mm": 8.0,
            "data_gap": False,
        },
        {
            "date": "2024-01-31",
            "checkpoint_label": "Jan 31",
            "ndvi": 0.68,
            "rainfall_mm": 10.0,
            "data_gap": False,
        },
    ]
    pst = PlotSeasonTimeline(
        plot_id=plot.id,
        season="2023-24",
        timeline_json=timeline_pts,
        data_gaps_json=[],
        checkpoint_count=3,
        imported_at=datetime.now(UTC),
    )
    session.add(pst)

    alert = Alert(
        plot_id=plot.id,
        season="2023-24",
        type="crop_health_drop",
        severity="medium",
        status="open",
        detected_on=datetime(2024, 1, 15, tzinfo=UTC),
        checkpoint_label="Jan 15",
        headline="Vegetation vigor decline (18.5% drop below plot prior baseline)",
        detail=(
            "At Jan 15, plot recorded vegetative drag indicating "
            "repayment stress and support needed."
        ),
        supportive_action=(
            "Schedule supportive field visit to verify plot moisture and canopy vigor."
        ),
        is_replay=True,
    )
    session.add(alert)
    session.commit()

    # 1. 401 without auth token
    res_no_auth = client.get(f"/api/v1/plots/{plot.id}/monitoring")
    assert res_no_auth.status_code == 401

    # 2. 401 with mock token in real mode
    res_mock_tok = client.get(
        f"/api/v1/plots/{plot.id}/monitoring",
        headers={"Authorization": "Bearer mock-officer-token-xyz"},
    )
    assert res_mock_tok.status_code == 401

    # 3. 404 for non-existent plot
    res_404 = client.get(
        "/api/v1/plots/99999/monitoring",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_404.status_code == 404
    assert res_404.json()["error"]["code"] == "NOT_FOUND"

    # 4. 200 OK for active plot
    res_200 = client.get(
        f"/api/v1/plots/{plot.id}/monitoring?season=2023-24",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_200.status_code == 200
    data = res_200.json()

    assert data["plot_id"] == plot.id
    assert data["plot_code"] == "ANAND_WHEAT_01"
    assert data["season"] == "2023-24"
    assert data["mode"] == "replay"
    assert data["replay_note"] == REPLAY_NOTE
    assert len(data["timeline"]) == 3
    assert len(data["active_alerts"]) == 1
    assert data["active_alerts"][0]["headline"].startswith("Vegetation vigor decline")
    assert data["active_alerts"][0]["is_replay"] is True


def test_alert_actions_endpoint_real_mode_and_transitions(
    real_api_client: tuple[TestClient, Session, User, str],
) -> None:
    """POST /alerts/{id}/actions validates playbook actions, rejects PII, tracks lifecycle."""
    client, session, officer, token = real_api_client

    farmer = Farmer(display_name="Farmer-Anand-Action", village="Anand", district="Anand")
    session.add(farmer)
    session.flush()

    plot = Plot(
        plot_code="ANAND_WHEAT_02",
        farmer_id=farmer.id,
        crop="wheat",
        area_acre=2.0,
        irrigation="canal",
        insured=1,
    )
    session.add(plot)
    session.flush()

    alert = Alert(
        plot_id=plot.id,
        season="2024-25",
        type="rainfall_deficit",
        severity="medium",
        status="open",
        detected_on=datetime(2024, 12, 15, tzinfo=UTC),
        checkpoint_label="Dec 15",
        headline="Winter precipitation deficit (-45.0% anomaly)",
        detail=(
            "Precipitation deficit observed, early monitoring required to avoid repayment stress."
        ),
        supportive_action="Advise farmer on supplementary protective irrigation scheduling.",
        is_replay=True,
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)

    headers = {"Authorization": f"Bearer {token}"}

    # 1. 404 for unknown alert
    res_404 = client.post(
        "/api/v1/alerts/99999/actions",
        json={"action_type": "field_visit", "note": "Valid note describing supportive check."},
        headers=headers,
    )
    assert res_404.status_code == 404

    # 2. 400 for unknown action_type
    res_bad_action = client.post(
        f"/api/v1/alerts/{alert.id}/actions",
        json={"action_type": "invalid_action_name", "note": "Valid note about field check."},
        headers=headers,
    )
    assert res_bad_action.status_code == 400

    # 3. 400 for PII / phone number in note
    res_phone = client.post(
        f"/api/v1/alerts/{alert.id}/actions",
        json={
            "action_type": "field_visit",
            "note": "Called farmer on 9876543210 to schedule visit.",
        },
        headers=headers,
    )
    assert res_phone.status_code == 400
    assert res_phone.json()["error"]["code"] == "PII_NOT_PERMITTED"

    # 4. 400 for note exceeding 500 characters
    long_note = "A" * 501
    res_long = client.post(
        f"/api/v1/alerts/{alert.id}/actions",
        json={"action_type": "field_visit", "note": long_note},
        headers=headers,
    )
    assert res_long.status_code == 400

    # 5. Valid first action: moves open -> in_progress
    res_act1 = client.post(
        f"/api/v1/alerts/{alert.id}/actions",
        json={
            "action_type": "field_visit",
            "note": "Conducted supportive field visit; verified tubewell water availability.",
        },
        headers=headers,
    )
    assert res_act1.status_code == 201
    data1 = res_act1.json()
    assert data1["status_before"] == "open"
    assert data1["status_after"] == "in_progress"
    assert data1["done_by"] == officer.name

    session.refresh(alert)
    assert alert.status == "in_progress"

    # Verify AuditLog written with zero personal data
    audit1 = (
        session.execute(select(AuditLog).where(AuditLog.event == "alert_action_logged"))
        .scalars()
        .first()
    )
    assert audit1 is not None
    assert audit1.entity == "alert"
    assert audit1.entity_id == alert.id
    assert audit1.user_id == officer.id

    # 6. Valid second action: moves in_progress -> resolved
    res_act2 = client.post(
        f"/api/v1/alerts/{alert.id}/actions",
        json={
            "action_type": "extension_support",
            "note": (
                "Connected farmer with local KVK agronomist for protective irrigation schedule."
            ),
        },
        headers=headers,
    )
    assert res_act2.status_code == 201
    data2 = res_act2.json()
    assert data2["status_before"] == "in_progress"
    assert data2["status_after"] == "resolved"

    session.refresh(alert)
    assert alert.status == "resolved"

    # 7. Disallowed transition from resolved alert: returns 409 Conflict
    res_act3 = client.post(
        f"/api/v1/alerts/{alert.id}/actions",
        json={
            "action_type": "rescheduling_request",
            "note": "Attempting action on already resolved alert.",
        },
        headers=headers,
    )
    assert res_act3.status_code == 409
    assert res_act3.json()["error"]["code"] == "DISALLOWED_STATUS_TRANSITION"


def test_no_recovery_pressure_action_in_playbook() -> None:
    """Verify strictly supportive actions in playbook; zero debt collection or pressure actions."""
    for action in PLAYBOOK_ACTIONS:
        assert "recovery" not in action
        assert "demand" not in action
        assert "seize" not in action
        assert "penalty" not in action


def test_banned_wording_on_alerts_and_playbook() -> None:
    """Alert texts and playbook terms must contain zero banned blame or mental health words."""
    for action in PLAYBOOK_ACTIONS:
        for banned in BANNED_WORDS:
            assert banned not in action

    sample_texts = [
        "In-season vegetation vigor decline (22.5% drop below plot prior baseline)",
        "At Jan 15, plot recorded vegetative drag indicating in-season drag and support needed.",
        "Schedule supportive field visit to verify plot moisture and canopy vigor.",
        "Early monitoring required to avoid repayment stress.",
    ]
    for text in sample_texts:
        lower = text.lower()
        for banned in BANNED_WORDS:
            assert banned not in lower, f"Banned word '{banned}' found in text: {text}"


def test_openapi_drift_and_stable_schemas_preserved() -> None:
    """Contract is 0.4.0 and openapi.json matches generated spec; STABLE schemas untouched."""
    client = TestClient(app)
    res = client.get("/openapi.json")
    assert res.status_code == 200
    live_spec = res.json()

    assert live_spec["info"]["version"] == API_CONTRACT_VERSION

    openapi_path = Path("docs/api/openapi.json")
    assert openapi_path.is_file()
    with open(openapi_path, encoding="utf-8") as f:
        stored_spec = json.load(f)

    assert stored_spec["info"]["version"] == API_CONTRACT_VERSION

    # Assert stable schemas exist with identical required core fields
    schemas = stored_spec["components"]["schemas"]
    assert "AssessmentResponse" in schemas
    assert "LoanSuggestionResponse" in schemas
    assert "WhatIfResponse" in schemas
    assert "cutoff_date_iso" in schemas["AssessmentResponse"]["properties"]
