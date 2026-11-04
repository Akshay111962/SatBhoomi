"""District crop yield statistics connector package for SatBhoomi."""

from satbhoomi.connectors.yield_stats.loader import (
    WHEAT_YIELD_MAX_BOUND_KG_HA,
    WHEAT_YIELD_MIN_BOUND_KG_HA,
    DistrictYieldRecord,
    YieldDataValidationError,
    load_district_yield_records,
)

__all__ = [
    "DistrictYieldRecord",
    "WHEAT_YIELD_MAX_BOUND_KG_HA",
    "WHEAT_YIELD_MIN_BOUND_KG_HA",
    "YieldDataValidationError",
    "load_district_yield_records",
]
