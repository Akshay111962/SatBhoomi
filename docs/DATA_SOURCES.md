# SatBhoomi Score + Raksha — Multi-Source Data Sources Specification (Tasks T-02 & T-03)

This document specifies the data sources, mathematical formulas, physical bounds, validation rules, seasonal aggregation logic, and analytical limitations across satellite, precipitation, market price, and district yield connectors.

---

## 1. Primary Data Sources & Collections

| Domain | Provider | Collection / Endpoint | Spatial Resolution | Temporal Frequency | Access Mode | Live Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Vegetation Index (NDVI)** | **Microsoft Planetary Computer** | `sentinel-2-l2a` (STAC API) | 10m (B04, B08), 20m (SCL) | 5 days | Public STAC Search & Blob Assets | Verified live against 12 Anand points |
| **Vegetation Index (NDVI)** | **Sentinel-2 L2A (GEE)** | `COPERNICUS/S2_SR_HARMONIZED` | 10m (B4, B8), 20m (SCL) | 5 days | Earth Engine Python API (`GEE_PROJECT`) | Built; not verified against live data |
| **Vegetation Index (NDVI)** | **Offline Fixtures** | Deterministic phenology model | Point centroid | 5 days | Offline Python generator & cache | Verified offline |
| **Precipitation (Rainfall)** | **NASA POWER** | `api/temporal/daily/point` (AG) | 0.5° x 0.5° (~55 km) | Daily | Public HTTP GET (no key) | Built with retry & cache; offline fixture tested |
| **Precipitation (Rainfall)** | **Offline Fixtures** | Deterministic winter disturbance model | Point centroid | Daily | Offline Python generator | Verified offline |
| **Precipitation (Rainfall)** | **CHIRPS** | Placeholder integration stub | 0.05° gridded | Daily | Unbuilt stub (`NotImplementedError`) | Stub only |
| **Mandi Prices** | **CEDA Agri Market API** | `api/v1/agri-market/daily` (Ashoka Univ.) | District / APMC | Daily market arrivals | `CEDA_API_KEY` header authentication | Built; not verified against live data |
| **Mandi Prices** | **Historical APMC CSV** | `data/external/mandi_prices_wheat.csv` | Market-day (Anand, Umreth) | Weekly / Daily trading days | Local validated CSV file | Verified offline (280 records across 5 seasons) |
| **Mandi Prices** | **Offline Fixtures** | Deterministic APMC model | Market-day | Daily | Offline Python generator | Verified offline |
| **District Crop Yield** | **Directorate of Agriculture, Gujarat** | `data/external/district_yield_wheat.csv` | Administrative District (Anand) | Annual / Seasonal | Local validated CSV file | Verified offline (official published data 2020-25) |

---

## 2. Band Mathematics & Vegetation Index Formulation (T-02)

Normalized Difference Vegetation Index (NDVI) is computed per pixel as:

$$\text{NDVI} = \frac{B8 - B4}{B8 + B4}$$

- **Band 8 (Near-Infrared / NIR)**: Central wavelength ~842 nm (10m resolution). Highly reflected by healthy green leaf mesophyll.
- **Band 4 (Red)**: Central wavelength ~665 nm (10m resolution). Strongly absorbed by chlorophyll $a$ and $b$ for photosynthesis.
- **Valid Numerical Bounds**: Strict mathematical range $[-1.0, 1.0]$. Values outside this boundary indicate corrupted sensors or invalid atmospheric corrections and are rejected.

### Processing Baseline 04.00 Radiometric Offset Note
Beginning 25 January 2022 (ESA Processing Baseline 04.00+), Sentinel-2 L2A surface reflectance digital numbers ($\text{DN}$) incorporate an offset of $+1000$ to avoid negative numbers in dark surfaces ($\text{DN} = 10000 \cdot \rho + 1000$).
- **Conversion Equation**:
  $$\rho = \frac{\text{DN} + \text{BOA\_ADD\_OFFSET}}{10000.0}$$
  where $\text{BOA\_ADD\_OFFSET} = -1000.0$ for processing baseline $\ge 04.00$, and $0.0$ for baseline $< 04.00$.
- **Provider Implementation**: `PlanetaryComputerProvider` reads `raster:bands` metadata or `s2:processing_baseline` per scene to determine the offset. Raw DN == 0 is masked as nodata before offset application, and pixels where corrected NIR + Red $\le 0$ are masked out before NDVI ratio computation.

### Cloud & Shadow Masking (Scene Classification Layer - SCL)
Sentinel-2 Level-2A data includes an algorithmic Scene Classification Layer (SCL) at 20m resolution:
- Excluded: `0` (NO_DATA), `1` (SATURATED_OR_DEFECTIVE), `3` (CLOUD_SHADOWS), `8` (CLOUD_MEDIUM_PROBABILITY), `9` (CLOUD_HIGH_PROBABILITY), `10` (THIN_CIRRUS), `11` (SNOW_ICE).
- Included: `2` (DARK_AREA_PIXELS), `4` (VEGETATION), `5` (NOT_VEGETATED/Soil), `6` (WATER), `7` (UNCLASSIFIED).

---

## 3. Daily Precipitation & Deficit Formulation (T-03)

### NASA POWER Agroclimatology
- **Endpoint**: `https://power.larc.nasa.gov/api/temporal/daily/point`
- **Parameter**: `PRECTOTCORR` (Precipitation Corrected, mm/day). Bias-corrected satellite-model reanalysis from MERRA-2.
- **Community**: `AG` (Agroclimatology).
- **Missing Value Sentinel**: `-999.0` (mapped to `None`, flagged `is_valid=False`, never imputed with zero).
- **Spatial Resolution**: $0.5^\circ \times 0.5^\circ$ global grid (~55 km).

### Seasonal Rainfall Metrics & Baseline Normal
- **Normal Rabi Baseline**: $19.5\text{ mm}$ for Anand/Kheda district across the Rabi window (Nov 1 to Apr 15). Derived from IMD 30-year district climate normals (1981–2010). Winter precipitation in central Gujarat is sparse and driven by occasional western disturbances.
- **Deficit Percentage**:
  $$\text{rain\_deficit\_pct} = \frac{\text{rain\_total\_mm} - \text{baseline\_mm}}{\text{baseline\_mm}} \times 100$$
  A negative value (e.g. $-45.0\%$) denotes rainfall deficit; a positive value (e.g. $+25.0\%$) denotes surplus.
- **Early Season Window (`rain_early_mm`)**: First 6 weeks (42 days) from season start (Nov 1 to Dec 13).
- **Monthly Breakdown**: Retained as separate fields (`rain_nov_mm`, `rain_dec_mm`, `rain_jan_mm`, `rain_feb_mm`, `rain_mar_mm`, `rain_apr_mm`) to prevent temporal data leakage in downstream modeling.
- **Data Gap Rule**: Flagged `data_gap=True` if valid observation ratio $< 90\%$ or if days are unobserved.

---

## 4. APMC Mandi Price & Volatility Formulation (T-03)

### Sources & Authentication
- **CEDA API**: Center for Economic Data and Analysis (Ashoka University) / Agmarknet daily price portal. Authenticated via `CEDA_API_KEY` HTTP header.
- **Manual CSV Fallback**: Historical weekly/bi-weekly trading day records for Anand APMC and Umreth APMC (`data/external/mandi_prices_wheat.csv`).

### Price Aggregation & Volatility
- **Multi-Market District Aggregation**: On calendar days where multiple APMCs report in Anand district, the daily district price is computed as the arithmetic mean of market modal prices.
- **Price Volatility (Sample Coefficient of Variation, CV)**:
  $$\text{CV} = \frac{s}{\bar{x}} = \frac{\sqrt{\frac{1}{N-1}\sum_{i=1}^N (x_i - \bar{x})^2}}{\bar{x}}$$
  Where $x_i$ is the daily district modal price and $\bar{x}$ is the seasonal mean.
- **Data Gap Rule**: Flagged `data_gap=True` if fewer than 10 reporting days exist across the season or if no markets reported.

### CRITICAL DOMAIN NOTICE: DATA LEAKAGE PREVENTION
> [!WARNING]
> Wheat harvest modal prices realized in March/April represent seasonal **outcomes**, determined by total regional harvest volume and macroeconomic conditions. They are **NOT** available during November sowing or December vegetative growth.
> Downstream tasks (**T-04 Feature Engineering** and **T-05 ML/Credit Assessment**) MUST NOT leak post-sowing mandi prices into early-warning or loan underwriting models. The monthly price breakdown allows features to strictly isolate sowing-time prices (`price_nov`, `price_dec`) from harvest outcomes (`price_mar`, `price_apr`).

---

## 5. Administrative District Crop Yield Statistics (T-03)

- **Source File**: `data/external/district_yield_wheat.csv`
- **Data Origin**: Directorate of Agriculture, Government of Gujarat (`https://dag.gujarat.gov.in`) and Directorate of Economics & Statistics, Ministry of Agriculture & Farmers Welfare (`https://desagri.gov.in`).
- **Validation Rules**:
  1. Required schema: `district,season,area_ha,production_tonnes,yield_kg_per_ha,source_name,source_url,retrieved_on`.
  2. Strict positive bounds: `area_ha > 0`, `production_tonnes > 0`, `yield_kg_per_ha > 0`.
  3. Plausibility bounds: $500 \le \text{yield\_kg\_per\_ha} \le 6000\text{ kg/ha}$.
  4. Mathematical consistency:
     $$\left|\text{yield\_kg\_per\_ha} - \frac{\text{production\_tonnes} \times 1000}{\text{area\_ha}}\right| \Big/ \left(\frac{\text{production\_tonnes} \times 1000}{\text{area\_ha}}\right) \le 0.01\quad (1\%)$$

### IMPORTANT STATISTICAL LIMITATION
> [!NOTE]
> District yield represents an **administrative aggregate average** across ~50,000 hectares in Anand district. It CANNOT capture within-district spatial microclimates, farm-specific soil fertility, or individual farmer management practices. It serves strictly as a macro-regional productivity benchmark.

---

## 6. Multi-Source Dataset Join Schema (`season_dataset.csv`)

The multi-source join in `scripts/build_dataset.py` uses `(plot_code, season)` as primary key with a deterministic Left Join from the NDVI skeleton table:

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `plot_code` | String (PK) | Unique plot identifier (e.g. `ANAND_WHEAT_01`) |
| `season` | String (PK) | Rabi cropping season (e.g. `2023-24`) |
| `district` | String | Administrative district (`Anand`) |
| `crop` | String | Commodity (`wheat`) |
| `lat`, `lon` | Float | Centroid geographic coordinates |
| `buffer_m` | Float | Radius around centroid in meters (e.g. 50.0m) |
| `irrigation` | String | Irrigation source (`tube_well`, `canal`, `rainfed`) |
| `insured` | Integer | PMFBY insurance coverage status (0 or 1) |
| `ndvi_mean`, `ndvi_peak`, `ndvi_std`, `ndvi_early` | Float | Seasonal Sentinel-2 NDVI statistics |
| `ndvi_valid_obs_count`, `ndvi_source` | Int / String | Clear observation count and data source |
| `rain_total_mm`, `rain_early_mm` | Float | Seasonal and first 6-week cumulative rainfall |
| `rain_nov_mm` to `rain_apr_mm` | Float | Month-by-month rainfall breakdown |
| `rain_deficit_pct` | Float | Deviation from 30-year IMD normal |
| `rain_valid_days_count`, `rain_source` | Int / String | Reporting days count and rainfall source |
| `price_mean`, `price_volatility` | Float | Mean modal price (₹/qtl) and Coefficient of Variation |
| `price_nov` to `price_apr` | Float | Month-by-month mandi price breakdown |
| `price_market_count`, `price_source` | Int / String | Reporting APMC market count and source |
| `yield_kg_per_ha`, `yield_area_ha` | Float | District administrative yield and reported acreage |
| `yield_production_tonnes`, `yield_source` | Float / String | District production and data source |
| `data_gap_ndvi`, `data_gap_rainfall` | Boolean | Individual source gap flags |
| `data_gap_price`, `data_gap_yield` | Boolean | Individual source gap flags |
| `data_gap_any` | Boolean | Combined data gap indicator |
| `completeness_note` | String | Audit note detailing missing modalities or 'complete' |

---

## 7. How to Execute Pipeline Targets

### Using Make:
```bash
make fetch-ndvi      # Fetch satellite NDVI observations
make fetch-rainfall  # Fetch daily precipitation time-series
make fetch-prices    # Fetch APMC mandi price series
make build-dataset   # Assemble multi-source joined dataset
```

### Using PowerShell directly on Windows:
```powershell
.venv\Scripts\python.exe scripts/fetch_ndvi.py --provider fixture
.venv\Scripts\python.exe scripts/fetch_rainfall.py --provider fixture
.venv\Scripts\python.exe scripts/fetch_prices.py --provider manual_csv
.venv\Scripts\python.exe scripts/build_dataset.py
```

### Dry Run Validation:
```powershell
.venv\Scripts\python.exe scripts/fetch_rainfall.py --dry-run
.venv\Scripts\python.exe scripts/fetch_prices.py --dry-run
```
