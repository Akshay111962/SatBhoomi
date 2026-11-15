"""Unit tests for import_plots_features script, cutoff helper, and database cascade."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from alembic import command
from satbhoomi.db.base import Base
from satbhoomi.db.models.farmer import Farmer
from satbhoomi.db.models.plot import Plot
from satbhoomi.db.models.plot_season_features import PlotSeasonFeatures
from satbhoomi.features.config import (
    get_season_cutoff_iso_date,
)
from scripts.import_plots_features import import_plots_and_features


@pytest.fixture
def in_memory_db() -> Session:
    """Create an in-memory SQLite database session with all models created."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Enable foreign key cascade constraints in SQLite
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")

    Base.metadata.create_all(bind=engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_csv_fixtures(tmp_path: Path) -> dict[str, Path]:
    """Create synthetic sample_plots.csv and features.csv fixtures."""
    sample_plots_path = tmp_path / "sample_plots.csv"
    with sample_plots_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "plot_code",
                "lat",
                "lon",
                "buffer_m",
                "crop",
                "irrigation",
                "insured",
                "district",
                "status",
                "exclusion_reason",
                "exclusion_date",
            ]
        )
        writer.writerow(
            [
                "ANAND_WHEAT_01",
                22.5125,
                72.9340,
                50,
                "wheat",
                "tube_well",
                1,
                "Anand",
                "active",
                "",
                "",
            ]
        )
        writer.writerow(
            ["ANAND_WHEAT_02", 22.5280, 72.9515, 60, "wheat", "canal", 1, "Anand", "active", "", ""]
        )
        writer.writerow(
            [
                "EXCLUDED_PLOT_99",
                22.4000,
                72.9000,
                50,
                "wheat",
                "tube_well",
                0,
                "Anand",
                "excluded",
                "Rule R1 non-crop",
                "2026-11-14",
            ]
        )

    features_path = tmp_path / "features.csv"
    with features_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "plot_code",
                "season",
                "district",
                "crop",
                "lat",
                "lon",
                "area_acre",
                "irrigation",
                "insured",
                "ndvi_early",
                "ndvi_pre_cutoff_mean",
                "ndvi_pre_cutoff_std",
                "ndvi_trend_pre_cutoff",
                "rain_pre_cutoff_total_mm",
                "rain_pre_cutoff_deficit_pct",
                "mandi_pre_cutoff_volatility",
                "past_stressed_seasons_count",
                "prev_season_ndvi_peak",
                # Label columns to verify they get dropped
                "stressed",
                "label_unavailable",
                "peak_drop_pct",
                "historical_baseline_ndvi",
            ]
        )
        # Plot 1: 2 seasons
        writer.writerow(
            [
                "ANAND_WHEAT_01",
                "2020-21",
                "Anand",
                "wheat",
                22.5125,
                72.9340,
                1.94,
                "tube_well",
                1,
                0.4123,
                0.5596,
                0.1827,
                0.0059,
                80.1,
                662.86,
                0.0061,
                0,
                "",  # null prev_season_ndvi_peak
                "",  # stressed label
                True,  # label_unavailable
                "",  # peak_drop_pct
                "",  # historical_baseline
            ]
        )
        writer.writerow(
            [
                "ANAND_WHEAT_01",
                "2021-22",
                "Anand",
                "wheat",
                22.5125,
                72.9340,
                1.94,
                "tube_well",
                1,
                0.3572,
                0.4818,
                0.1440,
                0.0047,
                69.5,
                561.90,
                0.0057,
                0,
                0.7680,
                0.0,
                False,
                5.78,
                0.7680,
            ]
        )
        # Plot 2: 1 season
        writer.writerow(
            [
                "ANAND_WHEAT_02",
                "2021-22",
                "Anand",
                "wheat",
                22.5280,
                72.9515,
                2.50,
                "canal",
                1,
                0.3900,
                0.5200,
                0.1200,
                0.0035,
                55.0,
                400.0,
                0.0055,
                0,
                0.7200,
                1.0,
                False,
                18.5,
                0.7200,
            ]
        )
        # Excluded Plot: 1 season
        writer.writerow(
            [
                "EXCLUDED_PLOT_99",
                "2021-22",
                "Anand",
                "wheat",
                22.4000,
                72.9000,
                3.00,
                "tube_well",
                0,
                0.2000,
                0.2500,
                0.0500,
                0.0010,
                30.0,
                200.0,
                0.0050,
                0,
                0.3000,
                0.0,
                False,
                0.0,
                0.3000,
            ]
        )

    return {
        "sample_plots": sample_plots_path,
        "features": features_path,
    }


def test_season_cutoff_iso_date_helper() -> None:
    """Verify cutoff helper outputs correct ISO date for valid seasons and raises on malformed."""
    assert get_season_cutoff_iso_date("2020-21", 1, 31) == "2021-01-31"
    assert get_season_cutoff_iso_date("2021-22", 1, 31) == "2022-01-31"
    assert get_season_cutoff_iso_date("2024-25", 1, 31) == "2025-01-31"

    # Malformed season inputs
    with pytest.raises(ValueError, match="Invalid season format"):
        get_season_cutoff_iso_date("2021")

    with pytest.raises(ValueError, match="Invalid season format"):
        get_season_cutoff_iso_date("2021/22")

    with pytest.raises(ValueError, match="Invalid year span"):
        get_season_cutoff_iso_date("2021-25")

    with pytest.raises(ValueError, match="Invalid season format"):
        get_season_cutoff_iso_date("")

    with pytest.raises(ValueError, match="Season must be a string"):
        get_season_cutoff_iso_date(202122)  # type: ignore


def test_import_twice_idempotence(
    in_memory_db: Session, mock_csv_fixtures: dict[str, Path]
) -> None:
    """Running import twice produces identical row counts, no duplicates, and zero errors."""
    res1 = import_plots_and_features(
        in_memory_db,
        mock_csv_fixtures["features"],
        mock_csv_fixtures["sample_plots"],
    )
    assert res1["plots_created"] == 2
    assert res1["plots_updated"] == 0
    assert res1["plots_unchanged"] == 0
    assert res1["features_upserted"] == 3
    assert len(res1["rejections"]) == 0

    # Second run
    res2 = import_plots_and_features(
        in_memory_db,
        mock_csv_fixtures["features"],
        mock_csv_fixtures["sample_plots"],
    )
    assert res2["plots_created"] == 0
    assert res2["plots_updated"] == 0
    assert res2["plots_unchanged"] == 2
    assert res2["features_upserted"] == 3
    assert len(res2["rejections"]) == 0

    # Verify counts in database
    plots = in_memory_db.execute(select(Plot)).scalars().all()
    assert len(plots) == 2
    features = in_memory_db.execute(select(PlotSeasonFeatures)).scalars().all()
    assert len(features) == 3


def test_label_columns_never_imported(
    in_memory_db: Session, mock_csv_fixtures: dict[str, Path]
) -> None:
    """Label columns are dropped on load and never stored in features JSON."""
    import_plots_and_features(
        in_memory_db,
        mock_csv_fixtures["features"],
        mock_csv_fixtures["sample_plots"],
    )

    features = in_memory_db.execute(select(PlotSeasonFeatures)).scalars().all()
    assert len(features) == 3

    forbidden_keys = {"stressed", "label_unavailable", "peak_drop_pct", "historical_baseline_ndvi"}
    for psf in features:
        feat_dict = psf.features
        for key in feat_dict:
            assert key not in forbidden_keys
            assert "label" not in key.lower()
            assert "stressed" not in key.lower()


def test_excluded_plots_not_imported(
    in_memory_db: Session, mock_csv_fixtures: dict[str, Path]
) -> None:
    """Excluded plots (status != active) are never imported into Plot or PlotSeasonFeatures."""
    import_plots_and_features(
        in_memory_db,
        mock_csv_fixtures["features"],
        mock_csv_fixtures["sample_plots"],
    )

    plot_codes = in_memory_db.execute(select(Plot.plot_code)).scalars().all()
    assert "EXCLUDED_PLOT_99" not in plot_codes
    assert set(plot_codes) == {"ANAND_WHEAT_01", "ANAND_WHEAT_02"}


def test_invalid_row_rejected_atomic_safety(
    in_memory_db: Session, tmp_path: Path, mock_csv_fixtures: dict[str, Path]
) -> None:
    """An invalid row (e.g. area_acre <= 0) is rejected and nothing is half-written."""
    invalid_features = tmp_path / "invalid_features.csv"
    with invalid_features.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "plot_code",
                "season",
                "district",
                "crop",
                "lat",
                "lon",
                "area_acre",
                "irrigation",
                "insured",
                "ndvi_early",
                "ndvi_pre_cutoff_mean",
            ]
        )
        # Invalid row: area_acre = -2.5
        writer.writerow(
            [
                "ANAND_WHEAT_01",
                "2021-22",
                "Anand",
                "wheat",
                22.5125,
                72.934,
                -2.5,
                "tube_well",
                1,
                0.4,
                0.5,
            ]
        )

    res = import_plots_and_features(
        in_memory_db,
        invalid_features,
        mock_csv_fixtures["sample_plots"],
    )
    assert len(res["rejections"]) == 1
    assert res["rejections"][0]["row"] == 2
    assert res["rejections"][0]["plot_code"] == "ANAND_WHEAT_01"
    assert "area_acre" in res["rejections"][0]["reason"]

    # Verify nothing was written for ANAND_WHEAT_01
    plot = in_memory_db.execute(
        select(Plot).where(Plot.plot_code == "ANAND_WHEAT_01")
    ).scalar_one_or_none()
    assert plot is None


def test_fixture_provenance_rejected_without_flag(
    in_memory_db: Session, tmp_path: Path, mock_csv_fixtures: dict[str, Path]
) -> None:
    """Fixture provenance rows are rejected by default unless --allow-fixture is given."""
    fixture_features = tmp_path / "fixture_features.csv"
    with fixture_features.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "plot_code",
                "season",
                "district",
                "crop",
                "lat",
                "lon",
                "area_acre",
                "irrigation",
                "insured",
                "ndvi_early",
                "ndvi_pre_cutoff_mean",
                "ndvi_source",
            ]
        )
        writer.writerow(
            [
                "ANAND_WHEAT_01",
                "2021-22",
                "Anand",
                "wheat",
                22.5125,
                72.934,
                2.0,
                "tube_well",
                1,
                0.4,
                0.5,
                "fixture",
            ]
        )

    # 1. Without allow_fixture -> Rejected
    res1 = import_plots_and_features(
        in_memory_db,
        fixture_features,
        mock_csv_fixtures["sample_plots"],
        allow_fixture=False,
    )
    assert len(res1["rejections"]) == 1
    assert "Fixture provenance detected" in res1["rejections"][0]["reason"]

    # 2. With allow_fixture -> Allowed
    res2 = import_plots_and_features(
        in_memory_db,
        fixture_features,
        mock_csv_fixtures["sample_plots"],
        allow_fixture=True,
    )
    assert len(res2["rejections"]) == 0
    assert res2["features_upserted"] == 1


def test_json_round_trips_to_csv_with_nulls_preserved(
    in_memory_db: Session, mock_csv_fixtures: dict[str, Path]
) -> None:
    """Stored JSON values match input CSV values and preserve nulls."""
    import_plots_and_features(
        in_memory_db,
        mock_csv_fixtures["features"],
        mock_csv_fixtures["sample_plots"],
    )

    psf_season1 = in_memory_db.execute(
        select(PlotSeasonFeatures).where(
            PlotSeasonFeatures.season == "2020-21",
        )
    ).scalar_one()

    # prev_season_ndvi_peak in 2020-21 was empty in CSV -> stored as None
    assert psf_season1.features["prev_season_ndvi_peak"] is None
    assert psf_season1.features["ndvi_early"] == pytest.approx(0.4123)
    assert psf_season1.features["rain_pre_cutoff_total_mm"] == pytest.approx(80.1)
    assert psf_season1.cutoff_date == date(2021, 1, 31)

    psf_season2 = (
        in_memory_db.execute(
            select(PlotSeasonFeatures).where(
                PlotSeasonFeatures.season == "2021-22",
            )
        )
        .scalars()
        .first()
    )
    assert psf_season2.cutoff_date == date(2022, 1, 31)


def test_cascade_deletion(in_memory_db: Session, mock_csv_fixtures: dict[str, Path]) -> None:
    """Deleting a Plot or Farmer cascades to delete plot_season_features rows."""
    import_plots_and_features(
        in_memory_db,
        mock_csv_fixtures["features"],
        mock_csv_fixtures["sample_plots"],
    )

    plot1 = in_memory_db.execute(
        select(Plot).where(Plot.plot_code == "ANAND_WHEAT_01")
    ).scalar_one()

    # 1. Delete plot -> plot_season_features rows for plot1 deleted
    in_memory_db.delete(plot1)
    in_memory_db.commit()

    features_plot1 = (
        in_memory_db.execute(
            select(PlotSeasonFeatures).where(PlotSeasonFeatures.plot_id == plot1.id)
        )
        .scalars()
        .all()
    )
    assert len(features_plot1) == 0

    # 2. Delete farmer for plot2 -> plot2 and its features deleted
    plot2 = in_memory_db.execute(
        select(Plot).where(Plot.plot_code == "ANAND_WHEAT_02")
    ).scalar_one()
    farmer2 = in_memory_db.execute(select(Farmer).where(Farmer.id == plot2.farmer_id)).scalar_one()

    in_memory_db.delete(farmer2)
    in_memory_db.commit()

    remaining_plots = in_memory_db.execute(select(Plot)).scalars().all()
    assert len(remaining_plots) == 0
    remaining_features = in_memory_db.execute(select(PlotSeasonFeatures)).scalars().all()
    assert len(remaining_features) == 0


def test_alembic_migration_upgrade_and_downgrade(tmp_path: Path) -> None:
    """Verify Alembic migration upgrade to e4f5a6b7c8d9 and downgrade to ccd1da2ae408."""
    db_file = tmp_path / "test_migration_features.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    ini_path = Path(__file__).resolve().parents[2] / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head (e4f5a6b7c8d9)
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(db_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "plot_season_features" in tables
    plot_columns = [c["name"] for c in inspector.get_columns("plot")]
    assert "plot_code" in plot_columns

    # 2. Downgrade to ccd1da2ae408
    command.downgrade(alembic_cfg, "ccd1da2ae408")
    inspector = inspect(engine)
    tables_after = inspector.get_table_names()
    assert "plot_season_features" not in tables_after
    plot_columns_after = [c["name"] for c in inspector.get_columns("plot")]
    assert "plot_code" not in plot_columns_after

    # 3. Upgrade back to head
    command.upgrade(alembic_cfg, "head")
    inspector = inspect(engine)
    assert "plot_season_features" in inspector.get_table_names()
