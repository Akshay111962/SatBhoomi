# SatBhoomi Score + Raksha — Satellite Data Sources Specification (Task T-02)

This document specifies the satellite data sources, spectral band mathematics, cloud/shadow filtering rules, seasonal aggregation logic, and analytical limitations for **Task T-02 (Satellite NDVI Connector)**.

---

## 1. Primary Data Sources & Collections

| Provider | Collection Identifier | Spatial Resolution | Revisit Cadence | Access Mode |
| :--- | :--- | :--- | :--- | :--- |
| **Sentinel-2 L2A (Copernicus / GEE)** | `COPERNICUS/S2_SR_HARMONIZED` | 10m (B4, B8), 20m (SCL) | 5 days (constellation 2A + 2B) | Earth Engine Python API (`GEE_PROJECT`) |
| **Microsoft Planetary Computer** | `sentinel-2-l2a` (STAC API) | 10m (B04, B08), 20m (SCL) | 5 days | Public STAC Search & Blob Assets |
| **Offline Test Fixtures** | Deterministic phenology model | Point centroid | 5 days | Offline local CSV & JSON cache |

---

## 2. Band Mathematics & Vegetation Index Formulation

Normalized Difference Vegetation Index (NDVI) is computed per pixel as:

$$\text{NDVI} = \frac{B8 - B4}{B8 + B4}$$

- **Band 8 (Near-Infrared / NIR)**: Central wavelength ~842 nm (10m resolution). Highly reflected by healthy green leaf mesophyll.
- **Band 4 (Red)**: Central wavelength ~665 nm (10m resolution). Strongly absorbed by chlorophyll $a$ and $b$ for photosynthesis.
- **Valid Numerical Bounds**: Strict mathematical range $[-1.0, 1.0]$. Values outside this boundary indicate corrupted sensors or invalid atmospheric corrections and are rejected.

---

## 3. Cloud & Shadow Masking (Scene Classification Layer - SCL)

Sentinel-2 Level-2A data includes an algorithmic Scene Classification Layer (SCL) at 20m resolution. Observations are masked as follows:

| SCL Class Code | Class Name | Masking Action | Justification |
| :---: | :--- | :---: | :--- |
| `0` | NO_DATA | **Exclude** | Missing sensor data |
| `1` | SATURATED_OR_DEFECTIVE | **Exclude** | Sensor saturation artifact |
| `2` | DARK_AREA_PIXELS | Include | Valid topographic dark terrain |
| `3` | CLOUD_SHADOWS | **Exclude** | Shadow causes severe NDVI drops |
| `4` | VEGETATION | **Include** | Primary agricultural target |
| `5` | NOT_VEGETATED (Soil) | **Include** | Early vegetative / fallow baseline |
| `6` | WATER | Include | Water bodies (negative NDVI) |
| `7` | UNCLASSIFIED | Include | Unclassified surface reflectance |
| `8` | CLOUD_MEDIUM_PROBABILITY | **Exclude** | Partial cloud haze |
| `9` | CLOUD_HIGH_PROBABILITY | **Exclude** | Dense opaque cloud |
| `10` | THIN_CIRRUS | **Exclude** | Atmospheric ice-crystal reflection |
| `11` | SNOW_ICE | **Exclude** | Freezing contamination |

---

## 4. Seasonal Aggregation Standards

- **Standard Season Naming**: Uniform string format `YYYY-YY` (e.g., `2021-22`, `2022-23`, `2023-24`, `2024-25`). Defined in `src/satbhoomi/connectors/satellite/seasons.py`.
- **Rabi Cropping Window**: November 1 to April 15.
- **Early Season Window (`ndvi_early`)**: First 6 weeks (42 days) from November 1 (Nov 1 to Dec 13) capturing germination and initial vegetative establishment.
- **Minimum Observations Rule**: At least **4 clear, cloud-free observations** (`valid_obs_count >= 4`) are required across the 5.5-month season. If `valid_obs_count < 4`, the record is explicitly flagged with `data_gap = True`.
- **Honesty Rule**: Missing observations are never invented, imputed, or silently filled. Missing values remain `None` when valid count is zero.

---

## 5. Methodological Assumptions & Known Limitations

1. **Circular Buffer vs. True Boundary**:
   - Smallholder farmers in India typically cultivate fragmented plots (0.5 to 2.5 acres).
   - In this PoC, plot coordinates represent **field centroids** with a circular buffer radius (30m to 100m).
   - Buffers are approximations and do not correspond to official cadastral land boundaries.
2. **Mixed Pixel Effects**:
   - A 10m Sentinel-2 pixel on plot edges may encompass irrigation furrows, bunds, farm roads, or adjacent uncultivated land.
3. **Cloud Gaps**:
   - Extended winter overcast periods may result in observational gaps during vegetative heading. The system marks these with a `data-gap` banner.
4. **Sample Points vs. Real Farmers**:
   - Plot coordinates in `data/synthetic/sample_plots.csv` are sample points visually identified in satellite imagery, not linked to real human farmers.

---

## 6. How to Run the Fetch Script

### Using Make:
```bash
make fetch-ndvi
```

### Using PowerShell directly on Windows:
```powershell
.venv\Scripts\python.exe scripts/fetch_ndvi.py --provider fixture
```

### Dry Run (Validation only):
```powershell
.venv\Scripts\python.exe scripts/fetch_ndvi.py --dry-run
```

### Live Planetary Computer STAC Fetch (Requires Network):
```powershell
.venv\Scripts\python.exe scripts/fetch_ndvi.py --provider planetary
```
