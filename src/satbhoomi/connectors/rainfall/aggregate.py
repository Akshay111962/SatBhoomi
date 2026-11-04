"""Seasonal aggregation and deficit metric calculation for daily precipitation time series."""

from datetime import UTC, datetime

from satbhoomi.connectors.rainfall.base import (
    ANAND_RABI_NORMAL_RAINFALL_MM,
    MIN_VALID_DAYS_RATIO,
    DailyRainfallRecord,
    RainfallAggregate,
)
from satbhoomi.connectors.satellite.base import SeasonWindow

RABI_MONTH_NAMES = ("nov", "dec", "jan", "feb", "mar", "apr")
MONTH_NUMBER_MAP = {
    11: "nov",
    12: "dec",
    1: "jan",
    2: "feb",
    3: "mar",
    4: "apr",
}


def aggregate_season_rainfall(
    plot_code: str,
    window: SeasonWindow,
    records: list[DailyRainfallRecord],
    source: str,
    baseline_mm: float = ANAND_RABI_NORMAL_RAINFALL_MM,
    min_valid_ratio: float = MIN_VALID_DAYS_RATIO,
    fetched_at: str | None = None,
) -> RainfallAggregate:
    """Aggregate daily precipitation observations into seasonal risk metrics.

    Rules:
    1. Validates every record against the seasonal temporal window.
    2. Rejects precipitation values that are negative.
    3. Missing days stay missing and flagged (never imputed with zero).
    4. Computes rain_total_mm, rain_early_mm (first 6 weeks = 42 days),
       rain_deficit_pct against the documented long-term baseline,
       and monthly breakdown.
    5. Flags data_gap=True if any days are missing or valid ratio < min_valid_ratio.

    Args:
        plot_code: Unique plot identifier.
        window: Cropping season window.
        records: Collection of daily precipitation records returned by provider.
        source: Provider identifier ('nasa_power', 'fixture', 'chirps').
        baseline_mm: Long-term normal seasonal rainfall for the region in mm.
        min_valid_ratio: Fraction of window days required to be valid.
        fetched_at: ISO timestamp of data retrieval. If None, current UTC time is used.

    Returns:
        RainfallAggregate object with seasonal totals and monthly breakdown.
    """
    total_days = (window.end_date - window.start_date).days + 1

    # 1. Validate dates and physical range
    seen_dates: set = set()
    for rec in records:
        if not window.contains(rec.date):
            raise ValueError(
                f"Rainfall record date {rec.date} falls outside season window "
                f"{window.season_name} ({window.start_date} to {window.end_date})."
            )
        if rec.precipitation_mm is not None and rec.precipitation_mm < 0:
            raise ValueError(
                f"Rainfall precipitation {rec.precipitation_mm} mm cannot be negative."
            )
        if rec.date in seen_dates:
            raise ValueError(f"Duplicate rainfall record found for date {rec.date}.")
        seen_dates.add(rec.date)

    # 2. Filter valid observations
    valid_records = [rec for rec in records if rec.is_valid and rec.precipitation_mm is not None]
    valid_count = len(valid_records)

    # 3. Check for gaps: any missing days or ratio below required threshold
    is_data_gap = (valid_count < total_days) or ((valid_count / total_days) < min_valid_ratio)

    # 4. Monthly aggregation dictionary initialization
    monthly_rain: dict[str, float | None] = dict.fromkeys(RABI_MONTH_NAMES)
    monthly_valid_counts: dict[str, int] = dict.fromkeys(RABI_MONTH_NAMES, 0)
    monthly_sums: dict[str, float] = dict.fromkeys(RABI_MONTH_NAMES, 0.0)

    for rec in valid_records:
        month_key = MONTH_NUMBER_MAP.get(rec.date.month)
        if month_key and rec.precipitation_mm is not None:
            monthly_sums[month_key] += rec.precipitation_mm
            monthly_valid_counts[month_key] += 1

    for m in RABI_MONTH_NAMES:
        if monthly_valid_counts[m] > 0:
            monthly_rain[m] = round(monthly_sums[m], 2)
        else:
            monthly_rain[m] = None

    # 5. Compute seasonal totals
    if valid_count == 0:
        rain_total_mm = None
        rain_early_mm = None
        rain_deficit_pct = None
    else:
        rain_total_mm = round(sum(r.precipitation_mm for r in valid_records), 2)  # type: ignore[arg-type]

        # Early window: first 6 weeks (42 days) of the cropping season
        early_records = [r for r in valid_records if r.date <= window.early_window_end]
        if early_records:
            rain_early_mm = round(
                sum(r.precipitation_mm for r in early_records),  # type: ignore[arg-type]
                2,
            )
        else:
            rain_early_mm = 0.0

        # Deficit percentage relative to baseline:
        # deficit_pct = ((total - baseline) / baseline) * 100
        # Negative indicates deficit (e.g. -35.2%), positive indicates surplus (+12.4%)
        if baseline_mm > 0:
            rain_deficit_pct = round(((rain_total_mm - baseline_mm) / baseline_mm) * 100.0, 2)
        else:
            rain_deficit_pct = None

    timestamp = fetched_at or datetime.now(UTC).isoformat()

    return RainfallAggregate(
        plot_code=plot_code,
        season=window.season_name,
        rain_total_mm=rain_total_mm,
        rain_early_mm=rain_early_mm,
        rain_deficit_pct=rain_deficit_pct,
        valid_days_count=valid_count,
        total_days_count=total_days,
        data_gap=is_data_gap,
        monthly_rain_mm=monthly_rain,
        source=source,
        fetched_at=timestamp,
    )
