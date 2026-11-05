"""CEDA (Centre for Economic Data and Analysis, Ashoka University) Agri Market API connector.

Official Specification & Terms:
- Source: CEDA Agri-Market Daily Price and Arrival Portal
- Official Portal: https://ceda.ashoka.edu.in/agri-market/
- Data origin: Daily Agmarknet mandi market bulletins, cleaned, harmonized, and standardized.
- Commodity Coverage: Cereals (including Wheat / Triticum aestivum), Pulses, Oilseeds, Vegetables.
- Geographic Coverage: District and APMC market-level across India.
- Authentication: API key passed via HTTP header ('Authorization: Bearer <key>' or 'x-api-key').
- Rate Limits: CEDA requests researchers to limit queries to <= 10 calls/minute.
- Live Status: Marked as 'not verified against live data' unless executed live with user approval.
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from satbhoomi.config import get_settings
from satbhoomi.connectors.mandi.base import DailyMandiRecord, PriceProvider
from satbhoomi.connectors.satellite.base import SeasonWindow

logger = logging.getLogger(__name__)

CEDA_API_BASE_URL = "https://ceda.ashoka.edu.in/api/v1/agri-market/daily"
DEFAULT_CACHE_DIR = Path("data/raw/mandi")


class CedaPriceProvider(PriceProvider):
    """Fetches APMC mandi prices from CEDA Agri Market API with local caching and retries."""

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> None:
        # Load API key strictly from parameter, environment, or settings; NEVER print or hardcode
        if api_key is not None:
            self._api_key = api_key
        else:
            settings = get_settings()
            self._api_key = os.getenv("CEDA_API_KEY") or settings.ceda_api_key
        self.cache_dir = Path(cache_dir)
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    @property
    def source_name(self) -> str:
        return "ceda"

    def _get_cache_path(
        self,
        crop: str,
        district: str,
        window: SeasonWindow,
    ) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        filename = f"ceda_{crop.lower()}_{district.lower()}_{window.season_name}.json"
        return self.cache_dir / filename

    def _fetch_from_api(  # pragma: no cover
        self,
        crop: str,
        state: str,
        district: str,
        start_str: str,
        end_str: str,
    ) -> dict[str, Any]:
        """Execute authenticated request to CEDA API with retries.

        This method makes live network calls and cannot be exercised in offline CI.
        It is excluded from coverage measurement.
        """
        if not self._api_key or not self._api_key.strip():
            raise ValueError(
                "CEDA_API_KEY environment variable is not configured. "
                "To obtain an API key, register for academic/research access at "
                "https://ceda.ashoka.edu.in/agri-market/ and add CEDA_API_KEY to your .env file."
            )

        params = {
            "commodity": crop,
            "state": state,
            "district": district,
            "from_date": start_str,
            "to_date": end_str,
        }
        url = f"{CEDA_API_BASE_URL}?{urllib.parse.urlencode(params)}"
        headers = {
            "Authorization": f"Bearer {self._api_key.strip()}",
            "x-api-key": self._api_key.strip(),
            "User-Agent": "SatBhoomi-AgriFinTech/0.1.0",
            "Accept": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    if resp.status == 200:
                        raw_data = resp.read().decode("utf-8")
                        data: dict[str, Any] = json.loads(raw_data)
                        return data
                    raise RuntimeError(f"CEDA API returned HTTP status {resp.status}")
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
                last_error = e
                logger.warning(
                    "CEDA API request attempt %d failed: %s",
                    attempt,
                    e,
                )
                if attempt < self.max_retries:
                    sleep_time = self.backoff_factor ** (attempt - 1)
                    time.sleep(sleep_time)

        raise RuntimeError(
            f"Failed to fetch CEDA mandi prices after {self.max_retries} attempts: {last_error}"
        )

    def fetch_prices(
        self,
        crop: str,
        state: str,
        district: str,
        window: SeasonWindow,
    ) -> list[DailyMandiRecord]:
        """Fetch daily mandi records for crop, district, and season window."""
        cache_path = self._get_cache_path(crop, district, window)

        if cache_path.exists():
            with open(cache_path, encoding="utf-8") as f:
                payload = json.load(f)
        else:
            start_str = window.start_date.isoformat()
            end_str = window.end_date.isoformat()
            payload = self._fetch_from_api(crop, state, district, start_str, end_str)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)

        raw_records = payload.get("data", [])
        records: list[DailyMandiRecord] = []
        for item in raw_records:
            try:
                obs_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
            except (ValueError, KeyError):
                continue

            if not window.contains(obs_date):
                continue

            try:
                modal = float(item["modal_price"])
            except (ValueError, TypeError, KeyError):
                continue

            if modal <= 0:
                continue

            records.append(
                DailyMandiRecord(
                    date=obs_date,
                    market=item.get("market", district),
                    state=state,
                    district=district,
                    commodity=crop,
                    modal_price=modal,
                    min_price=float(item["min_price"]) if item.get("min_price") else None,
                    max_price=float(item["max_price"]) if item.get("max_price") else None,
                    arrivals_tonnes=(
                        float(item["arrivals_tonnes"]) if item.get("arrivals_tonnes") else None
                    ),
                    source=self.source_name,
                    metadata={"api_version": "v1"},
                )
            )

        records.sort(key=lambda r: (r.date, r.market))
        return records
