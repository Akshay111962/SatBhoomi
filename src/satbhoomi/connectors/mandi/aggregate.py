"""Seasonal aggregation and price volatility calculation for commodity mandi series."""

from datetime import UTC, datetime
from statistics import mean, stdev

from satbhoomi.connectors.mandi.base import (
    MIN_MANDI_REPORTING_DAYS_THRESHOLD,
    DailyMandiRecord,
    MandiSeasonAggregate,
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


def aggregate_season_mandi_prices(
    district: str,
    crop: str,
    window: SeasonWindow,
    records: list[DailyMandiRecord],
    source: str,
    min_reporting_days: int = MIN_MANDI_REPORTING_DAYS_THRESHOLD,
    fetched_at: str | None = None,
) -> MandiSeasonAggregate:
    """Aggregate daily mandi observations into seasonal price metrics and monthly breakdown.

    Rules:
    1. Validates every observation against the seasonal temporal window.
    2. Rejects invalid, zero, or negative prices.
    3. Correctly handles multiple reporting markets on the same calendar day by
       first computing daily district modal averages.
    4. Computes seasonal mean modal price (INR/quintal).
    5. Computes price volatility as the Sample Coefficient of Variation (CV = stdev / mean).
    6. Produces a month-by-month breakdown (Nov, Dec, Jan, Feb, Mar, Apr) to allow
       downstream features to isolate pre-harvest vs harvest periods.
    7. Flags data_gap=True if reporting_days_count < min_reporting_days or market_count == 0.

    Args:
        district: Target district name (e.g. 'Anand').
        crop: Commodity name (e.g. 'wheat').
        window: Cropping season window.
        records: Collection of daily mandi price records.
        source: Provider identifier ('ceda', 'manual_csv', 'fixture').
        min_reporting_days: Minimum days required to consider the series reliable.
        fetched_at: ISO timestamp of data retrieval. If None, current UTC time is used.

    Returns:
        MandiSeasonAggregate object.
    """
    # 1. Validate records
    for rec in records:
        if not window.contains(rec.date):
            raise ValueError(
                f"Mandi record date {rec.date} falls outside season window "
                f"{window.season_name} ({window.start_date} to {window.end_date})."
            )
        if rec.modal_price <= 0:
            raise ValueError(f"Mandi modal price {rec.modal_price} must be strictly positive.")

    valid_records = [rec for rec in records if rec.modal_price > 0]

    # Group records by date to compute daily district averages (handles multiple APMCs)
    daily_prices_by_date: dict = {}
    distinct_markets: set[str] = set()
    for rec in valid_records:
        distinct_markets.add(rec.market)
        if rec.date not in daily_prices_by_date:
            daily_prices_by_date[rec.date] = []
        daily_prices_by_date[rec.date].append(rec.modal_price)

    reporting_days_count = len(daily_prices_by_date)
    market_count = len(distinct_markets)
    is_data_gap = (reporting_days_count < min_reporting_days) or (market_count == 0)

    # Monthly breakdown initialization
    monthly_prices: dict[str, float | None] = dict.fromkeys(RABI_MONTH_NAMES)
    monthly_daily_means: dict[str, list[float]] = {m: [] for m in RABI_MONTH_NAMES}

    if reporting_days_count == 0:
        price_mean = None
        price_volatility = None
    else:
        # Compute daily district mean modal price
        daily_averages: list[float] = []
        for obs_date, price_list in daily_prices_by_date.items():
            day_avg = float(mean(price_list))
            daily_averages.append(day_avg)

            month_key = MONTH_NUMBER_MAP.get(obs_date.month)
            if month_key:
                monthly_daily_means[month_key].append(day_avg)

        price_mean = round(float(mean(daily_averages)), 2)

        # Volatility: Coefficient of Variation (CV = sample stdev / mean)
        if len(daily_averages) > 1 and price_mean > 0:
            sample_sd = float(stdev(daily_averages))
            price_volatility = round(sample_sd / price_mean, 4)
        else:
            price_volatility = 0.0

        for m in RABI_MONTH_NAMES:
            if monthly_daily_means[m]:
                monthly_prices[m] = round(float(mean(monthly_daily_means[m])), 2)

    timestamp = fetched_at or datetime.now(UTC).isoformat()

    return MandiSeasonAggregate(
        district=district,
        crop=crop,
        season=window.season_name,
        price_mean=price_mean,
        price_volatility=price_volatility,
        monthly_prices=monthly_prices,
        market_count=market_count,
        reporting_days_count=reporting_days_count,
        data_gap=is_data_gap,
        source=source,
        fetched_at=timestamp,
    )
