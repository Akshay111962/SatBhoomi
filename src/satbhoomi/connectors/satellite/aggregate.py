"""Aggregation and statistical feature derivation for seasonal NDVI time-series."""

from datetime import UTC, datetime
from statistics import mean, stdev

from satbhoomi.connectors.satellite.base import RawObservation, SeasonAggregate, SeasonWindow

# Minimum clear, valid Sentinel-2 observations required across a 5.5-month season
# to consider the season statistically reliable without flagging a data gap banner.
MIN_VALID_OBSERVATIONS_THRESHOLD: int = 4

# Strict theoretical limits of Normalized Difference Vegetation Index
NDVI_MIN_BOUND: float = -1.0
NDVI_MAX_BOUND: float = 1.0


def validate_observation(obs: RawObservation, window: SeasonWindow) -> None:
    """Validate provider output as untrusted input.

    Raises:
        ValueError: If observation date is outside the season window or NDVI is out of bounds.
    """
    if not window.contains(obs.date):
        raise ValueError(
            f"Observation date {obs.date} falls outside season window {window.season_name} "
            f"({window.start_date} to {window.end_date})."
        )
    if not (NDVI_MIN_BOUND <= obs.ndvi <= NDVI_MAX_BOUND):
        raise ValueError(
            f"Observation NDVI {obs.ndvi} violates valid bounds "
            f"[{NDVI_MIN_BOUND}, {NDVI_MAX_BOUND}]."
        )


def aggregate_season_observations(
    plot_code: str,
    window: SeasonWindow,
    observations: list[RawObservation],
    source: str,
    min_valid_obs: int = MIN_VALID_OBSERVATIONS_THRESHOLD,
    fetched_at: str | None = None,
) -> SeasonAggregate:
    """Aggregate raw satellite observations into seasonal risk features.

    Rules:
    1. Validates every observation against temporal and physical bounds.
    2. Rejects invalid or out-of-window observations.
    3. Excludes cloudy/invalid observations (`is_valid=False`) from statistics.
    4. NEVER invents, imputes, or silently interpolates missing values.
    5. Flags `data_gap=True` whenever valid observation count is below `min_valid_obs`.

    Args:
        plot_code: Unique plot identifier.
        window: Cropping season window.
        observations: Collection of raw observations returned by the provider.
        source: Provider identifier ('gee', 'planetary', 'fixture').
        min_valid_obs: Minimum valid observations required before flagging data gap.
        fetched_at: ISO timestamp of data retrieval. If None, current UTC time is used.

    Returns:
        SeasonAggregate object with computed statistics and gap flag.
    """
    # 1. Validate all incoming observations (treat provider data as untrusted)
    for obs in observations:
        validate_observation(obs, window)

    # 2. Filter to valid, cloud-free observations
    valid_obs = [obs for obs in observations if obs.is_valid]
    valid_count = len(valid_obs)

    # 3. Check data gap threshold
    is_data_gap = valid_count < min_valid_obs

    # 4. Compute statistics on valid observations only; never invent values
    if valid_count == 0:
        ndvi_mean = None
        ndvi_peak = None
        ndvi_std = None
        ndvi_early = None
    else:
        values = [obs.ndvi for obs in valid_obs]
        ndvi_mean = round(float(mean(values)), 4)
        ndvi_peak = round(float(max(values)), 4)
        ndvi_std = round(float(stdev(values)), 4) if len(values) > 1 else 0.0

        # Early season window: first 6 weeks (42 days) of the cropping season
        early_obs = [obs.ndvi for obs in valid_obs if obs.date <= window.early_window_end]
        ndvi_early = round(float(mean(early_obs)), 4) if early_obs else None

    timestamp = fetched_at or datetime.now(UTC).isoformat()

    return SeasonAggregate(
        plot_code=plot_code,
        season=window.season_name,
        ndvi_mean=ndvi_mean,
        ndvi_peak=ndvi_peak,
        ndvi_std=ndvi_std,
        ndvi_early=ndvi_early,
        valid_obs_count=valid_count,
        data_gap=is_data_gap,
        source=source,
        fetched_at=timestamp,
    )
