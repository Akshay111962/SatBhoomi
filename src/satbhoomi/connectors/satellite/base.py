"""Abstract base classes and data transfer models for satellite NDVI data retrieval."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SeasonWindow:
    """Cropping season temporal window.

    Season naming follows the uniform standard "YYYY-YY" (e.g. "2021-22").
    """

    season_name: str
    start_date: date
    end_date: date

    def contains(self, obs_date: date) -> bool:
        """Return True if obs_date falls within the season boundaries inclusive."""
        return self.start_date <= obs_date <= self.end_date

    @property
    def early_window_end(self) -> date:
        """First 6 weeks (42 days) of the cropping season from start_date."""
        from datetime import timedelta

        return self.start_date + timedelta(days=42)


@dataclass(frozen=True)
class PlotLocation:
    """Spatial representation of a sample plot centroid with buffer."""

    plot_code: str
    lat: float
    lon: float
    buffer_m: float = 50.0
    crop: str = "wheat"
    irrigation: str | None = None
    insured: int = 0
    district: str = "Anand"


@dataclass(frozen=True)
class RawObservation:
    """A single satellite pass observation over the plot."""

    date: date
    ndvi: float
    is_valid: bool
    cloud_prob: float | None = None
    scl_class: int | None = None
    scene_id: str | None = None


@dataclass(frozen=True)
class SeasonAggregate:
    """Aggregated seasonal NDVI profile for credit and in-season risk assessment."""

    plot_code: str
    season: str
    ndvi_mean: float | None
    ndvi_peak: float | None
    ndvi_std: float | None
    ndvi_early: float | None
    valid_obs_count: int
    data_gap: bool
    source: str
    fetched_at: str


class NdviProvider(ABC):
    """Abstract interface for satellite vegetation data providers."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for the data source (e.g., 'gee', 'planetary', 'fixture')."""
        ...

    @abstractmethod
    def fetch_observations(
        self,
        plot: PlotLocation,
        window: SeasonWindow,
    ) -> list[RawObservation]:
        """Fetch raw satellite NDVI observations for a plot within the season window.

        Args:
            plot: The plot location and buffer specifications.
            window: Temporal season start and end dates.

        Returns:
            List of raw observations including valid and clouded passes.
        """
        ...
