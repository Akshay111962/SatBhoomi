"""NASA POWER Daily Point API precipitation connector.

Official Specification:
- API Endpoint: https://power.larc.nasa.gov/api/temporal/daily/point
- Community: AG (Agroclimatology)
- Parameter: PRECTOTCORR (Precipitation Corrected, mm/day)
  * Note: PRECTOTCORR is the corrected bias-adjusted precipitation parameter recommended
    by NASA POWER v2 for agricultural and hydrological applications, derived from MERRA-2
    and calibrated against GPCP (Global Precipitation Climatology Project).
- Spatial Resolution: 0.5° latitude x 0.5° longitude (~55 km x 55 km grid cell).
- Temporal Frequency: Daily time-step.
- Missing Values: NASA POWER encodes missing or uncomputed values as -999.0.
  These are explicitly converted to None and flagged as invalid (never imputed).
- Authentication: Open public access, no API key required.
"""

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from satbhoomi.connectors.rainfall.base import DailyRainfallRecord, RainfallProvider
from satbhoomi.connectors.satellite.base import SeasonWindow

logger = logging.getLogger(__name__)

NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
DEFAULT_CACHE_DIR = Path("data/raw/rainfall")
MISSING_VALUE_SENTINEL = -999.0


class NasaPowerRainfallProvider(RainfallProvider):
    """Fetches daily precipitation from NASA POWER Daily Point API with caching and retry logic."""

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    @property
    def source_name(self) -> str:
        return "nasa_power"

    def _get_cache_path(self, lat: float, lon: float, window: SeasonWindow) -> Path:
        """Return deterministic raw JSON cache path."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        filename = f"power_{lat:.4f}_{lon:.4f}_{window.season_name}.json"
        return self.cache_dir / filename

    def _fetch_from_api(
        self,
        lat: float,
        lon: float,
        start_str: str,
        end_str: str,
    ) -> dict[str, Any]:
        """Execute HTTP GET request to NASA POWER API with retries and exponential backoff."""
        params = {
            "parameters": "PRECTOTCORR",
            "community": "AG",
            "longitude": f"{lon:.4f}",
            "latitude": f"{lat:.4f}",
            "start": start_str,
            "end": end_str,
            "format": "JSON",
        }
        url = f"{NASA_POWER_DAILY_URL}?{urllib.parse.urlencode(params)}"
        headers = {"User-Agent": "SatBhoomi-AgriFinTech/0.1.0"}

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    if resp.status == 200:
                        raw_data = resp.read().decode("utf-8")
                        data: dict[str, Any] = json.loads(raw_data)
                        return data
                    raise RuntimeError(f"NASA POWER API returned HTTP status {resp.status}")
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                last_error = e
                logger.warning(
                    "NASA POWER API request attempt %d failed: %s",
                    attempt,
                    e,
                )
                if attempt < self.max_retries:
                    sleep_time = self.backoff_factor ** (attempt - 1)
                    time.sleep(sleep_time)

        raise RuntimeError(
            f"Failed to fetch NASA POWER rainfall after {self.max_retries} attempts: {last_error}"
        )

    def fetch_daily_rainfall(
        self,
        lat: float,
        lon: float,
        window: SeasonWindow,
    ) -> list[DailyRainfallRecord]:
        """Fetch daily precipitation records for a coordinate and season window."""
        cache_path = self._get_cache_path(lat, lon, window)

        # Check raw cache first
        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                payload = json.load(f)
        else:
            start_str = window.start_date.strftime("%Y%m%d")
            end_str = window.end_date.strftime("%Y%m%d")
            payload = self._fetch_from_api(lat, lon, start_str, end_str)
            # Write raw cached payload
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

        # Parse NASA POWER JSON payload
        # Structure: payload["properties"]["parameter"]["PRECTOTCORR"]["YYYYMMDD"] = value
        try:
            precip_dict = payload["properties"]["parameter"]["PRECTOTCORR"]
        except KeyError as e:
            raise ValueError(
                f"Unexpected NASA POWER response format: missing parameter key {e}"
            ) from e

        records: list[DailyRainfallRecord] = []
        for date_str, raw_val in sorted(precip_dict.items()):
            obs_date = datetime.strptime(date_str, "%Y%m%d").date()
            if not window.contains(obs_date):
                continue

            # Check for missing value sentinel (-999.0)
            if raw_val is None or raw_val <= MISSING_VALUE_SENTINEL:
                precip_mm = None
                is_valid = False
            elif raw_val < 0.0:
                # Any other negative value is invalid
                precip_mm = None
                is_valid = False
            else:
                precip_mm = round(float(raw_val), 2)
                is_valid = True

            records.append(
                DailyRainfallRecord(
                    date=obs_date,
                    precipitation_mm=precip_mm,
                    is_valid=is_valid,
                    source=self.source_name,
                    metadata={"spatial_res": "0.5_deg", "param": "PRECTOTCORR"},
                )
            )

        return records
