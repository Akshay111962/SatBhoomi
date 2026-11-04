"""Abstract base classes and data transfer models for daily and seasonal rainfall retrieval."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from satbhoomi.connectors.satellite.base import SeasonWindow

# Long-term climatological mean rainfall (mm) for Anand district during the Rabi
# season window (Nov 1 to Apr 15).
# Source: India Meteorological Department (IMD) 30-year district climate normals (1981-2010)
# for Anand/Kheda district. Winter precipitation is dominated by sporadic western disturbances.
ANAND_RABI_NORMAL_RAINFALL_MM: float = 19.5

# Minimum fraction of reporting days required in the season window before
# flagging a data gap (default: at least 90% of days must be validly observed).
MIN_VALID_DAYS_RATIO: float = 0.90


@dataclass(frozen=True)
class DailyRainfallRecord:
    """A single daily precipitation observation at a point location."""

    date: date
    precipitation_mm: float | None
    is_valid: bool
    source: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RainfallAggregate:
    """Aggregated seasonal rainfall profile and monthly breakdown."""

    plot_code: str
    season: str
    rain_total_mm: float | None
    rain_early_mm: float | None
    rain_deficit_pct: float | None
    valid_days_count: int
    total_days_count: int
    data_gap: bool
    monthly_rain_mm: dict[str, float | None]
    source: str
    fetched_at: str


class RainfallProvider(ABC):
    """Abstract interface for point-location daily rainfall providers."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for the data source (e.g. 'nasa_power', 'fixture', 'chirps')."""
        ...

    @abstractmethod
    def fetch_daily_rainfall(
        self,
        lat: float,
        lon: float,
        window: SeasonWindow,
    ) -> list[DailyRainfallRecord]:
        """Fetch daily precipitation records for a coordinate across a season window.

        Args:
            lat: Latitude of point centroid (decimal degrees).
            lon: Longitude of point centroid (decimal degrees).
            window: Temporal season start and end dates.

        Returns:
            List of DailyRainfallRecord objects ordered chronologically.
        """
        ...
