"""CLI script to fetch multi-season mandi commodity prices and compute seasonal price aggregates."""

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

from satbhoomi.connectors.mandi import (  # noqa: E402
    CedaPriceProvider,
    FixturePriceProvider,
    MandiSeasonAggregate,
    ManualCsvPriceProvider,
    PriceProvider,
    aggregate_season_mandi_prices,
)
from satbhoomi.connectors.satellite import get_default_rabi_seasons  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_prices")


def main() -> int:
    """Main CLI entry point for mandi prices fetch."""
    parser = argparse.ArgumentParser(
        description="Fetch multi-season mandi prices and compute seasonal price metrics."
    )
    parser.add_argument(
        "--provider",
        choices=["manual_csv", "fixture", "ceda"],
        default="manual_csv",
        help="Price provider source (default: manual_csv)",
    )
    parser.add_argument(
        "--crop",
        default="wheat",
        help="Target agricultural commodity (default: wheat)",
    )
    parser.add_argument(
        "--district",
        default="Anand",
        help="Target district (default: Anand)",
    )
    parser.add_argument(
        "--state",
        default="Gujarat",
        help="Target state (default: Gujarat)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate parameters and print execution plan without fetching",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "mandi_prices_season.csv",
        help="Path to processed output CSV (default: data/processed/mandi_prices_season.csv)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "mandi",
        help="Directory to cache raw mandi responses (default: data/raw/mandi)",
    )
    parser.add_argument(
        "--seasons",
        type=int,
        default=5,
        help="Number of completed rabi seasons to fetch (default: 5)",
    )

    args = parser.parse_args()

    # 1. Determine season windows
    seasons = get_default_rabi_seasons(count=args.seasons)
    logger.info("Targeting %d Rabi seasons: %s", len(seasons), [s.season_name for s in seasons])

    # 2. Handle dry run
    if args.dry_run:
        logger.info(
            "DRY RUN: Validation passed. %d seasons would be processed for %s in %s, %s.",
            len(seasons),
            args.crop,
            args.district,
            args.state,
        )
        return 0

    # 3. Instantiate provider
    provider: PriceProvider
    if args.provider == "manual_csv":
        provider = ManualCsvPriceProvider()
    elif args.provider == "fixture":
        provider = FixturePriceProvider()
    elif args.provider == "ceda":
        provider = CedaPriceProvider(cache_dir=args.cache_dir)
    else:
        logger.error("Unknown provider: %s", args.provider)
        return 1

    logger.info("Using mandi price provider: %s", provider.source_name)

    # 4. Fetch and aggregate prices per season
    aggregates: list[MandiSeasonAggregate] = []
    for window in seasons:
        logger.info(
            "Fetching mandi prices for %s in %s for season %s...",
            args.crop,
            args.district,
            window.season_name,
        )
        try:
            records = provider.fetch_prices(
                crop=args.crop,
                state=args.state,
                district=args.district,
                window=window,
            )
            agg = aggregate_season_mandi_prices(
                district=args.district,
                crop=args.crop,
                window=window,
                records=records,
                source=provider.source_name,
            )
            aggregates.append(agg)
        except Exception as exc:
            logger.error(
                "Error processing prices for season %s: %s",
                window.season_name,
                exc,
            )
            return 1

    # 5. Write output CSV
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
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
    ]

    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for agg in aggregates:
            writer.writerow(
                {
                    "district": agg.district,
                    "crop": agg.crop,
                    "season": agg.season,
                    "price_mean": agg.price_mean,
                    "price_volatility": agg.price_volatility,
                    "price_nov": agg.monthly_prices.get("nov"),
                    "price_dec": agg.monthly_prices.get("dec"),
                    "price_jan": agg.monthly_prices.get("jan"),
                    "price_feb": agg.monthly_prices.get("feb"),
                    "price_mar": agg.monthly_prices.get("mar"),
                    "price_apr": agg.monthly_prices.get("apr"),
                    "market_count": agg.market_count,
                    "reporting_days_count": agg.reporting_days_count,
                    "data_gap": agg.data_gap,
                    "source": agg.source,
                    "fetched_at": agg.fetched_at,
                }
            )

    means = [a.price_mean for a in aggregates if a.price_mean is not None]
    min_price = min(means) if means else 0.0
    avg_price = sum(means) / len(means) if means else 0.0
    max_price = max(means) if means else 0.0
    gaps = sum(1 for a in aggregates if a.data_gap)

    logger.info("Successfully wrote %d mandi price records to %s", len(aggregates), args.output)
    logger.info(
        "Summary: Seasons=%d, Gaps=%d, Mean Price (min=₹%0.2f, avg=₹%0.2f, max=₹%0.2f/qtl)",
        len(aggregates),
        gaps,
        min_price,
        avg_price,
        max_price,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
