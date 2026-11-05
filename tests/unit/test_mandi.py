"""Unit tests for mandi price connector and manual CSV fallback (T-03)."""

import csv
import json
from datetime import date
from pathlib import Path

import pytest

from satbhoomi.connectors.mandi import (
    CedaPriceProvider,
    DailyMandiRecord,
    FixturePriceProvider,
    ManualCsvPriceProvider,
    aggregate_season_mandi_prices,
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


def test_mandi_aggregation_multiple_markets_same_day(sample_rabi_window: SeasonWindow) -> None:
    """Verify that multiple markets reporting on the same day are averaged into daily price."""
    # Day 1 (Nov 5): Anand APMC = 2000, Umreth APMC = 2100 -> Daily district avg = 2050
    # Day 2 (Nov 12): Anand APMC = 2200, Umreth APMC = 2300 -> Daily district avg = 2250
    records = [
        DailyMandiRecord(
            date=date(2023, 11, 5),
            market="Anand APMC",
            state="Gujarat",
            district="Anand",
            commodity="wheat",
            modal_price=2000.0,
        ),
        DailyMandiRecord(
            date=date(2023, 11, 5),
            market="Umreth APMC",
            state="Gujarat",
            district="Anand",
            commodity="wheat",
            modal_price=2100.0,
        ),
        DailyMandiRecord(
            date=date(2023, 11, 12),
            market="Anand APMC",
            state="Gujarat",
            district="Anand",
            commodity="wheat",
            modal_price=2200.0,
        ),
        DailyMandiRecord(
            date=date(2023, 11, 12),
            market="Umreth APMC",
            state="Gujarat",
            district="Anand",
            commodity="wheat",
            modal_price=2300.0,
        ),
    ]

    # Hand calculation:
    # Daily averages: [2050.0, 2250.0]
    # Mean modal price = (2050 + 2250) / 2 = 2150.0
    # Sample stdev([2050, 2250]) = sqrt(20000) = 141.421356...
    # Volatility CV = 141.421356 / 2150.0 = 0.065777 -> 0.0658
    agg = aggregate_season_mandi_prices(
        district="Anand",
        crop="wheat",
        window=sample_rabi_window,
        records=records,
        source="test",
        min_reporting_days=2,  # set low for this unit test
    )

    assert agg.price_mean == 2150.0
    assert agg.price_volatility == pytest.approx(0.0658, abs=0.0001)
    assert agg.market_count == 2
    assert agg.reporting_days_count == 2
    assert agg.data_gap is False
    assert agg.monthly_prices["nov"] == 2150.0
    assert agg.monthly_prices["dec"] is None


def test_mandi_volatility_formula_is_cv(sample_rabi_window: SeasonWindow) -> None:
    """Verify price volatility computes Sample Coefficient of Variation (stdev / mean)."""
    # 3 days with known values: 100, 200, 300
    # Mean = 200.0
    # Sample stdev = 100.0
    # CV = 100 / 200 = 0.50
    records = [
        DailyMandiRecord(
            date=date(2023, 11, 10),
            market="Anand APMC",
            state="Gujarat",
            district="Anand",
            commodity="wheat",
            modal_price=100.0,
        ),
        DailyMandiRecord(
            date=date(2023, 11, 20),
            market="Anand APMC",
            state="Gujarat",
            district="Anand",
            commodity="wheat",
            modal_price=200.0,
        ),
        DailyMandiRecord(
            date=date(2023, 11, 30),
            market="Anand APMC",
            state="Gujarat",
            district="Anand",
            commodity="wheat",
            modal_price=300.0,
        ),
    ]

    agg = aggregate_season_mandi_prices(
        district="Anand",
        crop="wheat",
        window=sample_rabi_window,
        records=records,
        source="test",
        min_reporting_days=3,
    )

    assert agg.price_mean == 200.0
    assert agg.price_volatility == 0.50


def test_mandi_data_gap_when_reporting_days_below_threshold(
    sample_rabi_window: SeasonWindow,
) -> None:
    """Verify that fewer than 10 reporting days flags data_gap=True."""
    # Only 5 reporting days
    records = [
        DailyMandiRecord(
            date=date(2023, 11, 5 + i),
            market="Anand APMC",
            state="Gujarat",
            district="Anand",
            commodity="wheat",
            modal_price=2100.0,
        )
        for i in range(5)
    ]

    agg = aggregate_season_mandi_prices(
        district="Anand",
        crop="wheat",
        window=sample_rabi_window,
        records=records,
        source="test",
        min_reporting_days=10,
    )

    assert agg.reporting_days_count == 5
    assert agg.data_gap is True


def test_manual_csv_provider_loads_and_filters(
    tmp_path: Path, sample_rabi_window: SeasonWindow
) -> None:
    """Verify manual CSV provider properly loads and filters matching records."""
    csv_file = tmp_path / "mandi_test.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "market",
                "state",
                "district",
                "commodity",
                "modal_price",
                "min_price",
                "max_price",
                "arrivals_tonnes",
            ],
        )
        writer.writeheader()
        # Row 1: Matching
        writer.writerow(
            {
                "date": "2023-11-15",
                "market": "Anand APMC",
                "state": "Gujarat",
                "district": "Anand",
                "commodity": "wheat",
                "modal_price": "2150.0",
                "min_price": "2100.0",
                "max_price": "2200.0",
                "arrivals_tonnes": "45.0",
            }
        )
        # Row 2: Different crop (must be filtered out)
        writer.writerow(
            {
                "date": "2023-11-15",
                "market": "Anand APMC",
                "state": "Gujarat",
                "district": "Anand",
                "commodity": "mustard",
                "modal_price": "5400.0",
                "min_price": "5300.0",
                "max_price": "5500.0",
                "arrivals_tonnes": "10.0",
            }
        )
        # Row 3: Different district (must be filtered out)
        writer.writerow(
            {
                "date": "2023-11-15",
                "market": "Rajkot APMC",
                "state": "Gujarat",
                "district": "Rajkot",
                "commodity": "wheat",
                "modal_price": "2200.0",
                "min_price": "2150.0",
                "max_price": "2250.0",
                "arrivals_tonnes": "80.0",
            }
        )

    provider = ManualCsvPriceProvider(csv_path=csv_file)
    results = provider.fetch_prices("wheat", "Gujarat", "Anand", sample_rabi_window)

    assert len(results) == 1
    assert results[0].market == "Anand APMC"
    assert results[0].modal_price == 2150.0
    assert results[0].commodity == "wheat"


def test_manual_csv_provider_rejects_missing_columns(
    tmp_path: Path, sample_rabi_window: SeasonWindow
) -> None:
    """Verify that manual CSV provider rejects files missing required schema columns."""
    csv_file = tmp_path / "bad_columns.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "market", "modal_price"])
        writer.writeheader()
        writer.writerow({"date": "2023-11-15", "market": "Anand", "modal_price": "2000"})

    provider = ManualCsvPriceProvider(csv_path=csv_file)
    with pytest.raises(ValueError, match="missing required columns"):
        provider.fetch_prices("wheat", "Gujarat", "Anand", sample_rabi_window)


def test_ceda_provider_raises_clear_error_when_key_missing(
    sample_rabi_window: SeasonWindow,
) -> None:
    """Verify CEDA provider raises descriptive error when CEDA_API_KEY is unset or empty."""
    provider = CedaPriceProvider(api_key="")

    with pytest.raises(ValueError, match="CEDA_API_KEY environment variable is not configured"):
        provider.fetch_prices("wheat", "Gujarat", "Anand", sample_rabi_window)


def test_fixture_price_provider_returns_multi_market_records(
    sample_rabi_window: SeasonWindow,
) -> None:
    """Verify fixture provider generates multi-market records across the season."""
    provider = FixturePriceProvider()
    records = provider.fetch_prices("wheat", "Gujarat", "Anand", sample_rabi_window)

    assert len(records) > 50
    markets = {r.market for r in records}
    assert "Anand APMC" in markets
    assert "Umreth APMC" in markets
    assert all(1800 <= r.modal_price <= 3000 for r in records)


def test_ceda_provider_parses_cached_json(tmp_path: Path, sample_rabi_window: SeasonWindow) -> None:
    """Verify CedaPriceProvider correctly parses a cached JSON response offline."""
    payload = {
        "data": [
            {
                "date": "2023-11-15",
                "market": "Anand APMC",
                "modal_price": "2200.0",
                "min_price": "2150.0",
                "max_price": "2250.0",
                "arrivals_tonnes": "45.0",
            },
            {
                "date": "2023-11-22",
                "market": "Anand APMC",
                "modal_price": "2250.0",
                "min_price": "2200.0",
                "max_price": "2300.0",
                "arrivals_tonnes": "55.0",
            },
        ]
    }

    provider = CedaPriceProvider(api_key="test-key", cache_dir=tmp_path)
    cache_file = tmp_path / f"ceda_wheat_anand_{sample_rabi_window.season_name}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(payload, f)

    records = provider.fetch_prices("wheat", "Gujarat", "Anand", sample_rabi_window)
    assert len(records) == 2
    assert records[0].date == date(2023, 11, 15)
    assert records[0].modal_price == 2200.0
    assert records[0].source == "ceda"
    assert records[1].modal_price == 2250.0
