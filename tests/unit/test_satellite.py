"""Unit tests for satellite NDVI connector, data validation, and seasonal aggregation."""

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from satbhoomi.connectors.satellite import (
    FixtureNdviProvider,
    GoogleEarthEngineProvider,
    PlotLocation,
    RawObservation,
    SeasonWindow,
    aggregate_season_observations,
    load_sample_plots,
    validate_observation,
    validate_plot_record,
)

# Reference sample plot and window
SAMPLE_PLOT = PlotLocation(
    plot_code="TEST_PLOT_001",
    lat=22.5645,
    lon=72.9289,
    buffer_m=50.0,
    crop="wheat",
    irrigation="tube_well",
    insured=1,
    district="Anand",
)

SAMPLE_WINDOW = SeasonWindow(
    season_name="2024-25",
    start_date=date(2024, 11, 1),
    end_date=date(2025, 4, 15),
)


# ---------------------------------------------------------------------------
# 1. NDVI Formula & Range Validation
# ---------------------------------------------------------------------------


def test_ndvi_formula_and_range_validation() -> None:
    """Verify standard Sentinel-2 NDVI formula (B8 - B4) / (B8 + B4) and bounds."""

    def compute_ndvi(b8: float, b4: float) -> float:
        denom = b8 + b4
        if denom == 0.0:
            return 0.0
        return (b8 - b4) / denom

    # Standard healthy canopy: NIR=0.40, Red=0.10 -> 0.30 / 0.50 = 0.60
    assert pytest.approx(compute_ndvi(0.40, 0.10)) == 0.60

    # Bare soil / equal reflectance: NIR=0.15, Red=0.15 -> 0.0
    assert pytest.approx(compute_ndvi(0.15, 0.15)) == 0.0

    # Water / negative NDVI: NIR=0.05, Red=0.15 -> -0.10 / 0.20 = -0.50
    assert pytest.approx(compute_ndvi(0.05, 0.15)) == -0.50

    # Theoretical boundaries
    assert -1.0 <= compute_ndvi(0.0, 1.0) <= 1.0
    assert -1.0 <= compute_ndvi(1.0, 0.0) <= 1.0


# ---------------------------------------------------------------------------
# 2. Hand-Checkable Aggregation
# ---------------------------------------------------------------------------


def test_aggregation_correctness_hand_checkable() -> None:
    """Verify statistical aggregation produces exact expected hand-calculated values."""
    observations = [
        # Early window (Nov 1 to Dec 13 = 42 days)
        RawObservation(date=date(2024, 11, 10), ndvi=0.20, is_valid=True),
        RawObservation(date=date(2024, 11, 25), ndvi=0.30, is_valid=True),
        # Cloudy pass (must be excluded from statistics)
        RawObservation(date=date(2024, 12, 20), ndvi=0.55, is_valid=False, scl_class=8),
        # Later season passes
        RawObservation(date=date(2025, 1, 15), ndvi=0.70, is_valid=True),
        RawObservation(date=date(2025, 2, 20), ndvi=0.80, is_valid=True),
    ]

    agg = aggregate_season_observations(
        plot_code="TEST_PLOT_001",
        window=SAMPLE_WINDOW,
        observations=observations,
        source="test_fixture",
        min_valid_obs=4,
    )

    # Valid values: [0.20, 0.30, 0.70, 0.80] -> sum = 2.00, count = 4
    # Mean: 2.00 / 4 = 0.5000
    # Peak: 0.8000
    # Early (Nov 10, Nov 25): (0.20 + 0.30) / 2 = 0.2500
    assert agg.valid_obs_count == 4
    assert agg.ndvi_mean == 0.5000
    assert agg.ndvi_peak == 0.8000
    assert agg.ndvi_early == 0.2500
    assert agg.data_gap is False
    assert agg.source == "test_fixture"
    assert agg.season == "2024-25"


# ---------------------------------------------------------------------------
# 3. All-Cloudy Season Handling
# ---------------------------------------------------------------------------


def test_all_cloudy_season_gives_data_gap_and_no_invented_values() -> None:
    """Verify an all-overcast season sets data_gap=True and does not invent numbers."""
    provider = FixtureNdviProvider(force_cloudy=True)
    raw_obs = provider.fetch_observations(SAMPLE_PLOT, SAMPLE_WINDOW)

    assert len(raw_obs) > 0
    assert all(not obs.is_valid for obs in raw_obs)

    agg = aggregate_season_observations(
        plot_code=SAMPLE_PLOT.plot_code,
        window=SAMPLE_WINDOW,
        observations=raw_obs,
        source=provider.source_name,
    )

    assert agg.valid_obs_count == 0
    assert agg.data_gap is True
    assert agg.ndvi_mean is None
    assert agg.ndvi_peak is None
    assert agg.ndvi_std is None
    assert agg.ndvi_early is None


# ---------------------------------------------------------------------------
# 4. Out-of-Range & Out-of-Window Observation Rejection
# ---------------------------------------------------------------------------


def test_out_of_range_ndvi_rejected() -> None:
    """Verify that NDVI values outside [-1.0, 1.0] are rejected."""
    bad_obs = RawObservation(date=date(2024, 12, 1), ndvi=1.45, is_valid=True)
    with pytest.raises(ValueError, match="violates valid bounds"):
        validate_observation(bad_obs, SAMPLE_WINDOW)

    bad_obs_low = RawObservation(date=date(2024, 12, 1), ndvi=-1.05, is_valid=True)
    with pytest.raises(ValueError, match="violates valid bounds"):
        validate_observation(bad_obs_low, SAMPLE_WINDOW)


def test_out_of_window_date_rejected() -> None:
    """Verify that observation dates outside the cropping window are rejected."""
    out_obs = RawObservation(date=date(2024, 8, 15), ndvi=0.45, is_valid=True)
    with pytest.raises(ValueError, match="falls outside season window"):
        validate_observation(out_obs, SAMPLE_WINDOW)


# ---------------------------------------------------------------------------
# 5. Sample Plots Validation
# ---------------------------------------------------------------------------


def test_sample_plots_validation_catches_bad_coordinates() -> None:
    """Verify coordinate bounding rules for mainland India."""
    # Bad latitude (outside India bounds [6, 38])
    with pytest.raises(ValueError, match="latitude"):
        validate_plot_record(PlotLocation("BAD_LAT", 45.0, 72.9, 50.0))

    # Bad longitude (outside India bounds [68, 98])
    with pytest.raises(ValueError, match="longitude"):
        validate_plot_record(PlotLocation("BAD_LON", 22.5, 60.0, 50.0))


def test_sample_plots_validation_catches_bad_buffer() -> None:
    """Verify buffer limits [30m, 200m]."""
    with pytest.raises(ValueError, match="buffer_m"):
        validate_plot_record(PlotLocation("BAD_BUF_LOW", 22.5, 72.9, 20.0))

    with pytest.raises(ValueError, match="buffer_m"):
        validate_plot_record(PlotLocation("BAD_BUF_HIGH", 22.5, 72.9, 250.0))


def test_sample_plots_loader_detects_duplicate_plot_codes(tmp_path: Path) -> None:
    """Verify CSV loader raises ValueError if duplicate plot_code is present."""
    csv_file = tmp_path / "dup_plots.csv"
    csv_file.write_text(
        "plot_code,lat,lon,buffer_m,crop,irrigation,insured,district\n"
        "PLOT_001,22.5645,72.9289,50,wheat,tube_well,1,Anand\n"
        "PLOT_001,22.5412,72.9156,60,wheat,canal,0,Anand\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate plot_code"):
        load_sample_plots(csv_file)


def test_sample_plots_synthetic_csv_valid() -> None:
    """Verify repository sample_plots.csv loads cleanly with valid records."""
    csv_path = Path(__file__).resolve().parents[2] / "data" / "synthetic" / "sample_plots.csv"
    plots = load_sample_plots(csv_path)
    assert len(plots) >= 3
    codes = [p.plot_code for p in plots]
    assert len(codes) == len(set(codes))


# ---------------------------------------------------------------------------
# 6. CLI Dry-Run
# ---------------------------------------------------------------------------


def test_cli_dry_run_works() -> None:
    """Verify scripts/fetch_ndvi.py --dry-run executes successfully."""
    script_path = Path(__file__).resolve().parents[2] / "scripts" / "fetch_ndvi.py"
    res = subprocess.run(
        [sys.executable, str(script_path), "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    assert "DRY RUN: Validation passed" in res.stderr or "DRY RUN: Validation passed" in res.stdout


# ---------------------------------------------------------------------------
# 7. No Secrets in Code
# ---------------------------------------------------------------------------


def test_no_secret_or_project_id_in_code_or_fixtures() -> None:
    """Verify that satellite package files contain no hardcoded secrets or credentials."""
    package_dir = (
        Path(__file__).resolve().parents[2] / "src" / "satbhoomi" / "connectors" / "satellite"
    )
    forbidden_tokens = ["AIzaSy", "ghp_", "sk-", "service_account"]

    for py_file in package_dir.glob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        for token in forbidden_tokens:
            assert token not in content, f"Possible secret token '{token}' in {py_file.name}"


# ---------------------------------------------------------------------------
# 8. GEE Live Provider Marker
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_gee_provider_marker() -> None:
    """Marked with @pytest.mark.live; skipped in default offline CI test runs."""
    provider = GoogleEarthEngineProvider()
    assert provider.source_name == "gee"
    # Live initialization is only attempted when GEE_PROJECT is set
    if not provider.project_id:
        pytest.skip("GEE_PROJECT not set in environment. Skipping live network test.")
