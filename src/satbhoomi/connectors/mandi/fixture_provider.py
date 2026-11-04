"""Deterministic offline fixture provider for mandi prices testing and CI."""

import hashlib
from datetime import timedelta

from satbhoomi.connectors.mandi.base import DailyMandiRecord, PriceProvider
from satbhoomi.connectors.satellite.base import SeasonWindow


class FixturePriceProvider(PriceProvider):
    """Generates realistic, deterministic daily APMC mandi prices for testing."""

    def __init__(self, simulate_gap: bool = False) -> None:
        self._simulate_gap = simulate_gap

    @property
    def source_name(self) -> str:
        return "fixture"

    def fetch_prices(
        self,
        crop: str,
        state: str,
        district: str,
        window: SeasonWindow,
    ) -> list[DailyMandiRecord]:
        """Generate deterministic mandi prices for the requested district and season."""
        records: list[DailyMandiRecord] = []
        if self._simulate_gap:
            return records

        markets = ["Anand APMC", "Umreth APMC"]
        cur_date = window.start_date

        # Mandis typically operate on weekdays (Mon-Sat, skipping Sundays)
        while cur_date <= window.end_date:
            if cur_date.weekday() != 6:  # Skip Sunday
                for market in markets:
                    key = f"{crop}_{district}_{market}_{cur_date.isoformat()}".encode()
                    hash_val = int(hashlib.sha256(key).hexdigest()[:8], 16)

                    # Base price rises moderately across seasons from 2020 to 2025 (~1950 to 2400)
                    base_price = 2000.0 + (cur_date.year - 2020) * 80.0
                    # Intra-season fluctuation: higher in lean months, slightly dipping
                    # at peak harvest (March/April)
                    seasonal_offset = 50.0 if cur_date.month in (1, 2) else 10.0
                    noise = (hash_val % 100) - 50.0

                    modal = round(base_price + seasonal_offset + noise, 2)
                    min_p = round(modal - 40.0 - (hash_val % 20), 2)
                    max_p = round(modal + 45.0 + (hash_val % 25), 2)
                    arrivals = round(20.0 + (hash_val % 80) * 1.5, 1)

                    records.append(
                        DailyMandiRecord(
                            date=cur_date,
                            market=market,
                            state=state,
                            district=district,
                            commodity=crop,
                            modal_price=modal,
                            min_price=min_p,
                            max_price=max_p,
                            arrivals_tonnes=arrivals,
                            source=self.source_name,
                            metadata={"synthetic": True},
                        )
                    )
            cur_date += timedelta(days=1)

        return records
