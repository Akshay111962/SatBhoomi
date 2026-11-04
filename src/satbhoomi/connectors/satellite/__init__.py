"""Satellite data connectors and aggregation module for Sentinel-2 NDVI time-series."""

from satbhoomi.connectors.satellite.aggregate import (
    MIN_VALID_OBSERVATIONS_THRESHOLD,
    NDVI_MAX_BOUND,
    NDVI_MIN_BOUND,
    aggregate_season_observations,
    validate_observation,
)
from satbhoomi.connectors.satellite.base import (
    NdviProvider,
    PlotLocation,
    RawObservation,
    SeasonAggregate,
    SeasonWindow,
)
from satbhoomi.connectors.satellite.fixture_provider import FixtureNdviProvider
from satbhoomi.connectors.satellite.gee_provider import GoogleEarthEngineProvider
from satbhoomi.connectors.satellite.loader import (
    BUFFER_M_MAX,
    BUFFER_M_MIN,
    INDIA_LAT_MAX,
    INDIA_LAT_MIN,
    INDIA_LON_MAX,
    INDIA_LON_MIN,
    load_sample_plots,
    validate_plot_record,
)
from satbhoomi.connectors.satellite.planetary_provider import PlanetaryComputerProvider
from satbhoomi.connectors.satellite.seasons import (
    format_rabi_season_name,
    get_default_rabi_seasons,
    get_rabi_season_window,
    parse_rabi_season_name,
)

__all__ = [
    "BUFFER_M_MAX",
    "BUFFER_M_MIN",
    "FixtureNdviProvider",
    "GoogleEarthEngineProvider",
    "INDIA_LAT_MAX",
    "INDIA_LAT_MIN",
    "INDIA_LON_MAX",
    "INDIA_LON_MIN",
    "MIN_VALID_OBSERVATIONS_THRESHOLD",
    "NDVI_MAX_BOUND",
    "NDVI_MIN_BOUND",
    "NdviProvider",
    "PlanetaryComputerProvider",
    "PlotLocation",
    "RawObservation",
    "SeasonAggregate",
    "SeasonWindow",
    "aggregate_season_observations",
    "format_rabi_season_name",
    "get_default_rabi_seasons",
    "get_rabi_season_window",
    "load_sample_plots",
    "parse_rabi_season_name",
    "validate_observation",
    "validate_plot_record",
]
