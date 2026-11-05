"""Unit tests for rainfall connector (T-03)."""

import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from satbhoomi.connectors.rainfall import (
    ANAND_RABI_NORMAL_RAINFALL_MM,
    ChirpsRainfallProvider,
    DailyRainfallRecord,
    FixtureRainfallProvider,
    aggregate_season_rainfall,
)
from satbhoomi.connectors.rainfall.nasa_power_provider import (
    MISSING_VALUE_SENTINEL,
    NasaPowerRainfallProvider,
)
from satbhoomi.connectors.satellite.base import SeasonWindow


@pytest.fixture
def sample_rabi_window() -> SeasonWindow:
    """Standard Rabi season window for 2023-24 (Nov 1 to Apr 15)."""
    return SeasonWindow(
        season_name="2023-24",
        start_date=date(2023, 11, 1),
        end_date=date(2024, 4, 15),
    )


def test_rainfall_aggregation_hand_checked_math(sample_rabi_window: SeasonWindow) -> None:
    """Verify rainfall aggregation against hand-calculated values on known sequence."""
    # 2023-11-01 to 2024-04-15 = 167 days
    total_days = (sample_rabi_window.end_date - sample_rabi_window.start_date).days + 1
    assert total_days == 167

    # Create 167 days of records:
    # 2023-11-05 (early window): 10.0 mm
    # 2023-12-10 (early window, day 40): 5.0 mm
    # 2024-01-15 (main season, day 76): 15.0 mm
    # All other 164 days: 0.0 mm
    records: list[DailyRainfallRecord] = []
    from datetime import timedelta

    cur = sample_rabi_window.start_date
    while cur <= sample_rabi_window.end_date:
        if cur == date(2023, 11, 5):
            rain = 10.0
        elif cur == date(2023, 12, 10):
            rain = 5.0
        elif cur == date(2024, 1, 15):
            rain = 15.0
        else:
            rain = 0.0

        records.append(
            DailyRainfallRecord(
                date=cur,
                precipitation_mm=rain,
                is_valid=True,
                source="test",
            )
        )
        cur += timedelta(days=1)

    # Hand calculations:
    # Total rain: 10 + 5 + 15 = 30.0 mm
    # Early rain (<= 2023-12-12): 10 + 5 = 15.0 mm
    # Monthly: nov=10.0, dec=5.0, jan=15.0, feb=0.0, mar=0.0, apr=0.0
    # Deficit % against baseline 19.5: ((30.0 - 19.5) / 19.5) * 100 = +53.85%
    baseline = 19.5
    agg = aggregate_season_rainfall(
        plot_code="TEST_PLOT_01",
        window=sample_rabi_window,
        records=records,
        source="test_provider",
        baseline_mm=baseline,
    )

    assert agg.rain_total_mm == 30.0
    assert agg.rain_early_mm == 15.0
    assert agg.rain_deficit_pct == 53.85
    assert agg.valid_days_count == 167
    assert agg.total_days_count == 167
    assert agg.data_gap is False
    assert agg.monthly_rain_mm["nov"] == 10.0
    assert agg.monthly_rain_mm["dec"] == 5.0
    assert agg.monthly_rain_mm["jan"] == 15.0
    assert agg.monthly_rain_mm["feb"] == 0.0
    assert agg.monthly_rain_mm["mar"] == 0.0
    assert agg.monthly_rain_mm["apr"] == 0.0


def test_early_rain_matches_exact_6_week_boundary(sample_rabi_window: SeasonWindow) -> None:
    """Verify that early rainfall respects the exact 42-day window boundary."""
    from datetime import timedelta

    records: list[DailyRainfallRecord] = []
    cur = sample_rabi_window.start_date

    # 42 days (6 weeks) after start_date (2023-11-01 + 42 days = 2023-12-13)
    assert sample_rabi_window.early_window_end == date(2023, 12, 13)

    while cur <= sample_rabi_window.end_date:
        # Day on boundary (2023-12-13) has 4.0 mm (should be in early)
        # Day after boundary (2023-12-14) has 6.0 mm (should NOT be in early)
        if cur == date(2023, 12, 13):
            rain = 4.0
        elif cur == date(2023, 12, 14):
            rain = 6.0
        else:
            rain = 0.0

        records.append(
            DailyRainfallRecord(
                date=cur,
                precipitation_mm=rain,
                is_valid=True,
                source="test",
            )
        )
        cur += timedelta(days=1)

    agg = aggregate_season_rainfall(
        plot_code="TEST_EARLY",
        window=sample_rabi_window,
        records=records,
        source="test",
    )

    assert agg.rain_total_mm == 10.0
    assert agg.rain_early_mm == 4.0  # Only day 42 included, day 43 excluded


def test_deficit_pct_correctly_signed(sample_rabi_window: SeasonWindow) -> None:
    """Verify that rain_deficit_pct is negative for drought/deficit and positive for surplus."""
    from datetime import timedelta

    records_deficit: list[DailyRainfallRecord] = []
    cur = sample_rabi_window.start_date
    while cur <= sample_rabi_window.end_date:
        # Only 5.0 mm total rain (vs 19.5 normal) -> deficit
        rain = 5.0 if cur == date(2023, 11, 10) else 0.0
        records_deficit.append(DailyRainfallRecord(date=cur, precipitation_mm=rain, is_valid=True))
        cur += timedelta(days=1)

    agg_def = aggregate_season_rainfall(
        plot_code="DEFICIT_PLOT",
        window=sample_rabi_window,
        records=records_deficit,
        source="test",
        baseline_mm=ANAND_RABI_NORMAL_RAINFALL_MM,
    )

    # ((5.0 - 19.5) / 19.5) * 100 = -74.36%
    assert agg_def.rain_deficit_pct is not None
    assert agg_def.rain_deficit_pct < 0
    assert agg_def.rain_deficit_pct == pytest.approx(-74.36, abs=0.01)


def test_missing_rain_days_set_data_gap_and_never_imputed(sample_rabi_window: SeasonWindow) -> None:
    """Verify that missing days trigger data_gap=True and are never silently imputed with zero."""
    # Only provide 50 days of observations out of 167 total days
    from datetime import timedelta

    records: list[DailyRainfallRecord] = []
    cur = sample_rabi_window.start_date
    for _ in range(50):
        records.append(DailyRainfallRecord(date=cur, precipitation_mm=1.0, is_valid=True))
        cur += timedelta(days=1)

    agg = aggregate_season_rainfall(
        plot_code="GAP_PLOT",
        window=sample_rabi_window,
        records=records,
        source="test",
    )

    assert agg.valid_days_count == 50
    assert agg.total_days_count == 167
    assert agg.data_gap is True
    # Missing months should have None, not 0.0
    assert agg.monthly_rain_mm["jan"] is None
    assert agg.monthly_rain_mm["feb"] is None
    assert agg.monthly_rain_mm["mar"] is None
    assert agg.monthly_rain_mm["apr"] is None


def test_rainfall_rejects_negative_and_out_of_window_values(
    sample_rabi_window: SeasonWindow,
) -> None:
    """Verify untrusted input validation rejecting negative mm or out-of-window dates."""
    # Negative mm
    bad_neg = [
        DailyRainfallRecord(
            date=sample_rabi_window.start_date,
            precipitation_mm=-5.0,
            is_valid=True,
        )
    ]
    with pytest.raises(ValueError, match="cannot be negative"):
        aggregate_season_rainfall("TEST", sample_rabi_window, bad_neg, "test")

    # Out of window date
    bad_date = [
        DailyRainfallRecord(
            date=date(2023, 10, 15),  # October is outside Nov 1 start
            precipitation_mm=10.0,
            is_valid=True,
        )
    ]
    with pytest.raises(ValueError, match="falls outside season window"):
        aggregate_season_rainfall("TEST", sample_rabi_window, bad_date, "test")


def test_chirps_stub_raises_not_implemented(sample_rabi_window: SeasonWindow) -> None:
    """Verify CHIRPS stub provider raises NotImplementedError."""
    provider = ChirpsRainfallProvider()
    assert provider.source_name == "chirps"
    with pytest.raises(NotImplementedError, match="unbuilt integration stub"):
        provider.fetch_daily_rainfall(22.5, 72.9, sample_rabi_window)


def test_fixture_rainfall_provider_deterministic(sample_rabi_window: SeasonWindow) -> None:
    """Verify fixture rainfall provider produces deterministic results across invocations."""
    provider = FixtureRainfallProvider()
    res1 = provider.fetch_daily_rainfall(22.5645, 72.9289, sample_rabi_window)
    res2 = provider.fetch_daily_rainfall(22.5645, 72.9289, sample_rabi_window)

    assert len(res1) == 167
    assert len(res2) == 167
    for r1, r2 in zip(res1, res2, strict=True):
        assert r1.date == r2.date
        assert r1.precipitation_mm == r2.precipitation_mm
        assert r1.is_valid == r2.is_valid


# ---------------------------------------------------------------------------
# NasaPowerRainfallProvider — offline cache-path tests
# These tests write a JSON fixture to tmp_path and exercise the cache-read
# and parsing paths without any live network calls.
# ---------------------------------------------------------------------------


def _build_precip_dict(window: SeasonWindow, default_mm: float = 0.0) -> dict:
    """Build a date-keyed precipitation dict for a full season window."""
    result: dict = {}
    cur = window.start_date
    while cur <= window.end_date:
        result[cur.strftime("%Y%m%d")] = default_mm
        cur += timedelta(days=1)
    return result


def _write_power_cache(
    tmp_path: Path, lat: float, lon: float, window: SeasonWindow, precip_dict: dict
) -> None:
    """Write a NASA POWER-shaped JSON file to the expected cache location."""
    payload = {"properties": {"parameter": {"PRECTOTCORR": precip_dict}}}
    cache_file = tmp_path / f"power_{lat:.4f}_{lon:.4f}_{window.season_name}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)


def test_nasa_power_provider_parses_cached_json(
    tmp_path: Path, sample_rabi_window: SeasonWindow
) -> None:
    """NasaPowerRainfallProvider parses cached NASA POWER JSON correctly (no network)."""
    lat, lon = 22.5125, 72.9340
    precip_dict = _build_precip_dict(sample_rabi_window)
    # Set one rainy day: 5.0 mm on Nov 15
    precip_dict[date(2023, 11, 15).strftime("%Y%m%d")] = 5.0
    _write_power_cache(tmp_path, lat, lon, sample_rabi_window, precip_dict)

    provider = NasaPowerRainfallProvider(cache_dir=tmp_path)
    records = provider.fetch_daily_rainfall(lat, lon, sample_rabi_window)

    assert len(records) == 167
    rain_days = [r for r in records if r.precipitation_mm and r.precipitation_mm > 0]
    assert len(rain_days) == 1
    assert rain_days[0].date == date(2023, 11, 15)
    assert rain_days[0].precipitation_mm == 5.0
    assert rain_days[0].is_valid is True
    assert all(r.source == "nasa_power" for r in records)


def test_nasa_power_provider_handles_missing_value_sentinel(
    tmp_path: Path, sample_rabi_window: SeasonWindow
) -> None:
    """Sentinel -999.0 values are converted to None and flagged invalid (never imputed)."""
    lat, lon = 22.5125, 72.9340
    precip_dict = _build_precip_dict(sample_rabi_window, default_mm=MISSING_VALUE_SENTINEL)
    _write_power_cache(tmp_path, lat, lon, sample_rabi_window, precip_dict)

    provider = NasaPowerRainfallProvider(cache_dir=tmp_path)
    records = provider.fetch_daily_rainfall(lat, lon, sample_rabi_window)

    assert len(records) == 167
    assert all(r.precipitation_mm is None for r in records)
    assert all(r.is_valid is False for r in records)


def test_nasa_power_provider_raises_on_bad_json_format(
    tmp_path: Path, sample_rabi_window: SeasonWindow
) -> None:
    """ValueError is raised when cached JSON does not match NASA POWER schema."""
    lat, lon = 22.5125, 72.9340
    # Deliberately bad JSON — missing 'properties' key
    cache_file = tmp_path / f"power_{lat:.4f}_{lon:.4f}_{sample_rabi_window.season_name}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"wrong_key": {}}, f)

    provider = NasaPowerRainfallProvider(cache_dir=tmp_path)
    with pytest.raises(ValueError, match="Unexpected NASA POWER response format"):
        provider.fetch_daily_rainfall(lat, lon, sample_rabi_window)


def test_nasa_power_provider_skips_out_of_window_dates(
    tmp_path: Path, sample_rabi_window: SeasonWindow
) -> None:
    """Dates outside the season window in the cache are silently skipped."""
    lat, lon = 22.5125, 72.9340
    precip_dict = _build_precip_dict(sample_rabi_window)
    # Add an out-of-window date (October — before Nov 1 start)
    precip_dict["20231015"] = 99.0
    _write_power_cache(tmp_path, lat, lon, sample_rabi_window, precip_dict)

    provider = NasaPowerRainfallProvider(cache_dir=tmp_path)
    records = provider.fetch_daily_rainfall(lat, lon, sample_rabi_window)

    # Out-of-window date must not appear in results
    assert all(r.date >= sample_rabi_window.start_date for r in records)
    assert all(r.date <= sample_rabi_window.end_date for r in records)
    # 99.0 mm day is excluded, so no record should have that value
    assert all(r.precipitation_mm != 99.0 for r in records if r.precipitation_mm is not None)
