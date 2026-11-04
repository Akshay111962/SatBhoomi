"""Abstract base classes and data transfer models for mandi price retrieval."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from satbhoomi.connectors.satellite.base import SeasonWindow

# Minimum distinct market reporting days required across a 5.5-month season
# before flagging a mandi price data gap.
MIN_MANDI_REPORTING_DAYS_THRESHOLD: int = 10


@dataclass(frozen=True)
class DailyMandiRecord:
    """A single market-day commodity price observation."""

    date: date
    market: str
    state: str
    district: str
    commodity: str
    modal_price: float
    min_price: float | None = None
    max_price: float | None = None
    arrivals_tonnes: float | None = None
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MandiSeasonAggregate:
    """Aggregated seasonal mandi price statistics and monthly time series.

    CRITICAL DOMAIN NOTICE (DATA LEAKAGE PREVENTION):
    Wheat harvest prices realized in March/April represent seasonal OUTCOMES,
    not pre-season or in-season inputs available at sowing (November) or during
    early vegetative growth (December-January).
    Downstream tasks (T-04 feature engineering, T-05 credit assessment) MUST NOT
    leak post-sowing mandi prices into early-warning or loan underwriting models.
    The monthly breakdown enables upstream feature filtering by date.
    """

    district: str
    crop: str
    season: str
    price_mean: float | None
    price_volatility: float | None
    monthly_prices: dict[str, float | None]
    market_count: int
    reporting_days_count: int
    data_gap: bool
    source: str
    fetched_at: str


class PriceProvider(ABC):
    """Abstract interface for agricultural commodity mandi price providers."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for the price data source (e.g. 'ceda', 'manual_csv', 'fixture')."""
        ...

    @abstractmethod
    def fetch_prices(
        self,
        crop: str,
        state: str,
        district: str,
        window: SeasonWindow,
    ) -> list[DailyMandiRecord]:
        """Fetch daily mandi price records for a crop, district, and season window.

        Args:
            crop: Standard crop name (e.g. 'wheat').
            state: State name (e.g. 'Gujarat').
            district: District name (e.g. 'Anand').
            window: Temporal season start and end dates.

        Returns:
            List of DailyMandiRecord objects ordered chronologically.
        """
        ...
