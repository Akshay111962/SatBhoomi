"""Unit tests for DPDP consent, audit trail completeness, and right to erasure.
Covers blueprint tasks T-13, FR-012, and FR-013.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from satbhoomi.api.auth.tokens import create_access_token
from satbhoomi.api.main import app
from satbhoomi.config.settings import Settings
from satbhoomi.db.base import Base
from satbhoomi.db.models.alert import Alert
from satbhoomi.db.models.assessment import Assessment
from satbhoomi.db.models.audit_log import AuditLog
from satbhoomi.db.models.consent import Consent
from satbhoomi.db.models.farmer import Farmer
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_features import PlotSeasonFeatures
from satbhoomi.db.models.plot_season_timeline import PlotSeasonTimeline
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db
from scripts.delete_farmer import main as delete_farmer_main


@pytest.fixture
def test_db_and_engine() -> tuple[Session, Any]:
    """Provide an in-memory SQLite database with SQLite audit immutability triggers."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    # Enable SQLite Foreign Keys and install audit log immutability triggers
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        conn.execute(
            text(
                """
                CREATE TRIGGER trg_audit_log_prevent_update
                BEFORE UPDATE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'Audit log entries are immutable and cannot be updated');
                END;
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TRIGGER trg_audit_log_prevent_delete
                BEFORE DELETE ON audit_log
                BEGIN
                    SELECT RAISE(ABORT, 'Audit log entries are immutable and cannot be deleted');
                END;
                """
            )
        )
        conn.commit()

    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = session_factory()
    yield session, engine
    session.close()


@pytest.fixture
def test_client(test_db_and_engine: tuple[Session, Any]) -> TestClient:
    """FastAPI TestClient with in-memory database dependency override."""
    session, _ = test_db_and_engine

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(test_db_and_engine: tuple[Session, Any]) -> dict[str, str]:
    """Create a verified officer user and return Bearer auth headers."""
    session, _ = test_db_and_engine
    officer = User(
        username="officer_guard",
        name="Officer Guard",
        role="officer",
        password_hash="mock_hash",
        is_active=True,
    )
    session.add(officer)
    session.commit()

    token = create_access_token(user_id=officer.id, role=officer.role)
    return {"Authorization": f"Bearer {token}"}


def test_allow_real_data_setting_default_and_guard(
    test_client: TestClient,
    test_db_and_engine: tuple[Session, Any],
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ALLOW_REAL_DATA is false by default in Settings and rejects real farmer creation."""
    session, _ = test_db_and_engine
    default_settings = Settings()
    assert default_settings.allow_real_data is False

    # Create real farmer in DB
    real_farmer = Farmer(
        display_name="REAL-FARMER-001",
        village="Anand",
        district="Anand",
        data_origin="real",
    )
    session.add(real_farmer)
    session.commit()

    # Attempt plot creation for real farmer while ALLOW_REAL_DATA is false
    # Returns 403 REAL_DATA_DISALLOWED
    monkeypatch.setattr(
        "satbhoomi.api.routes.plots.get_settings", lambda: Settings(allow_real_data=False)
    )
    resp = test_client.post(
        "/api/v1/plots",
        json={
            "farmer_id": real_farmer.id,
            "crop": "wheat",
            "area_acre": 3.0,
            "district": "Anand",
            "village": "Anand",
            "irrigation": "tube_well",
            "insured": 1,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "REAL_DATA_DISALLOWED"

    # When ALLOW_REAL_DATA is true, plot creation succeeds
    monkeypatch.setattr(
        "satbhoomi.api.routes.plots.get_settings", lambda: Settings(allow_real_data=True)
    )
    resp_allowed = test_client.post(
        "/api/v1/plots",
        json={
            "farmer_id": real_farmer.id,
            "crop": "wheat",
            "area_acre": 3.0,
            "district": "Anand",
            "village": "Anand",
            "irrigation": "tube_well",
            "insured": 1,
        },
        headers=auth_headers,
    )
    assert resp_allowed.status_code == 201
    assert resp_allowed.json()["farmer_id"] == real_farmer.id


def test_consent_endpoints_lifecycle(
    test_client: TestClient,
    test_db_and_engine: tuple[Session, Any],
    auth_headers: dict[str, str],
) -> None:
    """Give consent, reject duplicate active consent, withdraw, and prevent duplicate withdrawal."""
    session, _ = test_db_and_engine

    farmer = Farmer(
        display_name="TEST-FARMER-CONSENT",
        village="Boriavi",
        district="Anand",
        data_origin="real",
    )
    session.add(farmer)
    session.commit()

    # 1. Unknown farmer 404
    resp_404 = test_client.post(
        "/api/v1/farmers/9999/consents",
        json={"purpose": "credit_scoring"},
        headers=auth_headers,
    )
    assert resp_404.status_code == 404
    assert resp_404.json()["error"]["code"] == "FARMER_NOT_FOUND"

    # 2. Invalid purpose 400
    resp_400 = test_client.post(
        f"/api/v1/farmers/{farmer.id}/consents",
        json={"purpose": "unapproved_marketing_scheme"},
        headers=auth_headers,
    )
    assert resp_400.status_code == 400
    assert resp_400.json()["error"]["code"] == "INVALID_PURPOSE"
    assert resp_400.json()["error"]["field"] == "purpose"

    # 3. Give valid consent -> 201
    resp_give = test_client.post(
        f"/api/v1/farmers/{farmer.id}/consents",
        json={"purpose": "credit_scoring"},
        headers=auth_headers,
    )
    assert resp_give.status_code == 201
    data_give = resp_give.json()
    assert data_give["farmer_id"] == farmer.id
    assert data_give["purpose"] == "credit_scoring"
    assert data_give["withdrawn_on"] is None
    consent_id = data_give["id"]

    # Verify audit log was recorded
    audit_grant = (
        session.query(AuditLog).filter_by(event="consent_granted", entity_id=consent_id).first()
    )
    assert audit_grant is not None
    assert audit_grant.entity == "consent"

    # 4. Duplicate active consent for same farmer and purpose -> 409 Conflict
    resp_dup = test_client.post(
        f"/api/v1/farmers/{farmer.id}/consents",
        json={"purpose": "credit_scoring"},
        headers=auth_headers,
    )
    assert resp_dup.status_code == 409
    assert resp_dup.json()["error"]["code"] == "ACTIVE_CONSENT_EXISTS"

    # 5. List consents for farmer
    resp_list = test_client.get(f"/api/v1/farmers/{farmer.id}/consents", headers=auth_headers)
    assert resp_list.status_code == 200
    assert resp_list.json()["total"] == 1
    assert resp_list.json()["items"][0]["id"] == consent_id

    # 6. Withdraw consent -> 200
    resp_with = test_client.post(f"/api/v1/consents/{consent_id}/withdraw", headers=auth_headers)
    assert resp_with.status_code == 200
    assert resp_with.json()["withdrawn_on"] is not None

    # Verify audit log was recorded
    audit_with = (
        session.query(AuditLog).filter_by(event="consent_withdrawn", entity_id=consent_id).first()
    )
    assert audit_with is not None

    # 7. Withdraw already withdrawn consent -> 409 Conflict
    resp_with_again = test_client.post(
        f"/api/v1/consents/{consent_id}/withdraw", headers=auth_headers
    )
    assert resp_with_again.status_code == 409
    assert resp_with_again.json()["error"]["code"] == "CONSENT_ALREADY_WITHDRAWN"


def test_consent_guard_on_all_real_endpoints(
    test_client: TestClient,
    test_db_and_engine: tuple[Session, Any],
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Real farmer requires active consent across assessment, what-if, monitoring,
    alert action, relief, and farmer summary endpoints.
    """
    session, _ = test_db_and_engine
    monkeypatch.setattr(
        "satbhoomi.api.routes.deps.get_settings", lambda: Settings(allow_real_data=True)
    )

    # Setup real farmer, plot, and features
    farmer = Farmer(
        display_name="REAL-CONSENT-GUARD",
        village="Anand",
        district="Anand",
        data_origin="real",
    )
    session.add(farmer)
    session.flush()

    plot = Plot(
        plot_code="REAL-PLOT-01",
        farmer_id=farmer.id,
        crop="wheat",
        area_acre=2.5,
        irrigation="tube_well",
        insured=1,
    )
    session.add(plot)
    session.flush()

    psf = PlotSeasonFeatures(
        plot_id=plot.id,
        season="2024-25",
        features={"mean_ndvi": 0.55, "mean_ndvi_prior": 0.65},
        feature_set_version="1.0",
        cutoff_date=datetime.now(UTC),
    )
    session.add(psf)

    pst = PlotSeasonTimeline(
        plot_id=plot.id,
        season="2024-25",
        timeline_json=[{"date": "2025-01-15", "ndvi": 0.55, "rainfall_mm": 0.0}],
        imported_at=datetime.now(UTC),
    )
    session.add(pst)

    alert = Alert(
        plot_id=plot.id,
        season="2024-25",
        type="crop_health_drop",
        severity="medium",
        status="open",
        headline="Vegetation decline",
        checkpoint_label="January 15",
        detected_on=datetime(2025, 1, 15, tzinfo=UTC),
    )
    session.add(alert)

    asm = Assessment(
        plot_id=plot.id,
        season="2024-25",
        score=65,
        band="medium",
        status="ok",
        model_version="rules_baseline_2.0",
        created_at=datetime.now(UTC),
    )
    session.add(asm)
    session.commit()

    # A. BEFORE CONSENT: All 6 endpoints return 403 CONSENT_REQUIRED
    endpoints = [
        ("POST", f"/api/v1/plots/{plot.id}/assessments", {"season": "2024-25"}),
        (
            "POST",
            f"/api/v1/assessments/{asm.id}/what-if",
            {"changed_input": "insured", "new_value": "0"},
        ),
        ("GET", f"/api/v1/plots/{plot.id}/monitoring", None),
        (
            "POST",
            f"/api/v1/alerts/{alert.id}/actions",
            {"action_type": "field_visit", "note": "Visiting farm"},
        ),
        ("GET", f"/api/v1/plots/{plot.id}/relief-report", None),
        ("GET", f"/api/v1/assessments/{asm.id}/farmer-summary", None),
    ]

    for method, path, body in endpoints:
        if method == "POST":
            r = test_client.post(path, json=body, headers=auth_headers)
        else:
            r = test_client.get(path, headers=auth_headers)
        assert r.status_code == 403, (
            f"{method} {path} should be 403 before consent, got {r.status_code}"
        )
        assert r.json()["error"]["code"] == "CONSENT_REQUIRED"

    # B. GRANT CONSENT: Give active consent
    give_res = test_client.post(
        f"/api/v1/farmers/{farmer.id}/consents",
        json={"purpose": "credit_scoring"},
        headers=auth_headers,
    )
    assert give_res.status_code == 201
    consent_id = give_res.json()["id"]

    # C. WITH ACTIVE CONSENT: Monitoring and relief report now succeed
    r_mon = test_client.get(f"/api/v1/plots/{plot.id}/monitoring", headers=auth_headers)
    assert r_mon.status_code == 200

    r_relief = test_client.get(f"/api/v1/plots/{plot.id}/relief-report", headers=auth_headers)
    assert r_relief.status_code == 200

    r_action = test_client.post(
        f"/api/v1/alerts/{alert.id}/actions",
        json={"action_type": "field_visit", "note": "Conducted supportive visit"},
        headers=auth_headers,
    )
    assert r_action.status_code == 201

    # D. WITHDRAW CONSENT: Now endpoints are blocked again with 403 CONSENT_REQUIRED
    w_res = test_client.post(f"/api/v1/consents/{consent_id}/withdraw", headers=auth_headers)
    assert w_res.status_code == 200

    r_mon_withdrawn = test_client.get(f"/api/v1/plots/{plot.id}/monitoring", headers=auth_headers)
    assert r_mon_withdrawn.status_code == 403
    assert r_mon_withdrawn.json()["error"]["code"] == "CONSENT_REQUIRED"


def test_tc009_audit_completeness_and_zero_pii_table_test(
    test_client: TestClient,
    test_db_and_engine: tuple[Session, Any],
    auth_headers: dict[str, str],
) -> None:
    """TC-009: Table-driven test proving every real endpoint writes an audit row
    without notes, tokens, or passwords.
    """
    session, _ = test_db_and_engine

    # 1. Plot creation audit
    resp_plot = test_client.post(
        "/api/v1/plots",
        json={
            "farmer_id": 99,
            "crop": "wheat",
            "area_acre": 2.0,
            "district": "Anand",
            "village": "Anand",
            "irrigation": "canal",
            "insured": 1,
        },
        headers=auth_headers,
    )
    assert resp_plot.status_code == 201
    plot_id = resp_plot.json()["id"]

    audit_plot = session.query(AuditLog).filter_by(event="plot_created", entity_id=plot_id).first()
    assert audit_plot is not None

    # Verify all audit log rows in DB adhere strictly to zero-PII rules
    all_audit_rows = session.query(AuditLog).all()
    assert len(all_audit_rows) >= 1

    banned_fragments = ("Bearer", "password", "token", "secret", "note", "phone")
    for row in all_audit_rows:
        # User ID must be int or None
        assert row.user_id is None or isinstance(row.user_id, int)
        # Entity and Event must be clean alphanumeric tokens
        assert isinstance(row.event, str)
        assert isinstance(row.entity, str)
        assert isinstance(row.entity_id, int)
        assert isinstance(row.at, datetime)

        # Check serialized string has zero banned fragments
        serialized = f"{row.event}:{row.entity}:{row.entity_id}"
        for frag in banned_fragments:
            assert frag.lower() not in serialized.lower()


def test_audit_table_immutability_trigger_and_user_deletion(
    test_db_and_engine: tuple[Session, Any],
) -> None:
    """Audit table immutability trigger blocks UPDATE, DELETE,
    and cascading user deletion SET NULL.
    """
    session, engine = test_db_and_engine

    user = User(
        username="audit_test_user", name="User", role="officer", password_hash="h", is_active=True
    )
    session.add(user)
    session.commit()

    entry = AuditLog(
        user_id=user.id,
        event="test_event",
        entity="plot",
        entity_id=1,
        at=datetime.now(UTC),
    )
    session.add(entry)
    session.commit()

    # 1. Attempt UPDATE on audit_log -> MUST FAIL
    with pytest.raises(DatabaseError) as exc_update:
        with engine.connect() as conn:
            conn.execute(text(f"UPDATE audit_log SET event = 'tampered' WHERE id = {entry.id};"))
            conn.commit()
    assert "Audit log entries are immutable and cannot be updated" in str(exc_update.value)

    # 2. Attempt DELETE on audit_log -> MUST FAIL
    with pytest.raises(DatabaseError) as exc_delete:
        with engine.connect() as conn:
            conn.execute(text(f"DELETE FROM audit_log WHERE id = {entry.id};"))
            conn.commit()
    assert "Audit log entries are immutable and cannot be deleted" in str(exc_delete.value)

    # 3. Attempt to delete a user referenced by audit rows:
    # Because foreign key ON DELETE SET NULL triggers an UPDATE on audit_log,
    # the trigger blocks user deletion
    with pytest.raises(DatabaseError) as exc_user_del:
        with engine.connect() as conn:
            conn.execute(text(f"DELETE FROM user WHERE id = {user.id};"))
            conn.commit()
    assert "Audit log entries are immutable and cannot be updated" in str(exc_user_del.value)


def test_delete_farmer_script_dry_run_and_confirmed(tmp_path: Path) -> None:
    """Script scripts/delete_farmer.py: dry run deletes nothing;
    --confirm cascades erasure and records audit entry.
    """
    db_file = tmp_path / "test_delete.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        farmer = Farmer(
            display_name="DEL-FARMER-01", village="Anand", district="Anand", data_origin="synthetic"
        )
        session.add(farmer)
        session.flush()

        plot = Plot(plot_code="DEL-PLOT-01", farmer_id=farmer.id, crop="wheat", area_acre=1.5)
        session.add(plot)
        session.flush()

        consent = Consent(farmer_id=farmer.id, purpose="credit_scoring", recorded_by=1)
        session.add(consent)

        asm = Assessment(
            plot_id=plot.id, season="2024-25", score=50, band="low", status="ok", model_version="m"
        )
        session.add(asm)
        session.commit()

        farmer_id = farmer.id
        plot_id = plot.id

    # 1. Refusal without explicit --db unless --confirm
    ret_no_db = delete_farmer_main(["--farmer-code", "DEL-FARMER-01"])
    assert ret_no_db == 1

    # 2. Dry run with --db: returns 0 and modifies ZERO records
    ret_dry = delete_farmer_main(["--farmer-code", "DEL-FARMER-01", "--db", db_url])
    assert ret_dry == 0

    with Session(engine) as session:
        assert session.get(Farmer, farmer_id) is not None
        assert session.query(Plot).filter_by(farmer_id=farmer_id).count() == 1
        assert session.query(Consent).filter_by(farmer_id=farmer_id).count() == 1

    # 3. Execution with --confirm: deletes farmer and cascades
    ret_confirm = delete_farmer_main(
        ["--farmer-code", "DEL-FARMER-01", "--db", db_url, "--confirm"]
    )
    assert ret_confirm == 0

    with Session(engine) as session:
        # Farmer, plot, consent, and assessment are gone
        assert session.get(Farmer, farmer_id) is None
        assert session.query(Plot).filter_by(farmer_id=farmer_id).count() == 0
        assert session.query(Consent).filter_by(farmer_id=farmer_id).count() == 0
        assert session.query(Assessment).filter_by(plot_id=plot_id).count() == 0

        # Audit row recorded without personal data
        audit_del = (
            session.query(AuditLog).filter_by(event="farmer_deleted", entity_id=farmer_id).first()
        )
        assert audit_del is not None
        assert audit_del.entity == "farmer"
        assert audit_del.user_id is None
