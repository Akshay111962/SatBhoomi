"""Google Earth Engine Sentinel-2 Harmonized Surface Reflectance data connector.

Specification:
- Collection: COPERNICUS/S2_SR_HARMONIZED
- Cloud & Shadow Masking: Scene Classification Layer (SCL)
  - Valid: SCL in [4 (Vegetation), 5 (Bare Soils), 6 (Water), 7 (Unclassified)]
  - Masked: SCL in [3 (Shadow), 8 (Med Cloud), 9 (High Cloud), 10 (Cirrus), 11 (Snow)]
- NDVI Formula: (B8 - B4) / (B8 + B4)
- Spatial Extraction: Circular buffer mean reduction around point centroid.
- Project Authentication: Initialized strictly from `GEE_PROJECT` environment variable.
"""

import os
from typing import Any

from satbhoomi.connectors.satellite.base import (
    NdviProvider,
    PlotLocation,
    RawObservation,
    SeasonWindow,
)

# Official Google Earth Engine collection identifier
EE_S2_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"


class GoogleEarthEngineProvider(NdviProvider):
    """Google Earth Engine provider for Sentinel-2 Harmonized Surface Reflectance.

    STATUS: STUB / READY FOR AUTHENTICATION
    This class contains the verified GEE workflow logic. When GEE_PROJECT is configured
    and `earthengine-api` is authenticated, it executes buffer reductions on Earth Engine.
    """

    def __init__(self, project_id: str | None = None) -> None:
        """Initialize provider with project ID from argument or environment."""
        self.project_id = project_id or os.environ.get("GEE_PROJECT")
        self._ee: Any = None
        self._is_initialized = False

    @property
    def source_name(self) -> str:
        """Identifier for GEE source."""
        return "gee"

    def initialize(self) -> None:
        """Attempt to initialize the Earth Engine API using the project ID."""
        if not self.project_id:
            raise RuntimeError(
                "Google Earth Engine project ID not configured. Please set the "
                "GEE_PROJECT environment variable to enable live GEE access."
            )

        try:
            import ee

            ee.Initialize(project=self.project_id)
            self._ee = ee
            self._is_initialized = True
        except ImportError as e:
            raise ImportError(
                "earthengine-api package is required to run live GEE fetch: "
                "pip install earthengine-api"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"Failed to authenticate with GEE for project '{self.project_id}': {e}"
            ) from e

    def build_s2_collection(self, geometry: Any, start_date: str, end_date: str) -> Any:
        """Construct cloud-masked, NDVI-augmented Sentinel-2 ImageCollection."""
        ee = self._ee
        if not self._is_initialized:
            self.initialize()

        def mask_s2_clouds(image: Any) -> Any:
            """Mask clouds and shadows using the SCL (Scene Classification Layer) band."""
            scl = image.select("SCL")
            # Clear pixels: 4=Vegetation, 5=Bare Soil, 6=Water, 7=Unclassified
            clear_mask = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7))
            return image.updateMask(clear_mask)

        def add_ndvi_band(image: Any) -> Any:
            """Calculate NDVI = (B8 - B4) / (B8 + B4)."""
            ndvi = image.normalizedDifference(["B8", "B4"]).rename("NDVI")
            return image.addBands(ndvi)

        collection = (
            ee.ImageCollection(EE_S2_COLLECTION)
            .filterBounds(geometry)
            .filterDate(start_date, end_date)
            .map(mask_s2_clouds)
            .map(add_ndvi_band)
        )
        return collection

    def fetch_observations(
        self,
        plot: PlotLocation,
        window: SeasonWindow,
    ) -> list[RawObservation]:
        """Fetch seasonal observations via Google Earth Engine."""
        if not self._is_initialized:
            self.initialize()

        ee = self._ee
        point = ee.Geometry.Point([plot.lon, plot.lat])
        buffered = point.buffer(plot.buffer_m)

        collection = self.build_s2_collection(
            geometry=buffered,
            start_date=window.start_date.isoformat(),
            end_date=window.end_date.isoformat(),
        )

        def extract_stats(image: Any) -> Any:
            mean_dict = image.select("NDVI").reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=buffered,
                scale=10,
            )
            return image.set("ndvi_mean", mean_dict.get("NDVI"))

        with_stats = collection.map(extract_stats)
        info = with_stats.getInfo()

        observations: list[RawObservation] = []
        for feat in info.get("features", []):
            props = feat.get("properties", {})
            ndvi_val = props.get("ndvi_mean")
            time_ms = props.get("system:time_start")

            if time_ms is None or ndvi_val is None:
                continue

            from datetime import date as d_date

            obs_date = d_date.fromtimestamp(time_ms / 1000.0)
            observations.append(
                RawObservation(
                    date=obs_date,
                    ndvi=float(ndvi_val),
                    is_valid=True,
                    scene_id=feat.get("id"),
                )
            )

        return observations
