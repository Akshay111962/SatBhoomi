"""CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data) connector stub.

This is a clearly marked placeholder stub for future CHIRPS 0.05-degree gridded daily rainfall
integration via Google Earth Engine or USGS/UCSB FTP.
Task link: T-03 (FR-003).
"""

from satbhoomi.connectors.rainfall.base import DailyRainfallRecord, RainfallProvider
from satbhoomi.connectors.satellite.base import SeasonWindow


class ChirpsRainfallProvider(RainfallProvider):
    """Placeholder stub for CHIRPS rainfall provider.

    NOT IMPLEMENTED: CHIRPS requires raster clip/extraction via Earth Engine or netCDF
    processing. NASA POWER daily point API and offline fixtures are used for T-03.
    """

    @property
    def source_name(self) -> str:
        return "chirps"

    def fetch_daily_rainfall(
        self,
        lat: float,
        lon: float,
        window: SeasonWindow,
    ) -> list[DailyRainfallRecord]:
        """Raise NotImplementedError indicating this provider is a stub."""
        raise NotImplementedError(
            "CHIRPS rainfall provider is an unbuilt integration stub. "
            "Use 'nasa_power' or 'fixture' provider instead."
        )
