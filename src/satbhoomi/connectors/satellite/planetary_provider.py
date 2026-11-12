"""Microsoft Planetary Computer Sentinel-2 L2A STAC data connector."""

from __future__ import annotations

import logging
import math
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import numpy as np
import pyproj
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window, from_bounds

from satbhoomi.connectors.satellite.base import (
    NdviProvider,
    PlotLocation,
    RawObservation,
    SeasonWindow,
)

logger = logging.getLogger(__name__)

# Planetary Computer STAC & SAS endpoints
PLANETARY_STAC_SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PLANETARY_SAS_TOKEN_URL = "https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a"
SENTINEL_COLLECTION = "sentinel-2-l2a"

# Sentinel-2 Scene Classification Layer (SCL) invalid/cloud classes:
# 3: Shadow, 8: Med Cloud, 9: High Cloud, 10: Cirrus, 11: Snow, 0: No data, 1: Defective
SCL_INVALID_CLASSES = (0, 1, 3, 8, 9, 10, 11)


def compute_bbox_from_centroid(lat: float, lon: float, buffer_m: float) -> list[float]:
    """Compute approximate bbox [min_lon, min_lat, max_lon, max_lat] from center & buffer."""
    delta_lat = buffer_m / 111320.0
    rad = math.radians(lat)
    delta_lon = buffer_m / (111320.0 * max(0.1, math.cos(rad)))

    return [
        round(lon - delta_lon, 6),
        round(lat - delta_lat, 6),
        round(lon + delta_lon, 6),
        round(lat + delta_lat, 6),
    ]


class PlanetaryComputerProvider(NdviProvider):
    """Sentinel-2 Level-2A provider using Microsoft Planetary Computer STAC + COG reads."""

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        max_retries: int = 3,
        backoff_sec: float = 1.0,
        max_stac_pages: int = 5,
        sas_token_fetcher: Callable[[], str] | None = None,
    ) -> None:
        """Initialize provider with optional HTTP client, retry, and SAS token config."""
        self.http_client = http_client or httpx.Client(timeout=30.0)
        self.max_retries = max_retries
        self.backoff_sec = backoff_sec
        self.max_stac_pages = max_stac_pages
        self._sas_token_fetcher = sas_token_fetcher
        self._cached_sas_token: str | None = None
        self._cached_sas_expiry: datetime | None = None

    @property
    def source_name(self) -> str:
        """Identifier for Planetary Computer source."""
        return "planetary"

    def _get_sas_token(self, force_refresh: bool = False) -> str:
        """Fetch and cache the Planetary Computer SAS token with expiry awareness."""
        now = datetime.now(UTC)
        if (
            not force_refresh
            and self._cached_sas_token is not None
            and (self._cached_sas_expiry is None or now < self._cached_sas_expiry)
        ):
            return self._cached_sas_token
        if self._sas_token_fetcher is not None:
            self._cached_sas_token = self._sas_token_fetcher()
            self._cached_sas_expiry = now + timedelta(minutes=30)
            return self._cached_sas_token

        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.http_client.get(PLANETARY_SAS_TOKEN_URL)
                response.raise_for_status()
                payload = response.json()
                token = str(payload["token"])
                expiry_str = payload.get("msft:expiry")
                if expiry_str:
                    expiry_dt = datetime.fromisoformat(str(expiry_str).replace("Z", "+00:00"))
                    self._cached_sas_expiry = expiry_dt - timedelta(seconds=120)
                else:
                    self._cached_sas_expiry = now + timedelta(minutes=30)
                self._cached_sas_token = token
                return token
            except (httpx.HTTPError, KeyError, ValueError) as exc:
                if attempt == self.max_retries:
                    msg = f"Failed to fetch Planetary SAS token: {exc}"
                    raise ConnectionError(msg) from exc
                time.sleep(self.backoff_sec * (2 ** (attempt - 1)))
        return ""

    def sign_asset_href(self, href: str, force_refresh: bool = False) -> str:
        """Append SAS query token to Azure Blob URLs; leave local/non-Azure paths untouched."""
        if "blob.core.windows.net" not in href:
            return href
        token = self._get_sas_token(force_refresh=force_refresh)
        if not token:
            return href
        sep = "&" if "?" in href else "?"
        return f"{href}{sep}{token}"

    def search_stac_items(
        self,
        bbox: list[float],
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Query Planetary Computer STAC API for Sentinel-2 L2A scenes with pagination."""
        payload: dict[str, Any] = {
            "collections": [SENTINEL_COLLECTION],
            "bbox": bbox,
            "datetime": f"{start_date.isoformat()}T00:00:00Z/{end_date.isoformat()}T23:59:59Z",
            "query": {"eo:cloud_cover": {"lt": 80}},
            "limit": 100,
        }

        all_features: list[dict[str, Any]] = []
        next_url: str | None = PLANETARY_STAC_SEARCH_URL
        next_body: dict[str, Any] | None = payload

        for _ in range(self.max_stac_pages):
            if next_url is None:
                break
            data = self._post_or_get_stac(next_url, next_body)
            all_features.extend(data.get("features", []))
            next_link = next(
                (lnk for lnk in data.get("links", []) if lnk.get("rel") == "next"),
                None,
            )
            if not next_link:
                break
            next_url = next_link.get("href")
            next_body = next_link.get("body") if next_link.get("method") == "POST" else None

        return all_features

    def _post_or_get_stac(self, url: str, json_body: dict[str, Any] | None) -> dict[str, Any]:
        """Execute a retried STAC request (POST when body provided, otherwise GET)."""
        for attempt in range(1, self.max_retries + 1):
            try:
                if json_body is not None:
                    response = self.http_client.post(url, json=json_body)
                else:
                    response = self.http_client.get(url)
                response.raise_for_status()
                return dict(response.json())
            except httpx.HTTPError as exc:
                logger.warning(
                    "Planetary STAC request failed (attempt %d/%d): %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt == self.max_retries:
                    msg = (
                        f"Failed to fetch Planetary STAC items after {self.max_retries} "
                        f"tries: {exc}"
                    )
                    raise ConnectionError(msg) from exc
                time.sleep(self.backoff_sec * (2 ** (attempt - 1)))
        return {}

    def _extract_scene_ndvi(
        self,
        b04_href: str,
        b08_href: str,
        scl_href: str,
        bbox: list[float],
    ) -> tuple[float | None, bool, int]:
        """Read B04, B08, and SCL over bbox and compute cloud-masked mean NDVI."""
        env_opts = {
            "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
            "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
        }
        with (
            rasterio.Env(**env_opts),
            rasterio.open(b04_href) as b04_src,
            rasterio.open(b08_href) as b08_src,
            rasterio.open(scl_href) as scl_src,
        ):
            transformer = pyproj.Transformer.from_crs(
                "EPSG:4326",
                b04_src.crs,
                always_xy=True,
            )
            min_x, min_y = transformer.transform(bbox[0], bbox[1])
            max_x, max_y = transformer.transform(bbox[2], bbox[3])

            raw_win = from_bounds(min_x, min_y, max_x, max_y, transform=b04_src.transform)
            win = raw_win.round_offsets().round_lengths()
            col_off = max(0, min(int(win.col_off), b04_src.width - 1))
            row_off = max(0, min(int(win.row_off), b04_src.height - 1))
            width = max(1, min(int(win.width) or 1, b04_src.width - col_off))
            height = max(1, min(int(win.height) or 1, b04_src.height - row_off))
            b04_window = Window(col_off, row_off, width, height)

            red = b04_src.read(1, window=b04_window).astype(np.float32)
            b08_win = from_bounds(min_x, min_y, max_x, max_y, transform=b08_src.transform)
            nir = b08_src.read(
                1,
                window=b08_win,
                out_shape=red.shape,
                resampling=Resampling.nearest,
            ).astype(np.float32)

            scl_win = from_bounds(min_x, min_y, max_x, max_y, transform=scl_src.transform)
            scl = scl_src.read(
                1,
                window=scl_win,
                out_shape=red.shape,
                resampling=Resampling.nearest,
            ).astype(np.int32)

        valid_mask = (
            (~np.isin(scl, SCL_INVALID_CLASSES)) & (red > 0) & (nir > 0) & ((nir + red) > 0)
        )
        if not np.any(valid_mask):
            vals, counts = np.unique(scl, return_counts=True)
            dominant_scl = int(vals[int(np.argmax(counts))]) if len(vals) else 8
            return None, False, dominant_scl

        ndvi_arr = (nir[valid_mask] - red[valid_mask]) / (nir[valid_mask] + red[valid_mask])
        ndvi_val = round(float(np.clip(np.mean(ndvi_arr), -1.0, 1.0)), 4)
        vals, counts = np.unique(scl[valid_mask], return_counts=True)
        dominant_scl = int(vals[int(np.argmax(counts))]) if len(vals) else 4
        return ndvi_val, True, dominant_scl

    def _read_feature_observation(
        self,
        feat: dict[str, Any],
        obs_date: date,
        bbox: list[float],
    ) -> RawObservation | None:
        """Read one STAC feature's COG pixels, refreshing SAS token once on 403."""
        props = feat.get("properties", {})
        scene_id = str(feat.get("id", "S2_UNKNOWN"))
        cloud_cover = float(props.get("eo:cloud_cover", 0.0))
        assets = feat.get("assets", {})
        b04_href = assets.get("B04", {}).get("href")
        b08_href = assets.get("B08", {}).get("href")
        scl_href = assets.get("SCL", {}).get("href")

        if not (b04_href and b08_href and scl_href):
            logger.warning("Scene %s missing B04/B08/SCL assets; skipping", scene_id)
            return None

        for force_refresh in (False, True):
            try:
                ndvi_val, is_valid, scl_class = self._extract_scene_ndvi(
                    self.sign_asset_href(str(b04_href), force_refresh=force_refresh),
                    self.sign_asset_href(str(b08_href), force_refresh=force_refresh),
                    self.sign_asset_href(str(scl_href), force_refresh=force_refresh),
                    bbox,
                )
                return RawObservation(
                    date=obs_date,
                    ndvi=ndvi_val,
                    is_valid=is_valid,
                    cloud_prob=cloud_cover,
                    scl_class=scl_class,
                    scene_id=scene_id,
                )
            except Exception as exc:
                if not force_refresh and "403" in str(exc):
                    logger.info("SAS token rejected (403) for %s; refreshing token", scene_id)
                    continue
                logger.warning("Failed reading COG pixels for scene %s: %s", scene_id, exc)
                return None
        return None

    def fetch_observations(
        self,
        plot: PlotLocation,
        window: SeasonWindow,
    ) -> list[RawObservation]:
        """Fetch and extract Sentinel-2 observations over plot buffer via Planetary Computer.

        Calculates NDVI = (B08 - B04) / (B08 + B04) with SCL scene classification masking,
        selecting the lowest-cloud-cover tile per acquisition date.
        """
        bbox = compute_bbox_from_centroid(plot.lat, plot.lon, plot.buffer_m)
        features = self.search_stac_items(bbox, window.start_date, window.end_date)

        by_date: dict[date, list[dict[str, Any]]] = {}
        for feat in features:
            dt_str = feat.get("properties", {}).get("datetime")
            if not dt_str:
                continue
            obs_date = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).date()
            if window.contains(obs_date):
                by_date.setdefault(obs_date, []).append(feat)

        observations: list[RawObservation] = []
        for obs_date in sorted(by_date):
            candidates = sorted(
                by_date[obs_date],
                key=lambda f: float(f.get("properties", {}).get("eo:cloud_cover", 100.0)),
            )
            for feat in candidates:
                obs = self._read_feature_observation(feat, obs_date, bbox)
                if obs is not None:
                    observations.append(obs)
                    break

        return observations
