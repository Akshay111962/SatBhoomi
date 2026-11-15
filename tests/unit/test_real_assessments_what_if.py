"""Fast, offline in-memory tests for real assessment and what-if endpoints (Task T-10 part 2)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from satbhoomi.api.auth.passwords import hash_password
from satbhoomi.api.auth.tokens import create_access_token
from satbhoomi.api.main import app
from satbhoomi.api.mock_data import FAKE_MOCK_TOKEN
from satbhoomi.api.schemas.assessments import AssessmentResponse
from satbhoomi.api.schemas.what_if import WhatIfResponse
from satbhoomi.config.settings import get_settings
from satbhoomi.db.base import Base
from satbhoomi.db.models.assessment import Assessment
from satbhoomi.db.models.audit_log import AuditLog
from satbhoomi.db.models.farmer import Farmer
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_features import PlotSeasonFeatures
from satbhoomi.db.models.user import User
from satbhoomi.db.session import get_db
from satbhoomi.risk.scoring import score_plot_season

SAMPLE_FEATURES_SEASON_1: dict[str, Any] = {
    "ndvi_early": 0.42,
    "ndvi_pre_cutoff_mean": 0.55,
    "ndvi_trend_pre_cutoff": 0.05,
    "ndvi_pre_cutoff_std": 0.02,
    "rain_pre_cutoff_total_mm": 25.0,
    "rain_pre_cutoff_deficit_pct": -5.0,
    "mandi_pre_cutoff_volatility": 0.10,
    "past_stressed_seasons_count": 0,
    "prev_season_ndvi_peak": 0.65,
    "prior_seasons_count": 0,
}

SAMPLE_FEATURES_SEASON_2: dict[str, Any] = {
    "ndvi_early": 0.45,
    "ndvi_pre_cutoff_mean": 0.58,
    "ndvi_trend_pre_cutoff": 0.06,
    "ndvi_pre_cutoff_std": 0.02,
    "ndvi_pre_cutoff_baseline": 0.55,
    "rain_pre_cutoff_total_mm": 30.0,
    "rain_pre_cutoff_deficit_pct": -2.0,
    "mandi_pre_cutoff_volatility": 0.08,
    "past_stressed_seasons_count": 0,
    "prev_season_ndvi_peak": 0.68,
    "prior_seasons_count": 1,
}

SAMPLE_FEATURES_SEASON_5: dict[str, Any] = {
    "ndvi_early": 0.48,
    "ndvi_pre_cutoff_mean": 0.60,
    "ndvi_trend_pre_cutoff": 0.07,
    "ndvi_pre_cutoff_std": 0.03,
    "ndvi_pre_cutoff_baseline": 0.58,
    "rain_pre_cutoff_total_mm": 40.0,
    "rain_pre_cutoff_deficit_pct": 5.0,
    "mandi_pre_cutoff_volatility": 0.05,
    "past_stressed_seasons_count": 0,
    "prev_season_ndvi_peak": 0.70,
    "prior_seasons_count": 4,
}


@pytest.fixture
def test_db_session():
    """In-memory SQLite database session with full schema initialized."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)

    with Session(bind=engine) as session:
        yield session

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def real_client(test_db_session: Session, monkeypatch: pytest.MonkeyPatch):
    """FastAPI TestClient configured with MOCK_API=false and overridden database."""
    monkeypatch.setenv("MOCK_API", "false")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32-bytes-minimum-length-ok")
    get_settings.cache_clear()

    def _override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def officer_user(test_db_session: Session) -> tuple[User, str]:
    """Create test officer user and return (User, JWT token)."""
    user = User(
        username="officer_alice",
        name="Officer Alice",
        role="officer",
        password_hash=hash_password("officer_pass_123"),
        is_active=True,
    )
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)

    token = create_access_token(user_id=user.id, role=user.role)
    return user, token


@pytest.fixture
def seeded_plot(test_db_session: Session) -> Plot:
    """Create a farmer and active plot with stored seasonal features."""
    farmer = Farmer(
        display_name="SAMPLE-FARMER-ANAND-01",
        village="Anand",
        district="Anand",
        created_at=datetime.now(UTC),
    )
    test_db_session.add(farmer)
    test_db_session.flush()

    plot = Plot(
        farmer_id=farmer.id,
        plot_code="ANAND_WHEAT_01",
        crop="wheat",
        area_acre=2.5,
        lat=22.5125,
        lon=72.9340,
        irrigation="tube_well",
        insured=1,
        created_at=datetime.now(UTC),
    )
    test_db_session.add(plot)
    test_db_session.flush()

    # Season 1 (2020-21) -> insufficient_data baseline
    psf1 = PlotSeasonFeatures(
        plot_id=plot.id,
        season="2020-21",
        cutoff_date=date(2021, 1, 31),
        feature_set_version="v1.0-pre-cutoff-jan31",
        features=SAMPLE_FEATURES_SEASON_1,
        provenance={"source": "sentinel2"},
        imported_at=datetime.now(UTC),
    )
    # Season 2 (2021-22) -> ok score
    psf2 = PlotSeasonFeatures(
        plot_id=plot.id,
        season="2021-22",
        cutoff_date=date(2022, 1, 31),
        feature_set_version="v1.0-pre-cutoff-jan31",
        features=SAMPLE_FEATURES_SEASON_2,
        provenance={"source": "sentinel2"},
        imported_at=datetime.now(UTC),
    )
    # Season 5 (2024-25) -> ok score
    psf5 = PlotSeasonFeatures(
        plot_id=plot.id,
        season="2024-25",
        cutoff_date=date(2025, 1, 31),
        feature_set_version="v1.0-pre-cutoff-jan31",
        features=SAMPLE_FEATURES_SEASON_5,
        provenance={"source": "sentinel2"},
        imported_at=datetime.now(UTC),
    )
    test_db_session.add_all([psf1, psf2, psf5])
    test_db_session.commit()
    test_db_session.refresh(plot)
    return plot


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------


def test_tc004_determinism_same_plot_and_season(
    real_client: TestClient, officer_user: tuple[User, str], seeded_plot: Plot
) -> None:
    """TC-004: Scoring same plot/season twice produces identical score, band, and reasons."""
    _, token = officer_user
    headers = {"Authorization": f"Bearer {token}"}

    resp1 = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={"season": "2024-25"},
        headers=headers,
    )
    assert resp1.status_code == 201
    data1 = resp1.json()

    resp2 = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={"season": "2024-25"},
        headers=headers,
    )
    assert resp2.status_code == 201
    data2 = resp2.json()

    assert data1["score"] == data2["score"]
    assert data1["band"] == data2["band"]
    assert data1["status"] == data2["status"] == "ok"
    assert [r["text"] for r in data1["reasons"]] == [r["text"] for r in data2["reasons"]]


def test_golden_check_three_plot_seasons_match_direct_scoring(
    real_client: TestClient, officer_user: tuple[User, str], seeded_plot: Plot
) -> None:
    """API result for 3 plot-seasons equals calling scoring function directly on same stored row."""
    _, token = officer_user
    headers = {"Authorization": f"Bearer {token}"}

    seasons = ["2020-21", "2021-22", "2024-25"]
    feature_map = {
        "2020-21": SAMPLE_FEATURES_SEASON_1,
        "2021-22": SAMPLE_FEATURES_SEASON_2,
        "2024-25": SAMPLE_FEATURES_SEASON_5,
    }

    for s in seasons:
        resp = real_client.post(
            f"/api/v1/plots/{seeded_plot.id}/assessments",
            json={"season": s},
            headers=headers,
        )
        assert resp.status_code == 201
        api_data = resp.json()

        direct_input = dict(feature_map[s])
        direct_input["plot_code"] = seeded_plot.plot_code
        direct_input["season"] = s
        direct_input["crop"] = seeded_plot.crop
        direct_input["area_acre"] = float(seeded_plot.area_acre)
        direct_input["irrigation"] = seeded_plot.irrigation
        direct_input["insured"] = 1 if seeded_plot.insured else 0

        direct_res = score_plot_season(direct_input, scorer="rules_baseline")
        assert api_data["status"] == direct_res.status
        assert api_data["score"] == direct_res.score
        assert api_data["band"] == direct_res.band
        assert api_data["insufficient_data_reason"] == direct_res.insufficient_data_reason


def test_label_blindness_and_season_1_insufficient_data(
    real_client: TestClient, officer_user: tuple[User, str], seeded_plot: Plot
) -> None:
    """No label fields; Season 1 returns status='insufficient_data' with no score."""
    _, token = officer_user
    headers = {"Authorization": f"Bearer {token}"}

    resp = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={"season": "2020-21"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()

    # Validate against AssessmentResponse contract schema
    validated = AssessmentResponse.model_validate(data)
    assert validated.status == "insufficient_data"
    assert validated.score is None
    assert validated.band is None
    assert validated.cutoff_date_iso == "2021-01-31"
    assert validated.loan_suggestion is not None
    assert validated.loan_suggestion.status == "manual_appraisal_required"


def test_auth_and_not_found_handling(
    real_client: TestClient, officer_user: tuple[User, str], seeded_plot: Plot
) -> None:
    """404 for unknown/inactive plot or missing features; 401 without token; mock token rejected."""
    _, token = officer_user
    headers = {"Authorization": f"Bearer {token}"}

    # 401 Unauthorized without header
    r_no_auth = real_client.post(f"/api/v1/plots/{seeded_plot.id}/assessments", json={})
    assert r_no_auth.status_code == 401

    # Mock token rejected in real mode
    r_mock = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={},
        headers={"Authorization": f"Bearer {FAKE_MOCK_TOKEN}"},
    )
    assert r_mock.status_code == 401

    # 404 Unknown plot
    r_404_plot = real_client.post(
        "/api/v1/plots/9999/assessments", json={"season": "2024-25"}, headers=headers
    )
    assert r_404_plot.status_code == 404

    # 404 Missing season features
    r_404_feat = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={"season": "1999-00"},
        headers=headers,
    )
    assert r_404_feat.status_code == 404


def test_idempotency_key_replay_and_mismatched_rejection(
    real_client: TestClient,
    officer_user: tuple[User, str],
    seeded_plot: Plot,
    test_db_session: Session,
) -> None:
    """Same key replays stored 200 without second row; different request gives 400."""
    _, token = officer_user
    idem_key = "test-idempotency-key-001"
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": idem_key}

    # First call: 201 Created
    r1 = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={"season": "2024-25"},
        headers=headers,
    )
    assert r1.status_code == 201
    created_id = r1.json()["id"]

    # Count rows in DB
    count1 = (
        test_db_session.execute(select(Assessment).where(Assessment.plot_id == seeded_plot.id))
        .scalars()
        .all()
    )
    assert len(count1) == 1

    # Second call with same key and request: 200 OK replay
    r2 = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={"season": "2024-25"},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["id"] == created_id

    # Verify no second row was created
    count2 = (
        test_db_session.execute(select(Assessment).where(Assessment.plot_id == seeded_plot.id))
        .scalars()
        .all()
    )
    assert len(count2) == 1

    # Reusing same idempotency key for a different season: 400 IDEMPOTENCY_KEY_REUSED
    r3 = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={"season": "2021-22"},
        headers=headers,
    )
    assert r3.status_code == 400
    err = r3.json()["error"]
    assert err["code"] == "IDEMPOTENCY_KEY_REUSED"


def test_get_assessment_stored_immutability(
    real_client: TestClient,
    officer_user: tuple[User, str],
    seeded_plot: Plot,
    test_db_session: Session,
) -> None:
    """Stored assessment has model_version, scorer, created_by; GET returns record."""
    user, token = officer_user
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={"season": "2024-25"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    asm_id = create_resp.json()["id"]

    # Verify database fields directly
    stored = (
        test_db_session.execute(select(Assessment).where(Assessment.id == asm_id)).scalars().one()
    )
    assert stored.model_version is not None
    assert stored.scorer == "rules_baseline"
    assert stored.created_by == user.id

    # GET assessment endpoint returns exact stored record
    get_resp = real_client.get(f"/api/v1/assessments/{asm_id}", headers=headers)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["id"] == asm_id
    assert get_data["score"] == int(stored.score)
    assert get_data["band"] == stored.band
    assert get_data["cutoff_date_iso"] == stored.cutoff_date.isoformat()


def test_what_if_allowed_inputs_immutability_and_audit(
    real_client: TestClient,
    officer_user: tuple[User, str],
    seeded_plot: Plot,
    test_db_session: Session,
) -> None:
    """What-if allows insured/irrigation, rejects others, keeps original unchanged."""
    user, token = officer_user
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = real_client.post(
        f"/api/v1/plots/{seeded_plot.id}/assessments",
        json={"season": "2024-25"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    asm_id = create_resp.json()["id"]
    orig_score = create_resp.json()["score"]
    orig_band = create_resp.json()["band"]

    # 1. Invalid input rejected with field name
    r_invalid = real_client.post(
        f"/api/v1/assessments/{asm_id}/what-if",
        json={"changed_input": "ndvi_early", "new_value": "0.99"},
        headers=headers,
    )
    assert r_invalid.status_code == 400
    assert r_invalid.json()["error"]["field"] == "changed_input"

    # 2. Valid simulation: change irrigation to rainfed
    r_valid = real_client.post(
        f"/api/v1/assessments/{asm_id}/what-if",
        json={"changed_input": "irrigation", "new_value": "rainfed"},
        headers=headers,
    )
    assert r_valid.status_code == 200
    what_if_data = r_valid.json()

    # Validate against WhatIfResponse contract schema
    validated_wi = WhatIfResponse.model_validate(what_if_data)
    assert validated_wi.estimate_label == "estimate"
    assert validated_wi.disclaimer is not None
    assert validated_wi.reliability_note is not None
    assert validated_wi.effect_basis in (
        "scorer_input",
        "scenario_assumption",
        "not_modelled",
    )

    # 3. Verify original assessment row in database was NOT changed
    assessment_after = (
        test_db_session.execute(select(Assessment).where(Assessment.id == asm_id)).scalars().one()
    )
    assert int(assessment_after.score) == orig_score
    assert assessment_after.band == orig_band

    # 4. Verify audit rows exist and contain zero personal data
    audit_rows = (
        test_db_session.execute(select(AuditLog).order_by(AuditLog.id.asc())).scalars().all()
    )
    events = [a.event for a in audit_rows]
    assert "assessment_created" in events
    assert "what_if_simulated" in events

    for a in audit_rows:
        assert a.user_id == user.id
        # Zero PII invariant
        assert "password" not in a.event
        assert "Alice" not in a.event
