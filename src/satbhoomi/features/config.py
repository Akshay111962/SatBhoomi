"""Feature engineering and proxy label configuration (T-04).

Central definition of in-season cut-off dates, proxy label thresholds,
approved feature sets, and look-ahead leakage quarantine lists.
"""

from dataclasses import dataclass
from datetime import date
from typing import Final

# Chronological order of supported Rabi seasons
RABI_SEASONS_ORDER: Final[tuple[str, ...]] = (
    "2020-21",
    "2021-22",
    "2022-23",
    "2023-24",
    "2024-25",
)

# In-season cutoff: January 31 (month=1, day=31)
DEFAULT_CUTOFF_MONTH: Final[int] = 1
DEFAULT_CUTOFF_DAY: Final[int] = 31

# Proxy label parameters (Option 1: Expanding prior baseline)
DEFAULT_LABEL_DROP_THRESHOLD_PCT: Final[float] = 15.0  # 15% drop below historical baseline
DEFAULT_MIN_PRIOR_SEASONS: Final[int] = 1  # Minimum 1 completed prior season for baseline

# Baseline normal rainfall for Anand pre-cutoff window (Nov 1 to Jan 31):
# Derived from IMD Anand 30-year normals: Nov (6.5 mm) + Dec (3.0 mm) + Jan (1.0 mm) = 10.5 mm
ANAND_PRE_CUTOFF_NORMAL_RAIN_MM: Final[float] = 10.5

# ---------------------------------------------------------------------------
# Column Groupings: Metadata, Features, Label, and Excluded
# ---------------------------------------------------------------------------

METADATA_COLUMNS: Final[list[str]] = [
    "plot_code",
    "season",
    "district",
    "crop",
    "lat",
    "lon",
]

FEATURE_COLUMNS: Final[list[str]] = [
    # Satellite vegetative features (strictly <= Jan 31)
    "ndvi_early",
    "ndvi_pre_cutoff_mean",
    "ndvi_pre_cutoff_std",
    "ndvi_trend_pre_cutoff",
    # Rainfall features (Nov, Dec, Jan <= Jan 31)
    "rain_pre_cutoff_total_mm",
    "rain_pre_cutoff_deficit_pct",
    # Mandi price volatility (Nov, Dec, Jan <= Jan 31)
    "mandi_pre_cutoff_volatility",
    # Historical track record (strictly earlier completed seasons)
    "past_stressed_seasons_count",
    "prev_season_ndvi_peak",
    # Assigned plot attributes (illustrative experimental properties)
    "area_acre",
    "irrigation",
    "insured",
]

LABEL_COLUMNS: Final[list[str]] = [
    "stressed",  # Binary proxy label: 1 if stressed, 0 if healthy, None if unavailable
    "label_unavailable",  # Boolean flag: True if insufficient prior history, False otherwise
    "peak_drop_pct",  # Outcome drop percentage below prior baseline
    "historical_baseline_ndvi",  # Plot-specific prior historical baseline NDVI
]

# Columns strictly excluded from feature engineering to prevent target / temporal leakage
EXCLUDED_LEAKAGE_COLUMNS: Final[list[str]] = [
    "ndvi_peak",  # Target input for the current season
    "ndvi_mean",  # Full-season aggregate (includes Feb/Mar/Apr post-cutoff)
    "ndvi_std",  # Full-season aggregate
    "rain_feb_mm",  # Post-cutoff rainfall
    "rain_mar_mm",  # Post-cutoff rainfall
    "rain_apr_mm",  # Post-cutoff rainfall
    "rain_total_mm",  # Full-season total rainfall
    "rain_deficit_pct",  # Full-season rainfall deficit
    "price_feb",  # Post-cutoff harvest market prices
    "price_mar",  # Post-cutoff harvest market prices
    "price_apr",  # Post-cutoff harvest market prices
    "price_mean",  # Full-season mean mandi price
    "price_volatility",  # Full-season price volatility
    "yield_kg_per_ha",  # Same-season official crop yield (post-harvest)
    "yield_area_ha",  # District harvest area
    "yield_production_tonnes",  # District harvest production
    "yield_source",
    "data_gap_ndvi",
    "data_gap_rainfall",
    "data_gap_price",
    "data_gap_yield",
    "data_gap_any",
    "completeness_note",
]


@dataclass(frozen=True)
class FeaturePipelineConfig:
    """Configuration container for feature engineering and label computation."""

    cutoff_month: int = DEFAULT_CUTOFF_MONTH
    cutoff_day: int = DEFAULT_CUTOFF_DAY
    drop_threshold_pct: float = DEFAULT_LABEL_DROP_THRESHOLD_PCT
    min_prior_seasons: int = DEFAULT_MIN_PRIOR_SEASONS
    baseline_normal_rain_mm: float = ANAND_PRE_CUTOFF_NORMAL_RAIN_MM

    def get_cutoff_date(self, season: str) -> date:
        """Resolve the calendar cut-off date for a given Rabi season.

        Example: '2023-24' -> 2024-01-31.
        """
        parts = season.split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid season format '{season}'. Expected format 'YYYY-YY'.")
        start_year = int(parts[0])
        # Rabi seasons span two calendar years (Nov in start_year, Jan in start_year + 1)
        cutoff_year = start_year + 1
        return date(cutoff_year, self.cutoff_month, self.cutoff_day)
