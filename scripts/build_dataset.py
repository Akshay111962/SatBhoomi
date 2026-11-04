"""Pipeline script to assemble multi-source seasonal dataset (T-03).

Integrates:
1. Satellite vegetation indices (NDVI) from Sentinel-2 (T-02).
2. Daily precipitation & deficit metrics (NASA POWER / IMD normals).
3. Local APMC mandi modal price & volatility series (Agmarknet / CEDA / manual CSV).
4. Administrative district crop yield statistics (Directorate of Agriculture).
5. Ground sample plot metadata (spatial coordinates, irrigation status, insurance).

Produces:
data/processed/season_dataset.csv
"""

import argparse
import csv
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    sys.path.insert(0, str(PROJECT_ROOT))

from satbhoomi.connectors.satellite.loader import load_sample_plots  # noqa: E402
from satbhoomi.connectors.yield_stats import load_district_yield_records  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_dataset")


def parse_bool(val: object) -> bool:
    """Parse string/bool representation of boolean."""
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    return s in ("true", "1", "t", "yes", "y")


def safe_float(val: object) -> float | None:
    """Parse float safely, returning None if empty or invalid."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan", ""):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def safe_int(val: object) -> int | None:
    """Parse int safely, returning None if empty or invalid."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() in ("none", "null", "nan", ""):
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def build_dataset(
    ndvi_path: Path,
    plots_path: Path,
    rainfall_path: Path,
    prices_path: Path,
    yield_path: Path,
    output_path: Path,
) -> int:
    """Perform deterministic left-join on (plot_code, season) skeleton and write joined dataset."""
    logger.info("Starting multi-source seasonal dataset join...")

    # 1. Load plot metadata
    plots = load_sample_plots(plots_path)
    plots_by_code = {p.plot_code: p for p in plots}
    logger.info("Loaded metadata for %d plots from %s", len(plots_by_code), plots_path)

    # 2. Load district yield statistics
    yield_records = load_district_yield_records(yield_path)
    yield_by_district_season = {(y.district.lower(), y.season): y for y in yield_records}
    logger.info(
        "Loaded %d district yield records from %s",
        len(yield_by_district_season),
        yield_path,
    )

    # 3. Load rainfall aggregates (plot_code, season)
    rainfall_by_plot_season: dict[tuple[str, str], dict[str, str]] = {}
    if rainfall_path.exists():
        with rainfall_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["plot_code"].strip(), row["season"].strip())
                rainfall_by_plot_season[key] = row
        logger.info(
            "Loaded %d rainfall plot-season records from %s",
            len(rainfall_by_plot_season),
            rainfall_path,
        )
    else:
        logger.warning(
            "Rainfall aggregates file not found at %s. Will flag rainfall gap.",
            rainfall_path,
        )

    # 4. Load mandi prices (district, season)
    prices_by_district_season: dict[tuple[str, str], dict[str, str]] = {}
    if prices_path.exists():
        with prices_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row["district"].strip().lower(), row["season"].strip())
                prices_by_district_season[key] = row
        logger.info(
            "Loaded %d mandi price records from %s",
            len(prices_by_district_season),
            prices_path,
        )
    else:
        logger.warning(
            "Mandi prices file not found at %s. Will flag price gap.",
            prices_path,
        )

    # 5. Load NDVI skeleton (base table)
    if not ndvi_path.exists():
        logger.error(
            "NDVI base file missing at %s. Cannot build dataset without NDVI skeleton.",
            ndvi_path,
        )
        return 1

    ndvi_rows: list[dict[str, str]] = []
    with ndvi_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ndvi_rows.append(row)
    logger.info("Loaded %d NDVI plot-season skeleton rows from %s", len(ndvi_rows), ndvi_path)

    # 6. Perform deterministic Left Join on (plot_code, season)
    joined_rows: list[dict[str, object]] = []
    seen_keys: set[tuple[str, str]] = set()

    for ndvi_row in ndvi_rows:
        plot_code = ndvi_row["plot_code"].strip()
        season = ndvi_row["season"].strip()
        pk = (plot_code, season)

        if pk in seen_keys:
            raise ValueError(f"Duplicate primary key ({plot_code}, {season}) in NDVI skeleton.")
        seen_keys.add(pk)

        # Plot metadata
        plot_meta = plots_by_code.get(plot_code)
        district = plot_meta.district if plot_meta else "Anand"
        district_key = district.lower()

        # NDVI features & gap
        ndvi_mean = safe_float(ndvi_row.get("ndvi_mean"))
        ndvi_peak = safe_float(ndvi_row.get("ndvi_peak"))
        ndvi_std = safe_float(ndvi_row.get("ndvi_std"))
        ndvi_early = safe_float(ndvi_row.get("ndvi_early"))
        ndvi_valid_obs = safe_int(ndvi_row.get("valid_obs_count")) or 0
        ndvi_gap = parse_bool(ndvi_row.get("data_gap", "True"))
        ndvi_source = ndvi_row.get("source", "unknown")

        # Rainfall features & gap
        rf_row = rainfall_by_plot_season.get(pk)
        rf_gap = True
        rf_total_mm = None
        rf_early_mm = None
        rf_deficit_pct = None
        rf_valid_days = 0
        rf_total_days = 0
        rf_source = "missing"
        rf_monthly: dict[str, float | None] = dict.fromkeys(
            ("nov", "dec", "jan", "feb", "mar", "apr")
        )

        if rf_row:
            rf_gap = parse_bool(rf_row.get("data_gap", "True"))
            rf_total_mm = safe_float(rf_row.get("rain_total_mm"))
            rf_early_mm = safe_float(rf_row.get("rain_early_mm"))
            rf_deficit_pct = safe_float(rf_row.get("rain_deficit_pct"))
            rf_valid_days = safe_int(rf_row.get("valid_days_count")) or 0
            rf_total_days = safe_int(rf_row.get("total_days_count")) or 0
            rf_source = rf_row.get("source", "unknown")
            for m in ("nov", "dec", "jan", "feb", "mar", "apr"):
                rf_monthly[m] = safe_float(rf_row.get(f"rain_{m}_mm"))

        # Mandi price features & gap
        pr_row = prices_by_district_season.get((district_key, season))
        pr_gap = True
        pr_mean = None
        pr_volatility = None
        pr_market_count = 0
        pr_reporting_days = 0
        pr_source = "missing"
        pr_monthly: dict[str, float | None] = dict.fromkeys(
            ("nov", "dec", "jan", "feb", "mar", "apr")
        )

        if pr_row:
            pr_gap = parse_bool(pr_row.get("data_gap", "True"))
            pr_mean = safe_float(pr_row.get("price_mean"))
            pr_volatility = safe_float(pr_row.get("price_volatility"))
            pr_market_count = safe_int(pr_row.get("market_count")) or 0
            pr_reporting_days = safe_int(pr_row.get("reporting_days_count")) or 0
            pr_source = pr_row.get("source", "unknown")
            for m in ("nov", "dec", "jan", "feb", "mar", "apr"):
                pr_monthly[m] = safe_float(pr_row.get(f"price_{m}"))

        # District yield features & gap
        yd_rec = yield_by_district_season.get((district_key, season))
        yd_gap = yd_rec is None
        yd_kg_per_ha = yd_rec.yield_kg_per_ha if yd_rec else None
        yd_area_ha = yd_rec.area_ha if yd_rec else None
        yd_production_tonnes = yd_rec.production_tonnes if yd_rec else None
        yd_source = yd_rec.source_name if yd_rec else "missing"

        # Gap propagation and completeness notes
        data_gap_any = ndvi_gap or rf_gap or pr_gap or yd_gap
        gap_reasons = []
        if ndvi_gap:
            gap_reasons.append(f"ndvi ({ndvi_valid_obs} passes)")
        if rf_gap:
            gap_reasons.append("rainfall incomplete")
        if pr_gap:
            gap_reasons.append("mandi price incomplete")
        if yd_gap:
            gap_reasons.append("yield missing")

        completeness_note = "complete" if not gap_reasons else f"gap: {'; '.join(gap_reasons)}"

        row_dict: dict[str, object] = {
            # Primary Key
            "plot_code": plot_code,
            "season": season,
            # Plot Metadata
            "district": district,
            "crop": plot_meta.crop if plot_meta else "wheat",
            "lat": plot_meta.lat if plot_meta else None,
            "lon": plot_meta.lon if plot_meta else None,
            "buffer_m": plot_meta.buffer_m if plot_meta else 50,
            "irrigation": plot_meta.irrigation if plot_meta else None,
            "insured": plot_meta.insured if plot_meta else 0,
            # NDVI Features
            "ndvi_mean": ndvi_mean,
            "ndvi_peak": ndvi_peak,
            "ndvi_std": ndvi_std,
            "ndvi_early": ndvi_early,
            "ndvi_valid_obs_count": ndvi_valid_obs,
            "ndvi_source": ndvi_source,
            # Rainfall Features
            "rain_total_mm": rf_total_mm,
            "rain_early_mm": rf_early_mm,
            "rain_nov_mm": rf_monthly["nov"],
            "rain_dec_mm": rf_monthly["dec"],
            "rain_jan_mm": rf_monthly["jan"],
            "rain_feb_mm": rf_monthly["feb"],
            "rain_mar_mm": rf_monthly["mar"],
            "rain_apr_mm": rf_monthly["apr"],
            "rain_deficit_pct": rf_deficit_pct,
            "rain_valid_days_count": rf_valid_days,
            "rain_total_days_count": rf_total_days,
            "rain_source": rf_source,
            # Mandi Price Features
            "price_mean": pr_mean,
            "price_volatility": pr_volatility,
            "price_nov": pr_monthly["nov"],
            "price_dec": pr_monthly["dec"],
            "price_jan": pr_monthly["jan"],
            "price_feb": pr_monthly["feb"],
            "price_mar": pr_monthly["mar"],
            "price_apr": pr_monthly["apr"],
            "price_market_count": pr_market_count,
            "price_reporting_days_count": pr_reporting_days,
            "price_source": pr_source,
            # District Yield Features
            "yield_kg_per_ha": yd_kg_per_ha,
            "yield_area_ha": yd_area_ha,
            "yield_production_tonnes": yd_production_tonnes,
            "yield_source": yd_source,
            # Data Gap Flags & Audit
            "data_gap_ndvi": ndvi_gap,
            "data_gap_rainfall": rf_gap,
            "data_gap_price": pr_gap,
            "data_gap_yield": yd_gap,
            "data_gap_any": data_gap_any,
            "completeness_note": completeness_note,
        }
        joined_rows.append(row_dict)

    # 7. Verification of row preservation and primary key
    if len(joined_rows) != len(ndvi_rows):
        raise RuntimeError(
            f"Join integrity violation: input NDVI rows ({len(ndvi_rows)}) != "
            f"output dataset rows ({len(joined_rows)})."
        )

    # 8. Write to output CSV
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(joined_rows[0].keys())

    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(joined_rows)

    logger.info("Successfully wrote joined dataset to %s (%d rows)", output_path, len(joined_rows))

    # 9. Compute and print summary
    total_rows = len(joined_rows)
    total_plots = len({r["plot_code"] for r in joined_rows})
    total_seasons = len({r["season"] for r in joined_rows})
    complete_count = sum(1 for r in joined_rows if not r["data_gap_any"])
    gap_count = sum(1 for r in joined_rows if r["data_gap_any"])

    peaks = [float(r["ndvi_peak"]) for r in joined_rows if r["ndvi_peak"] is not None]  # type: ignore[arg-type]
    rains = [float(r["rain_total_mm"]) for r in joined_rows if r["rain_total_mm"] is not None]  # type: ignore[arg-type]
    prices = [float(r["price_mean"]) for r in joined_rows if r["price_mean"] is not None]  # type: ignore[arg-type]
    yields = [float(r["yield_kg_per_ha"]) for r in joined_rows if r["yield_kg_per_ha"] is not None]  # type: ignore[arg-type]

    logger.info("================ DATASET JOIN SUMMARY ================")
    logger.info(
        "Total Rows: %d | Unique Plots: %d | Unique Seasons: %d",
        total_rows,
        total_plots,
        total_seasons,
    )
    logger.info(
        "Complete Rows: %d (%0.1f%%) | Rows with Any Data Gap: %d (%0.1f%%)",
        complete_count,
        (complete_count / total_rows) * 100,
        gap_count,
        (gap_count / total_rows) * 100,
    )
    if peaks:
        logger.info(
            "NDVI Peak:       min=%0.4f, mean=%0.4f, max=%0.4f",
            min(peaks),
            sum(peaks) / len(peaks),
            max(peaks),
        )
    if rains:
        logger.info(
            "Rainfall Total:  min=%0.1f mm, mean=%0.1f mm, max=%0.1f mm",
            min(rains),
            sum(rains) / len(rains),
            max(rains),
        )
    if prices:
        logger.info(
            "Mandi Price:     min=₹%0.2f, mean=₹%0.2f, max=₹%0.2f/qtl",
            min(prices),
            sum(prices) / len(prices),
            max(prices),
        )
    if yields:
        logger.info(
            "District Yield:  min=%0.1f, mean=%0.1f, max=%0.1f kg/ha",
            min(yields),
            sum(yields) / len(yields),
            max(yields),
        )
    logger.info("======================================================")

    return 0


def main() -> int:
    """CLI wrapper for dataset assembly."""
    parser = argparse.ArgumentParser(description="Assemble multi-source seasonal dataset.")
    parser.add_argument(
        "--ndvi",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "ndvi_plot_season.csv",
        help="Path to seasonal NDVI CSV",
    )
    parser.add_argument(
        "--plots",
        type=Path,
        default=PROJECT_ROOT / "data" / "synthetic" / "sample_plots.csv",
        help="Path to sample plots CSV",
    )
    parser.add_argument(
        "--rainfall",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "rainfall_plot_season.csv",
        help="Path to seasonal rainfall CSV",
    )
    parser.add_argument(
        "--prices",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "mandi_prices_season.csv",
        help="Path to seasonal mandi prices CSV",
    )
    parser.add_argument(
        "--yield-file",
        type=Path,
        default=PROJECT_ROOT / "data" / "external" / "district_yield_wheat.csv",
        help="Path to district yield CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "season_dataset.csv",
        help="Path to output joined dataset CSV",
    )

    args = parser.parse_args()
    return build_dataset(
        ndvi_path=args.ndvi,
        plots_path=args.plots,
        rainfall_path=args.rainfall,
        prices_path=args.prices,
        yield_path=args.yield_file,
        output_path=args.output,
    )


if __name__ == "__main__":
    sys.exit(main())
