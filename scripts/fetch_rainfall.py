"""CLI script to fetch multi-season daily rainfall and compute seasonal precipitation aggregates."""

import argparse
import csv
import json
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    sys.path.insert(0, str(PROJECT_ROOT))

from satbhoomi.connectors.rainfall import (  # noqa: E402
    DailyRainfallRecord,
    FixtureRainfallProvider,
    NasaPowerRainfallProvider,
    RainfallAggregate,
    aggregate_season_rainfall,
)
from satbhoomi.connectors.satellite import (  # noqa: E402
    PlotLocation,
    SeasonWindow,
    get_default_rabi_seasons,
    load_sample_plots,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_rainfall")


def serialize_rainfall_record(rec: DailyRainfallRecord) -> dict[str, object]:
    """Serialize DailyRainfallRecord to JSON-compatible dict."""
    return {
        "date": rec.date.isoformat(),
        "precipitation_mm": rec.precipitation_mm,
        "is_valid": rec.is_valid,
        "source": rec.source,
        "metadata": rec.metadata,
    }


def deserialize_rainfall_record(data: dict[str, object]) -> DailyRainfallRecord:
    """Deserialize dict to DailyRainfallRecord."""
    from datetime import date

    precip = data.get("precipitation_mm")
    return DailyRainfallRecord(
        date=date.fromisoformat(str(data["date"])),
        precipitation_mm=float(precip) if precip is not None else None,  # type: ignore[arg-type]
        is_valid=bool(data["is_valid"]),
        source=str(data.get("source", "cached")),
        metadata=dict(data.get("metadata", {})),  # type: ignore[arg-type]
    )


def fetch_rainfall_with_cache(
    provider: object,
    plot: PlotLocation,
    window: SeasonWindow,
    cache_dir: Path,
) -> list[DailyRainfallRecord]:
    """Fetch daily rainfall records, reading from local JSON cache if present."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"rainfall_{plot.plot_code}_{window.season_name}.json"

    if cache_file.is_file():
        logger.debug("Cache hit for %s %s", plot.plot_code, window.season_name)
        with cache_file.open("r", encoding="utf-8") as f:
            records = json.load(f)
            return [deserialize_rainfall_record(r) for r in records]

    # Fetch from provider
    fetch_method = provider.fetch_daily_rainfall
    daily_records: list[DailyRainfallRecord] = fetch_method(plot.lat, plot.lon, window)

    # Cache response
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump([serialize_rainfall_record(r) for r in daily_records], f, indent=2)

    return daily_records


def main() -> int:
    """Main CLI entry point for rainfall fetch."""
    parser = argparse.ArgumentParser(
        description="Fetch multi-season daily rainfall and compute seasonal aggregates."
    )
    parser.add_argument(
        "--provider",
        choices=["fixture", "nasa_power"],
        default="fixture",
        help="Rainfall provider source (default: fixture)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate sample plots and print execution plan without fetching",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "data" / "synthetic" / "sample_plots.csv",
        help="Path to sample plots CSV (default: data/synthetic/sample_plots.csv)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "rainfall_plot_season.csv",
        help="Path to processed output CSV (default: data/processed/rainfall_plot_season.csv)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "rainfall",
        help="Directory to cache raw rainfall responses (default: data/raw/rainfall)",
    )
    parser.add_argument(
        "--seasons",
        type=int,
        default=5,
        help="Number of completed rabi seasons to fetch (default: 5)",
    )

    args = parser.parse_args()

    # 1. Load and validate input plots
    try:
        plots = load_sample_plots(args.input)
        logger.info("Loaded and validated %d plots from %s", len(plots), args.input)
    except Exception as exc:
        logger.error("Failed to load sample plots: %s", exc)
        return 1

    # 2. Determine season windows
    seasons = get_default_rabi_seasons(count=args.seasons)
    logger.info("Targeting %d Rabi seasons: %s", len(seasons), [s.season_name for s in seasons])

    # 3. Handle dry run
    if args.dry_run:
        total_runs = len(plots) * len(seasons)
        logger.info(
            "DRY RUN: Validation passed. %d plot-seasons would be processed for rainfall.",
            total_runs,
        )
        for p in plots:
            logger.info(
                "  Plot %s (lat=%0.4f, lon=%0.4f, district=%s)",
                p.plot_code,
                p.lat,
                p.lon,
                p.district,
            )
        return 0

    # 4. Instantiate provider
    if args.provider == "fixture":
        provider = FixtureRainfallProvider()
    elif args.provider == "nasa_power":
        provider = NasaPowerRainfallProvider(cache_dir=args.cache_dir)
    else:
        logger.error("Unknown provider: %s", args.provider)
        return 1

    logger.info("Using rainfall provider: %s", provider.source_name)

    # 5. Process all plots across all seasons
    aggregates: list[RainfallAggregate] = []
    total = len(plots) * len(seasons)
    processed = 0

    for plot in plots:
        for window in seasons:
            processed += 1
            logger.info(
                "[%d/%d] Fetching rainfall for %s season %s...",
                processed,
                total,
                plot.plot_code,
                window.season_name,
            )
            try:
                records = fetch_rainfall_with_cache(provider, plot, window, args.cache_dir)
                agg = aggregate_season_rainfall(
                    plot_code=plot.plot_code,
                    window=window,
                    records=records,
                    source=provider.source_name,
                )
                aggregates.append(agg)
            except Exception as exc:
                logger.error(
                    "Error processing rainfall for plot %s season %s: %s",
                    plot.plot_code,
                    window.season_name,
                    exc,
                )
                return 1

    # 6. Write output CSV
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
    ]

    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for agg in aggregates:
            writer.writerow(
                {
                    "plot_code": agg.plot_code,
                    "season": agg.season,
                    "rain_total_mm": agg.rain_total_mm,
                    "rain_early_mm": agg.rain_early_mm,
                    "rain_nov_mm": agg.monthly_rain_mm.get("nov"),
                    "rain_dec_mm": agg.monthly_rain_mm.get("dec"),
                    "rain_jan_mm": agg.monthly_rain_mm.get("jan"),
                    "rain_feb_mm": agg.monthly_rain_mm.get("feb"),
                    "rain_mar_mm": agg.monthly_rain_mm.get("mar"),
                    "rain_apr_mm": agg.monthly_rain_mm.get("apr"),
                    "rain_deficit_pct": agg.rain_deficit_pct,
                    "valid_days_count": agg.valid_days_count,
                    "total_days_count": agg.total_days_count,
                    "data_gap": agg.data_gap,
                    "source": agg.source,
                    "fetched_at": agg.fetched_at,
                }
            )

    totals = [a.rain_total_mm for a in aggregates if a.rain_total_mm is not None]
    min_rain = min(totals) if totals else 0.0
    mean_rain = sum(totals) / len(totals) if totals else 0.0
    max_rain = max(totals) if totals else 0.0
    gaps = sum(1 for a in aggregates if a.data_gap)

    logger.info("Successfully wrote %d rainfall records to %s", len(aggregates), args.output)
    logger.info(
        "Summary: Records=%d, Gaps=%d, Seasonal Rain (min=%0.1f mm, mean=%0.1f mm, max=%0.1f mm)",
        len(aggregates),
        gaps,
        min_rain,
        mean_rain,
        max_rain,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
