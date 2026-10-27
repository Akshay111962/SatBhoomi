"""Unit tests for SQLAlchemy database models and constraint enforcement."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from satbhoomi.db.base import Base
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
from scripts.seed_synthetic import seed_synthetic_data


@pytest.fixture
def db_session() -> Session:
    """Fixture providing an isolated in-memory SQLite database session with FKs enabled."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # Enable SQLite foreign key enforcement
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON;"))

    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_area_acre_zero_or_negative_rejected(db_session: Session) -> None:
    """Verify CHECK(area_acre > 0) rejects 0 and negative acreages."""
    farmer = Farmer(display_name="Farmer-Test-Area", village="TestV", district="TestD")
    db_session.add(farmer)
    db_session.commit()

    # Zero area
    zero_plot = Plot(farmer_id=farmer.id, crop="wheat", area_acre=0.0)
    db_session.add(zero_plot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Negative area
    neg_plot = Plot(farmer_id=farmer.id, crop="wheat", area_acre=-2.5)
    db_session.add(neg_plot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicate_plot_season_rejected(db_session: Session) -> None:
    """Verify UNIQUE(plot_id, season) constraint prevents duplicate observation records."""
    farmer = Farmer(display_name="Farmer-Test-Dup", village="TestV", district="TestD")
    db_session.add(farmer)
    db_session.commit()

    plot = Plot(farmer_id=farmer.id, crop="wheat", area_acre=3.0)
    db_session.add(plot)
    db_session.commit()

    obs1 = SeasonObservation(plot_id=plot.id, season="2024-rabi", ndvi_mean=0.65)
    db_session.add(obs1)
    db_session.commit()

    obs2 = SeasonObservation(plot_id=plot.id, season="2024-rabi", ndvi_mean=0.70)
    db_session.add(obs2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_assessment_without_model_version_rejected(db_session: Session) -> None:
    """Verify NOT NULL constraint on assessment.model_version is enforced."""
    farmer = Farmer(display_name="Farmer-Test-Ass", village="TestV", district="TestD")
    db_session.add(farmer)
    db_session.commit()

    plot = Plot(farmer_id=farmer.id, crop="wheat", area_acre=2.0)
    db_session.add(plot)
    db_session.commit()

    # Assessment with model_version=None
    ass = Assessment(
        plot_id=plot.id,
        model_version=None,  # type: ignore[arg-type]
        score=75.0,
        band="medium",
        reasons_json={"reasons": ["Test reason"]},
        loan_suggestion_json={"limit": 50000},
    )
    db_session.add(ass)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_role_band_severity_status_rejected(db_session: Session) -> None:
    """Verify CHECK constraints on controlled categorical values."""
    # Invalid user role
    invalid_user = User(
        name="Bad Role User",
        role="superadmin",  # Allowed: 'officer', 'admin'
        password_hash="hash",
    )
    db_session.add(invalid_user)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Setup valid farmer and plot
    farmer = Farmer(display_name="Farmer-Check-Vals", village="V", district="D")
    db_session.add(farmer)
    db_session.commit()

    plot = Plot(farmer_id=farmer.id, crop="wheat", area_acre=2.0)
    db_session.add(plot)
    db_session.commit()

    # Invalid assessment band
    invalid_ass = Assessment(
        plot_id=plot.id,
        model_version="v0.1",
        score=50.0,
        band="critical",  # Allowed: 'low', 'medium', 'high'
        reasons_json={},
        loan_suggestion_json={},
    )
    db_session.add(invalid_ass)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Invalid alert severity
    invalid_alert_sev = Alert(
        plot_id=plot.id,
        type="crop_health_drop",
        severity="extreme",  # Allowed: 'low', 'medium', 'high'
        status="open",
    )
    db_session.add(invalid_alert_sev)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Invalid alert status
    invalid_alert_stat = Alert(
        plot_id=plot.id,
        type="crop_health_drop",
        severity="high",
        status="in_progress",  # Allowed: 'open', 'acknowledged', 'resolved', 'dismissed'
    )
    db_session.add(invalid_alert_stat)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_farmer_cascade_deletion(db_session: Session) -> None:
    """Verify deleting a farmer cascades and purges all related plots, observations, and alerts."""
    farmer = Farmer(display_name="Farmer-To-Delete", village="V", district="D")
    db_session.add(farmer)
    db_session.commit()

    consent = Consent(
        farmer_id=farmer.id,
        purpose="Test consent",
        given_on=datetime.now(UTC),
    )
    db_session.add(consent)
    db_session.commit()

    plot = Plot(farmer_id=farmer.id, crop="wheat", area_acre=3.0)
    db_session.add(plot)
    db_session.commit()

    obs = SeasonObservation(plot_id=plot.id, season="2024-rabi", ndvi_mean=0.6)
    db_session.add(obs)

    ass = Assessment(
        plot_id=plot.id,
        model_version="v0.1",
        score=80.0,
        band="low",
        reasons_json={"reason": "test"},
        loan_suggestion_json={"limit": 100000},
    )
    db_session.add(ass)
    db_session.flush()

    what_if = WhatIf(
        assessment_id=ass.id,
        changed_input="insured",
        old_value="0",
        new_value="1",
        new_score=85.0,
    )
    db_session.add(what_if)

    alert = Alert(
        plot_id=plot.id,
        type="rainfall_deficit",
        severity="medium",
        status="open",
    )
    db_session.add(alert)
    db_session.flush()

    action = ActionLog(
        alert_id=alert.id,
        action_type="visit",
        note="Farmer contacted",
    )
    db_session.add(action)

    audit = AuditLog(
        event="farmer_created",
        entity="farmer",
        entity_id=farmer.id,
    )
    db_session.add(audit)
    db_session.commit()

    # Record primary keys
    farmer_id = farmer.id
    consent_id = consent.id
    plot_id = plot.id
    obs_id = obs.id
    ass_id = ass.id
    what_if_id = what_if.id
    alert_id = alert.id
    action_id = action.id
    audit_id = audit.id

    # Pre-deletion assertions
    assert db_session.scalar(select(Plot.id).where(Plot.farmer_id == farmer_id)) is not None
    assert db_session.scalar(select(Consent.id).where(Consent.farmer_id == farmer_id)) is not None

    # Delete the farmer
    db_session.delete(farmer)
    db_session.commit()
    db_session.expunge_all()

    # Post-deletion assertions (Cascade verification)
    assert db_session.scalar(select(Farmer.id).where(Farmer.id == farmer_id)) is None
    assert db_session.scalar(select(Consent.id).where(Consent.id == consent_id)) is None
    assert db_session.scalar(select(Plot.id).where(Plot.id == plot_id)) is None
    assert (
        db_session.scalar(select(SeasonObservation.id).where(SeasonObservation.id == obs_id))
        is None
    )
    assert db_session.scalar(select(Assessment.id).where(Assessment.id == ass_id)) is None
    assert db_session.scalar(select(WhatIf.id).where(WhatIf.id == what_if_id)) is None
    assert db_session.scalar(select(Alert.id).where(Alert.id == alert_id)) is None
    assert db_session.scalar(select(ActionLog.id).where(ActionLog.id == action_id)) is None

    # Audit log entry persists (immutable bank compliance record)
    retained_audit = db_session.scalar(select(AuditLog.id).where(AuditLog.id == audit_id))
    assert retained_audit is not None


def test_seed_synthetic_idempotency() -> None:
    """Verify seed_synthetic_data can execute repeatedly without generating duplicate records."""
    # First execution
    u1, f1, p1, o1 = seed_synthetic_data()
    # Second execution must add 0 duplicate entities
    u2, f2, p2, o2 = seed_synthetic_data()

    assert u2 == 0
    assert f2 == 0
    assert p2 == 0
    assert o2 == 0
