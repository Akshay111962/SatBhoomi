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
                                "s2:processing_baseline": "02.14",
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


def test_pre_and_post_0400_offset_correction_equivalence(tmp_path: Path) -> None:
    """Pre-04.00 and post-04.00 scenes with identical true reflectance produce identical NDVI."""
    lat, lon = 22.5125, 72.9340
    # True reflectance: rho_red = 0.06, rho_nir = 0.34 -> True NDVI = 0.7000
    # Pre-04.00 (offset 0): DN_red = 600, DN_nir = 3400
    # Post-04.00 (offset -1000): DN_red = 1600, DN_nir = 4400
    scl_grid = np.full((5, 5), 4, dtype=np.uint8)

    pre_dir = tmp_path / "pre_0400"
    pre_dir.mkdir()
    b04_pre, b08_pre, scl_pre = _write_utm43_scene_tifs(
        pre_dir,
        lat,
        lon,
        np.full((10, 10), 600, dtype=np.uint16),
        np.full((10, 10), 3400, dtype=np.uint16),
        scl_grid,
    )

    post_dir = tmp_path / "post_0400"
    post_dir.mkdir()
    b04_post, b08_post, scl_post = _write_utm43_scene_tifs(
        post_dir,
        lat,
        lon,
        np.full((10, 10), 1600, dtype=np.uint16),
        np.full((10, 10), 4400, dtype=np.uint16),
        scl_grid,
    )

    provider = PlanetaryComputerProvider()
    bbox = [72.93, 22.51, 72.94, 22.52]

    # Pre-04.00 with baseline offset 0.0
    ndvi_pre, is_valid_pre, _ = provider._extract_scene_ndvi(
        b04_pre, b08_pre, scl_pre, bbox, offset=0.0
    )
    # Post-04.00 with baseline offset -1000.0
    ndvi_post, is_valid_post, _ = provider._extract_scene_ndvi(
        b04_post, b08_post, scl_post, bbox, offset=-1000.0
    )
    # Post-04.00 uncorrected (buggy: offset 0.0)
    ndvi_uncorr, is_valid_uncorr, _ = provider._extract_scene_ndvi(
        b04_post, b08_post, scl_post, bbox, offset=0.0
    )

    assert is_valid_pre is True
    assert is_valid_post is True
    assert is_valid_uncorr is True

    # Corrected values are identical and match true NDVI 0.7000
    assert ndvi_pre == pytest.approx(0.7000, abs=1e-4)
    assert ndvi_post == pytest.approx(0.7000, abs=1e-4)
    assert ndvi_pre == pytest.approx(ndvi_post, abs=1e-4)

    # Uncorrected value differs significantly (proves test discriminates the bug)
    assert ndvi_uncorr == pytest.approx(0.4667, abs=1e-4)
    assert abs(ndvi_post - ndvi_uncorr) > 0.20


def test_metadata_offset_used_when_present() -> None:
    """Scene with metadata offset in raster:bands uses it with offset_rule='metadata'."""
    provider = PlanetaryComputerProvider()
    feat = {
        "id": "S2_META_OFFSET",
        "properties": {"datetime": "2023-01-15T05:40:00Z"},
        "assets": {
            "B04": {
                "href": "b04.tif",
                "raster:bands": [{"offset": -1000.0, "scale": 0.0001}],
            }
        },
    }
    offset, rule, baseline = provider._determine_processing_offset(feat, date(2023, 1, 15))
    assert offset == -1000.0
    assert rule == "metadata"
    assert baseline is None


def test_date_fallback_flagged_when_baseline_missing() -> None:
    """Scene without metadata or s2:processing_baseline falls back to date and is flagged."""
    provider = PlanetaryComputerProvider()
    feat = {"id": "S2_NO_BASELINE", "properties": {}, "assets": {}}

    # Post-cutoff date
    offset_post, rule_post, bl_post = provider._determine_processing_offset(feat, date(2022, 2, 1))
    assert offset_post == -1000.0
    assert rule_post == "date_fallback"
    assert bl_post is None

    # Pre-cutoff date
    offset_pre, rule_pre, bl_pre = provider._determine_processing_offset(feat, date(2021, 12, 1))
    assert offset_pre == 0.0
    assert rule_pre == "date_fallback"
    assert bl_pre is None


def test_raw_dn_zero_stays_nodata_after_correction(tmp_path: Path) -> None:
    """Raw DN == 0 is nodata and remains masked after offset is applied."""
    lat, lon = 22.5125, 72.9340
    # All raw DN are 0, with clear SCL=4
    b04_zero = np.zeros((10, 10), dtype=np.uint16)
    b08_zero = np.zeros((10, 10), dtype=np.uint16)
    scl_grid = np.full((5, 5), 4, dtype=np.uint8)

    z_dir = tmp_path / "zero_scene"
    z_dir.mkdir()
    b04_p, b08_p, scl_p = _write_utm43_scene_tifs(z_dir, lat, lon, b04_zero, b08_zero, scl_grid)

    provider = PlanetaryComputerProvider()
    bbox = [72.93, 22.51, 72.94, 22.52]
    ndvi, is_valid, scl_class = provider._extract_scene_ndvi(
        b04_p, b08_p, scl_p, bbox, offset=-1000.0
    )
    assert is_valid is False
    assert ndvi is None


def test_dark_pixel_slightly_negative_reflectance_handled_without_error(tmp_path: Path) -> None:
    """A dark pixel whose corrected reflectance is slightly negative is handled without crash."""
    lat, lon = 22.5125, 72.9340
    # Post-04.00 offset -1000. DN_red=950 -> rho_red=-0.0050. DN_nir=2050 -> rho_nir=+0.1050.
    # nir + red = 0.1000 > 0. nir - red = 0.1100. NDVI = 1.1000 -> clipped to 1.0.
    b04_dark = np.full((10, 10), 950, dtype=np.uint16)
    b08_dark = np.full((10, 10), 2050, dtype=np.uint16)
    scl_grid = np.full((5, 5), 4, dtype=np.uint8)

    d_dir = tmp_path / "dark_scene"
    d_dir.mkdir()
    b04_p, b08_p, scl_p = _write_utm43_scene_tifs(d_dir, lat, lon, b04_dark, b08_dark, scl_grid)

    provider = PlanetaryComputerProvider()
    bbox = [72.93, 22.51, 72.94, 22.52]
    ndvi, is_valid, _ = provider._extract_scene_ndvi(b04_p, b08_p, scl_p, bbox, offset=-1000.0)
    assert is_valid is True
    assert ndvi == pytest.approx(1.0000, abs=1e-4)


def test_cached_observation_validation_fails_if_fields_missing() -> None:
    """Cached observations must contain all v2 provenance fields, failing if any are missing."""
    from scripts.fetch_ndvi import deserialize_observation

    valid_record = {
        "date": "2023-01-15",
        "ndvi": 0.65,
        "is_valid": True,
        "cloud_prob": 10.0,
        "scl_class": 4,
        "scene_id": "S2A_TEST",
        "processing_baseline": "05.10",
        "offset_applied": -1000.0,
        "offset_rule": "baseline",
        "provider_logic_version": "v2_pb_offset_corrected",
    }
    # Deserializes successfully
    obs = deserialize_observation(valid_record, require_v2=True)
    assert obs.processing_baseline == "05.10"
    assert obs.offset_applied == -1000.0
    assert obs.offset_rule == "baseline"
    assert obs.provider_logic_version == "v2_pb_offset_corrected"

    # Fails if any required v2 field is missing
    for missing_field in (
        "processing_baseline",
        "offset_applied",
        "offset_rule",
        "provider_logic_version",
    ):
        bad_record = dict(valid_record)
        del bad_record[missing_field]
        with pytest.raises(
            ValueError, match=f"Cached observation missing required field '{missing_field}'"
        ):
            deserialize_observation(bad_record, require_v2=True)
