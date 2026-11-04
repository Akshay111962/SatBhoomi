"""Rainfall data connector package for SatBhoomi."""

from satbhoomi.connectors.rainfall.aggregate import aggregate_season_rainfall
from satbhoomi.connectors.rainfall.base import (
    ANAND_RABI_NORMAL_RAINFALL_MM,
    DailyRainfallRecord,
    RainfallAggregate,
    RainfallProvider,
)
from satbhoomi.connectors.rainfall.chirps_provider import ChirpsRainfallProvider
from satbhoomi.connectors.rainfall.fixture_provider import FixtureRainfallProvider
from satbhoomi.connectors.rainfall.nasa_power_provider import NasaPowerRainfallProvider

__all__ = [
    "ANAND_RABI_NORMAL_RAINFALL_MM",
    "ChirpsRainfallProvider",
    "DailyRainfallRecord",
    "FixtureRainfallProvider",
    "NasaPowerRainfallProvider",
    "RainfallAggregate",
    "RainfallProvider",
    "aggregate_season_rainfall",
]
