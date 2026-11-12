"""Offline unit tests for PlanetaryComputerProvider COG NDVI extraction."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import numpy as np
import pyproj
import pytest
import rasterio
from rasterio.transform import from_origin

from satbhoomi.connectors.satellite.base import PlotLocation, SeasonWindow
from satbhoomi.connectors.satellite.planetary_provider import PlanetaryComputerProvider


def _write_utm43_scene_tifs(
    directory: Path,
    lat: float,
    lon: float,
    b04_arr: np.ndarray,
    b08_arr: np.ndarray,
    scl_arr: np.ndarray,
) -> tuple[str, str, str]:
    """Write local UTM 43N B04 (10m), B08 (10m), and SCL (20m) GeoTIFFs centered at (lat, lon)."""
    transformer = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
    cx, cy = transformer.transform(lon, lat)
    h, w = b04_arr.shape
    west = cx - (w * 10.0) / 2.0
    north = cy + (h * 10.0) / 2.0
    transform_10m = from_origin(west, north, 10.0, 10.0)
    transform_20m = from_origin(west, north, 20.0, 20.0)

    b04_path = directory / "B04.tif"
    b08_path = directory / "B08.tif"
    scl_path = directory / "SCL.tif"

    for path, arr, tfm in [
        (b04_path, b04_arr, transform_10m),
        (b08_path, b08_arr, transform_10m),
        (scl_path, scl_arr, transform_20m),
    ]:
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=arr.shape[0],
            width=arr.shape[1],
            count=1,
            dtype=arr.dtype,
            crs="EPSG:32643",
            transform=tfm,
        ) as dst:
            dst.write(arr, 1)

    return str(b04_path), str(b08_path), str(scl_path)


def test_planetary_provider_extracts_scl_masked_ndvi_from_cogs(tmp_path: Path) -> None:
    """Verify exact (B08 - B04)/(B08 + B04) math with 20m SCL cloud masking."""
    lat, lon = 22.5125, 72.9340
    # 10x10 10m grid (100m x 100m); left half clear vegetation (SCL=4), right half cloud (SCL=9)
    b04 = np.full((10, 10), 1000, dtype=np.uint16)
    b08 = np.full((10, 10), 4000, dtype=np.uint16)  # clear NDVI = (4000-1000)/(4000+1000) = 0.6
    b04[:, 6:] = 5000
    b08[:, 6:] = 5000  # cloudy pixels (cols 6..9, matching 20m SCL cols 3..4)

    scl_20m = np.full((5, 5), 4, dtype=np.uint8)
    scl_20m[:, 3:] = 9  # cloud on right columns (60m..100m -> 10m cols 6..9)

    clear_dir = tmp_path / "clear_scene"
    clear_dir.mkdir()
    b04_clear, b08_clear, scl_clear = _write_utm43_scene_tifs(
        clear_dir,
        lat,
        lon,
        b04,
        b08,
        scl_20m,
    )

    cloudy_dir = tmp_path / "cloudy_scene"
    cloudy_dir.mkdir()
    b04_cld, b08_cld, scl_cld = _write_utm43_scene_tifs(
        cloudy_dir,
        lat,
        lon,
        b04,
        b08,
        np.full((5, 5), 8, dtype=np.uint8),
    )

    page_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal page_calls
        if "sas/v1/token" in str(request.url):
            return httpx.Response(200, json={"token": "sig=fake_sas_token"})
        page_calls += 1
        if page_calls == 1:
            return httpx.Response(
                200,
                json={
                    "features": [
                        {
                            "id": "S2_CLEAR_SCENE",
                            "properties": {
                                "datetime": "2024-12-15T05:42:19Z",
                                "eo:cloud_cover": 20.0,
                            },
                            "assets": {
                                "B04": {"href": b04_clear},
                                "B08": {"href": b08_clear},
                                "SCL": {"href": scl_clear},
                            },
                        }
                    ],
                    "links": [
                        {
                            "rel": "next",
                            "href": "https://planetarycomputer.microsoft.com/api/stac/v1/search?page=2",
                            "method": "GET",
                        }
                    ],
                },
            )
        return httpx.Response(
            200,
            json={
                "features": [
                    {
                        "id": "S2_CLOUDY_SCENE",
                        "properties": {
                            "datetime": "2024-12-20T05:42:19Z",
                            "eo:cloud_cover": 75.0,
                        },
                        "assets": {
                            "B04": {"href": b04_cld},
                            "B08": {"href": b08_cld},
                            "SCL": {"href": scl_cld},
                        },
                    }
                ],
                "links": [],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = PlanetaryComputerProvider(http_client=client)

    # Verify SAS token signing behavior
    signed = provider.sign_asset_href("https://sentinel2l2a01.blob.core.windows.net/test.tif")
    assert signed.endswith("?sig=fake_sas_token")
    assert provider.sign_asset_href(b04_clear) == b04_clear

    obs = provider.fetch_observations(
        PlotLocation(plot_code="ANAND_WHEAT_01", lat=lat, lon=lon, buffer_m=30.0),
        SeasonWindow(
            season_name="2024-25", start_date=date(2024, 11, 1), end_date=date(2025, 4, 15)
        ),
    )
    assert page_calls == 2
    assert len(obs) == 2

    assert obs[0].scene_id == "S2_CLEAR_SCENE"
    assert obs[0].is_valid is True
    assert obs[0].ndvi == pytest.approx(0.6, abs=1e-4)
    assert obs[0].scl_class == 4

    assert obs[1].scene_id == "S2_CLOUDY_SCENE"
    assert obs[1].is_valid is False
    assert obs[1].ndvi is None
    assert obs[1].scl_class == 8


def test_planetary_provider_skips_missing_assets() -> None:
    """Verify scenes lacking B04/B08/SCL assets are skipped cleanly."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "features": [
                    {
                        "id": "S2_INCOMPLETE",
                        "properties": {"datetime": "2024-12-10T05:42:19Z", "eo:cloud_cover": 5.0},
                        "assets": {"B04": {"href": "only_b04.tif"}},
                    }
                ],
                "links": [],
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = PlanetaryComputerProvider(http_client=client)
    obs = provider.fetch_observations(
        PlotLocation(plot_code="P1", lat=22.5, lon=72.9, buffer_m=50.0),
        SeasonWindow(
            season_name="2024-25", start_date=date(2024, 11, 1), end_date=date(2025, 4, 15)
        ),
    )
    assert obs == []
