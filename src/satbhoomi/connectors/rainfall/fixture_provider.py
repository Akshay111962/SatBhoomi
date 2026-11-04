"""Deterministic offline fixture provider for daily precipitation testing and CI."""

import hashlib
from datetime import timedelta

from satbhoomi.connectors.rainfall.base import DailyRainfallRecord, RainfallProvider
from satbhoomi.connectors.satellite.base import SeasonWindow


class FixtureRainfallProvider(RainfallProvider):
    """Generates realistic, deterministic daily rainfall records without external network calls."""

    def __init__(self, simulate_gap: bool = False, missing_day_count: int = 20) -> None:
        """Initialize fixture provider.

        Args:
            simulate_gap: If True, omit `missing_day_count` days to trigger data_gap detection.
            missing_day_count: Number of unobserved days to simulate if simulate_gap is True.
        """
        self._simulate_gap = simulate_gap
        self._missing_day_count = missing_day_count

    @property
    def source_name(self) -> str:
        return "fixture"

    def fetch_daily_rainfall(
        self,
        lat: float,
        lon: float,
        window: SeasonWindow,
    ) -> list[DailyRainfallRecord]:
        """Generate deterministic daily rainfall for the requested season window."""
        records: list[DailyRainfallRecord] = []
        cur_date = window.start_date
        total_days = (window.end_date - window.start_date).days + 1

        day_index = 0
        while cur_date <= window.end_date:
            day_index += 1
            # If simulating gaps, omit the last `missing_day_count` days
            if self._simulate_gap and day_index > (total_days - self._missing_day_count):
                cur_date += timedelta(days=1)
                continue

            # Deterministic pseudo-random seed based on lat, lon, date
            key = f"{lat:.4f}_{lon:.4f}_{cur_date.isoformat()}".encode()
            hash_val = int(hashlib.sha256(key).hexdigest()[:8], 16)

            # In Anand Rabi winter (Nov-Apr), ~90% of days are completely dry (0.0 mm).
            # Sporadic winter disturbances yield 1.0 to 12.0 mm on ~10% of days.
            if hash_val % 100 < 88:
                rain_mm = 0.0
            else:
                rain_mm = round(1.0 + (hash_val % 110) / 10.0, 2)

            records.append(
                DailyRainfallRecord(
                    date=cur_date,
                    precipitation_mm=rain_mm,
                    is_valid=True,
                    source=self.source_name,
                    metadata={"synthetic": True},
                )
            )
            cur_date += timedelta(days=1)

        return records
