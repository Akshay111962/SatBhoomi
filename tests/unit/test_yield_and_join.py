"""Unit tests for district yield loader and multi-source seasonal dataset join (T-03)."""

import csv
from pathlib import Path

import pytest

from satbhoomi.connectors.yield_stats import (
    WHEAT_YIELD_MAX_BOUND_KG_HA,
    WHEAT_YIELD_MIN_BOUND_KG_HA,
    YieldDataValidationError,
    load_district_yield_records,
)
from scripts.build_dataset import build_dataset


def test_yield_loader_rejects_missing_file() -> None:
    """Verify yield loader fails loudly with instructions when file is missing."""
    with pytest.raises(
        YieldDataValidationError, match="Action Required: Obtain official district yield"
    ):
        load_district_yield_records(Path("data/external/non_existent_file.csv"))


def test_yield_loader_rejects_invalid_season_format(tmp_path: Path) -> None:
    """Verify yield loader rejects season strings that violate YYYY-YY standard."""
    csv_file = tmp_path / "bad_season.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "district",
                "season",
                "area_ha",
                "production_tonnes",
                "yield_kg_per_ha",
                "source_name",
                "source_url",
                "retrieved_on",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "district": "Anand",
                "season": "2023-2024",  # Should be 2023-24
                "area_ha": "50000",
                "production_tonnes": "175000",
                "yield_kg_per_ha": "3500",
                "source_name": "Test",
                "source_url": "http://test",
                "retrieved_on": "2026-11-04",
            }
        )

    with pytest.raises(YieldDataValidationError, match="Invalid season format"):
        load_district_yield_records(csv_file)


def test_yield_loader_rejects_negative_or_zero_values(tmp_path: Path) -> None:
    """Verify yield loader rejects negative or zero area, production, or yield."""
    csv_file = tmp_path / "neg_area.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "district",
                "season",
                "area_ha",
                "production_tonnes",
                "yield_kg_per_ha",
                "source_name",
                "source_url",
                "retrieved_on",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "district": "Anand",
                "season": "2023-24",
                "area_ha": "-100",  # Negative area
                "production_tonnes": "350",
                "yield_kg_per_ha": "3500",
                "source_name": "Test",
                "source_url": "http://test",
                "retrieved_on": "2026-11-04",
            }
        )

    with pytest.raises(YieldDataValidationError, match="must be strictly positive"):
        load_district_yield_records(csv_file)


def test_yield_loader_rejects_out_of_range_yields(tmp_path: Path) -> None:
    """Verify yield loader rejects physically impossible yields (<500 or >6000 kg/ha)."""
    csv_file = tmp_path / "absurd_yield.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "district",
                "season",
                "area_ha",
                "production_tonnes",
                "yield_kg_per_ha",
                "source_name",
                "source_url",
                "retrieved_on",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "district": "Anand",
                "season": "2023-24",
                "area_ha": "1000",
                "production_tonnes": "10000",
                "yield_kg_per_ha": "10000",  # 10,000 kg/ha exceeds max bound 6000
                "source_name": "Test",
                "source_url": "http://test",
                "retrieved_on": "2026-11-04",
            }
        )

    with pytest.raises(
        YieldDataValidationError, match="falls outside plausible agro-climatic bounds"
    ):
        load_district_yield_records(csv_file)


def test_yield_loader_rejects_inconsistent_production_area_yield(tmp_path: Path) -> None:
    """Verify yield loader catches inconsistency between area, production, and yield > 1%."""
    csv_file = tmp_path / "inconsistent.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "district",
                "season",
                "area_ha",
                "production_tonnes",
                "yield_kg_per_ha",
                "source_name",
                "source_url",
                "retrieved_on",
            ],
        )
        writer.writeheader()
        # Area = 50,000 ha, Production = 150,000 tonnes -> Expected yield = 3,000 kg/ha
        # But reported yield = 3,500 kg/ha (16.7% discrepancy)
        writer.writerow(
            {
                "district": "Anand",
                "season": "2023-24",
                "area_ha": "50000",
                "production_tonnes": "150000",
                "yield_kg_per_ha": "3500",
                "source_name": "Test",
                "source_url": "http://test",
                "retrieved_on": "2026-11-04",
            }
        )

    with pytest.raises(YieldDataValidationError, match="is inconsistent with area"):
        load_district_yield_records(csv_file)


def test_official_district_yield_csv_valid() -> None:
    """Verify that the repository's data/external/district_yield_wheat.csv passes all checks."""
    csv_path = Path("data/external/district_yield_wheat.csv")
    records = load_district_yield_records(csv_path)

    assert len(records) == 5
    seasons = [r.season for r in records]
    assert seasons == ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
    for r in records:
        assert r.district == "Anand"
        assert WHEAT_YIELD_MIN_BOUND_KG_HA <= r.yield_kg_per_ha <= WHEAT_YIELD_MAX_BOUND_KG_HA
        assert r.area_ha > 0
        assert r.production_tonnes > 0


def test_build_dataset_preserves_all_ndvi_rows_and_propagates_gaps(tmp_path: Path) -> None:
    """Verify build_dataset pipeline preserves all skeleton rows and marks gaps appropriately."""
    # 1. Create sample plots
    plots_path = tmp_path / "sample_plots.csv"
    with open(plots_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "plot_code",
                "lat",
                "lon",
                "buffer_m",
                "crop",
                "irrigation",
                "insured",
                "district",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "plot_code": "P1",
                "lat": "22.5",
                "lon": "72.9",
                "buffer_m": "50",
                "crop": "wheat",
                "irrigation": "tube_well",
                "insured": "1",
                "district": "Anand",
            }
        )
        writer.writerow(
            {
                "plot_code": "P2",
                "lat": "22.6",
                "lon": "72.8",
                "buffer_m": "50",
                "crop": "wheat",
                "irrigation": "canal",
                "insured": "0",
                "district": "Anand",
            }
        )

    # 2. Create NDVI base table with 2 seasons for 2 plots = 4 rows
    ndvi_path = tmp_path / "ndvi.csv"
    with open(ndvi_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "plot_code",
                "season",
                "ndvi_mean",
                "ndvi_peak",
                "ndvi_std",
                "ndvi_early",
                "valid_obs_count",
                "data_gap",
                "source",
                "fetched_at",
            ],
        )
        writer.writeheader()
        # P1 2023-24 (complete)
        writer.writerow(
            {
                "plot_code": "P1",
                "season": "2023-24",
                "ndvi_mean": "0.45",
                "ndvi_peak": "0.68",
                "ndvi_std": "0.12",
                "ndvi_early": "0.25",
                "valid_obs_count": "12",
                "data_gap": "False",
                "source": "planetary",
                "fetched_at": "2026-11-04T00:00:00",
            }
        )
        # P1 2024-25 (NDVI gap)
        writer.writerow(
            {
                "plot_code": "P1",
                "season": "2024-25",
                "ndvi_mean": "0.35",
                "ndvi_peak": "0.42",
                "ndvi_std": "0.05",
                "ndvi_early": "0.20",
                "valid_obs_count": "2",
                "data_gap": "True",
                "source": "planetary",
                "fetched_at": "2026-11-04T00:00:00",
            }
        )
        # P2 2023-24
        writer.writerow(
            {
                "plot_code": "P2",
                "season": "2023-24",
                "ndvi_mean": "0.50",
                "ndvi_peak": "0.72",
                "ndvi_std": "0.14",
                "ndvi_early": "0.28",
                "valid_obs_count": "15",
                "data_gap": "False",
                "source": "planetary",
                "fetched_at": "2026-11-04T00:00:00",
            }
        )
        # P2 2024-25
        writer.writerow(
            {
                "plot_code": "P2",
                "season": "2024-25",
                "ndvi_mean": "0.48",
                "ndvi_peak": "0.70",
                "ndvi_std": "0.13",
                "ndvi_early": "0.26",
                "valid_obs_count": "14",
                "data_gap": "False",
                "source": "planetary",
                "fetched_at": "2026-11-04T00:00:00",
            }
        )

    # 3. Create rainfall with only P1 2023-24 and P2 2023-24 (P1 2024-25 and P2 2024-25 missing)
    rainfall_path = tmp_path / "rainfall.csv"
    with open(rainfall_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "plot_code",
                "season",
                "rain_total_mm",
                "rain_early_mm",
                "rain_nov_mm",
                "rain_dec_mm",
                "rain_jan_mm",
                "rain_feb_mm",
                "rain_mar_mm",
                "rain_apr_mm",
                "rain_deficit_pct",
                "valid_days_count",
                "total_days_count",
                "data_gap",
                "source",
                "fetched_at",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "plot_code": "P1",
                "season": "2023-24",
                "rain_total_mm": "22.5",
                "rain_early_mm": "5.0",
                "rain_nov_mm": "5.0",
                "rain_dec_mm": "0.0",
                "rain_jan_mm": "10.0",
                "rain_feb_mm": "0.0",
                "rain_mar_mm": "7.5",
                "rain_apr_mm": "0.0",
                "rain_deficit_pct": "15.38",
                "valid_days_count": "167",
                "total_days_count": "167",
                "data_gap": "False",
                "source": "fixture",
                "fetched_at": "2026-11-04T00:00:00",
            }
        )
        writer.writerow(
            {
                "plot_code": "P2",
                "season": "2023-24",
                "rain_total_mm": "18.0",
                "rain_early_mm": "4.0",
                "rain_nov_mm": "4.0",
                "rain_dec_mm": "0.0",
                "rain_jan_mm": "8.0",
                "rain_feb_mm": "0.0",
                "rain_mar_mm": "6.0",
                "rain_apr_mm": "0.0",
                "rain_deficit_pct": "-7.69",
                "valid_days_count": "167",
                "total_days_count": "167",
                "data_gap": "False",
                "source": "fixture",
                "fetched_at": "2026-11-04T00:00:00",
            }
        )

    # 4. Create Mandi prices for Anand 2023-24 only
    prices_path = tmp_path / "prices.csv"
    with open(prices_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "district",
                "crop",
                "season",
                "price_mean",
                "price_volatility",
                "price_nov",
                "price_dec",
                "price_jan",
                "price_feb",
                "price_mar",
                "price_apr",
                "market_count",
                "reporting_days_count",
                "data_gap",
                "source",
                "fetched_at",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "district": "Anand",
                "crop": "wheat",
                "season": "2023-24",
                "price_mean": "2350.0",
                "price_volatility": "0.045",
                "price_nov": "2320.0",
                "price_dec": "2340.0",
                "price_jan": "2380.0",
                "price_feb": "2390.0",
                "price_mar": "2330.0",
                "price_apr": "2310.0",
                "market_count": "2",
                "reporting_days_count": "25",
                "data_gap": "False",
                "source": "manual_csv",
                "fetched_at": "2026-11-04T00:00:00",
            }
        )

    # 5. Create district yield
    yield_path = tmp_path / "yield.csv"
    with open(yield_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "district",
                "season",
                "area_ha",
                "production_tonnes",
                "yield_kg_per_ha",
                "source_name",
                "source_url",
                "retrieved_on",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "district": "Anand",
                "season": "2023-24",
                "area_ha": "52000",
                "production_tonnes": "184600",
                "yield_kg_per_ha": "3550",
                "source_name": "Test",
                "source_url": "http://test",
                "retrieved_on": "2026-11-04",
            }
        )
        writer.writerow(
            {
                "district": "Anand",
                "season": "2024-25",
                "area_ha": "51000",
                "production_tonnes": "177480",
                "yield_kg_per_ha": "3480",
                "source_name": "Test",
                "source_url": "http://test",
                "retrieved_on": "2026-11-04",
            }
        )

    out_path = tmp_path / "season_dataset.csv"

    ret = build_dataset(
        ndvi_path=ndvi_path,
        plots_path=plots_path,
        rainfall_path=rainfall_path,
        prices_path=prices_path,
        yield_path=yield_path,
        output_path=out_path,
        allow_fixture=True,
    )

    assert ret == 0
    assert out_path.exists()

    # Read output and verify
    with open(out_path, encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 4  # Exactly 4 rows preserved!

        # Check P1 2023-24 is complete
        p1_23 = [r for r in reader if r["plot_code"] == "P1" and r["season"] == "2023-24"][0]
        assert p1_23["data_gap_any"] == "False"
        assert p1_23["completeness_note"] == "complete"
        assert float(p1_23["ndvi_peak"]) == 0.68
        assert float(p1_23["rain_total_mm"]) == 22.5
        assert float(p1_23["price_mean"]) == 2350.0
        assert float(p1_23["yield_kg_per_ha"]) == 3550.0

        # Check P1 2024-25 has gaps (ndvi gap + rainfall missing + mandi price missing)
        p1_24 = [r for r in reader if r["plot_code"] == "P1" and r["season"] == "2024-25"][0]
        assert p1_24["data_gap_any"] == "True"
        assert p1_24["data_gap_ndvi"] == "True"
        assert p1_24["data_gap_rainfall"] == "True"
        assert p1_24["data_gap_price"] == "True"
        assert p1_24["data_gap_yield"] == "False"
        assert "gap:" in p1_24["completeness_note"]
