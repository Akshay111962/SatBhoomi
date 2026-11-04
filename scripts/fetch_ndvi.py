"""CLI script to fetch multi-season satellite NDVI time-series and compute seasonal aggregates."""

import argparse
import csv
import json
import logging
import sys
from datetime import date
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    sys.path.insert(0, str(PROJECT_ROOT))

from satbhoomi.connectors.satellite import (  # noqa: E402
    FixtureNdviProvider,
    GoogleEarthEngineProvider,
    PlanetaryComputerProvider,
    PlotLocation,
    RawObservation,
    SeasonAggregate,
    SeasonWindow,
    aggregate_season_observations,
    get_default_rabi_seasons,
    load_sample_plots,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("fetch_ndvi")


def serialize_observation(obs: RawObservation) -> dict[str, object]:
    """Serialize RawObservation to JSON-compatible dict."""
    return {
        "date": obs.date.isoformat(),
        "ndvi": obs.ndvi,
        "is_valid": obs.is_valid,
        "cloud_prob": obs.cloud_prob,
        "scl_class": obs.scl_class,
        "scene_id": obs.scene_id,
    }


def deserialize_observation(data: dict[str, object]) -> RawObservation:
    """Deserialize dict to RawObservation."""
    return RawObservation(
        date=date.fromisoformat(str(data["date"])),
        ndvi=float(data["ndvi"]),  # type: ignore[arg-type]
        is_valid=bool(data["is_valid"]),
        cloud_prob=float(data["cloud_prob"]) if data.get("cloud_prob") is not None else None,  # type: ignore[arg-type]
        scl_class=int(data["scl_class"]) if data.get("scl_class") is not None else None,  # type: ignore[arg-type]
        scene_id=str(data["scene_id"]) if data.get("scene_id") is not None else None,
    )


def fetch_with_cache(
    provider: object,
    plot: PlotLocation,
    window: SeasonWindow,
    cache_dir: Path,
) -> list[RawObservation]:
    """Fetch observations, reading from local JSON cache if present."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{plot.plot_code}_{window.season_name}.json"

    if cache_file.is_file():
        logger.debug("Cache hit for %s %s", plot.plot_code, window.season_name)
        with cache_file.open("r", encoding="utf-8") as f:
            records = json.load(f)
            return [deserialize_observation(r) for r in records]

    # Fetch from provider
    fetch_method = provider.fetch_observations
    observations: list[RawObservation] = fetch_method(plot, window)

    # Cache response
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump([serialize_observation(o) for o in observations], f, indent=2)

    return observations


def main() -> int:
    """Main CLI entry point for NDVI fetch."""
    parser = argparse.ArgumentParser(
        description="Fetch multi-season NDVI observations for farm plots."
    )
    parser.add_argument(
        "--provider",
        choices=["fixture", "gee", "planetary"],
        default="fixture",
        help="Satellite provider source (default: fixture)",
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
        default=PROJECT_ROOT / "data" / "processed" / "ndvi_plot_season.csv",
        help="Path to processed output CSV (default: data/processed/ndvi_plot_season.csv)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "raw" / "satellite",
        help="Directory to cache raw satellite responses (default: data/raw/satellite)",
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
        logger.info("DRY RUN: Validation passed. %d plot-seasons would be processed.", total_runs)
        for p in plots:
            logger.info(
                "  Plot %s (lat=%0.4f, lon=%0.4f, buffer=%dm, crop=%s, district=%s)",
                p.plot_code,
                p.lat,
                p.lon,
                p.buffer_m,
                p.crop,
                p.district,
            )
        return 0

    # 4. Instantiate chosen provider
    if args.provider == "fixture":
        provider = FixtureNdviProvider()
    elif args.provider == "planetary":
        provider = PlanetaryComputerProvider()
    elif args.provider == "gee":
        provider = GoogleEarthEngineProvider()
    else:
        logger.error("Unknown provider: %s", args.provider)
        return 1

    logger.info("Using provider: %s", provider.source_name)

    # 5. Process all plots across all seasons
    aggregates: list[SeasonAggregate] = []
    total = len(plots) * len(seasons)
    processed = 0

    for plot in plots:
        for window in seasons:
            processed += 1
            logger.info(
                "[%d/%d] Fetching %s for season %s...",
                processed,
                total,
                plot.plot_code,
                window.season_name,
            )
            try:
                obs = fetch_with_cache(provider, plot, window, args.cache_dir)
                agg = aggregate_season_observations(
                    plot_code=plot.plot_code,
                    window=window,
                    observations=obs,
                    source=provider.source_name,
                )
                aggregates.append(agg)
            except Exception as exc:
                logger.error(
                    "Error processing plot %s season %s: %s",
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
        "ndvi_mean",
        "ndvi_peak",
        "ndvi_std",
        "ndvi_early",
        "valid_obs_count",
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
                    "ndvi_mean": agg.ndvi_mean,
                    "ndvi_peak": agg.ndvi_peak,
                    "ndvi_std": agg.ndvi_std,
                    "ndvi_early": agg.ndvi_early,
                    "valid_obs_count": agg.valid_obs_count,
                    "data_gap": agg.data_gap,
                    "source": agg.source,
                    "fetched_at": agg.fetched_at,
                }
            )

    # Summary
    peaks = [a.ndvi_peak for a in aggregates if a.ndvi_peak is not None]
    min_peak = min(peaks) if peaks else 0.0
    mean_peak = sum(peaks) / len(peaks) if peaks else 0.0
    max_peak = max(peaks) if peaks else 0.0
    gaps = sum(1 for a in aggregates if a.data_gap)

    logger.info("Successfully wrote %d seasonal records to %s", len(aggregates), args.output)
    logger.info(
        "Summary: Records=%d, Gaps=%d, Peak NDVI (min=%0.4f, mean=%0.4f, max=%0.4f)",
        len(aggregates),
        gaps,
        min_peak,
        mean_peak,
        max_peak,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
