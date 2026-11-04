# SatBhoomi Score + Raksha — Step 3 Prerequisites & Context (Task T-02)

This document establishes the operational parameters, geographic scope, crop calendar, and data provider configuration for **Task T-02 (Satellite NDVI Connector)**.

---

## 1. Project Context & Agricultural Parameters

- **Target Crop**: Wheat (*Triticum aestivum*)
- **Target Season**: Rabi season
- **Seasonal Window**: **November 1 to April 15** (Sowing: ~November to December; Vegetative/Heading: ~January to February; Harvesting: ~March to April)
- **Target Seasons**: Last 5 completed Rabi seasons:
  1. `2020-21` (2020-11-01 to 2021-04-15)
  2. `2021-22` (2021-11-01 to 2022-04-15)
  3. `2022-23` (2022-11-01 to 2023-04-15)
  4. `2023-24` (2023-11-01 to 2024-04-15)
  5. `2024-25` (2024-11-01 to 2025-04-15)
- **District / State**: Anand, Gujarat (Reference agricultural district for wheat pilot; configurable per plot in `sample_plots.csv`).
- **Season Naming Standard**: Format `YYYY-YY` (e.g., `2021-22`), matching across data connectors, relational schema, and feature engineering.

---

## 2. Sample Plot Centroid Methodology & Caveats

- **Plot Representations**: Points in `data/synthetic/sample_plots.csv` represent **sample plot centroids** (field centres identified visually via satellite imagery/Google Maps), paired with a circular buffer radius in meters (`buffer_m`, e.g. 30m–100m).
- **Core Caveats & Limitations**:
  1. **Not Real Farmers**: Coordinates and farmer names are strictly synthetic demonstration samples. No real agricultural lending records or personally identifiable farmer data are present.
  2. **Buffer Approximation**: Circular buffers around centroid points do not represent true cadastral plot boundaries and may intersect field edges, irrigation channels, or tree lines (mixed pixel effect).
  3. **Cloud Gaps**: Monsoonal/winter cloud cover may create observational gaps. Gaps are explicitly marked with `data_gap=True` rather than imputed silently.

---

## 3. Earth Engine & Provider Status

- **`GEE_PROJECT` Status**: Unset / Pending in environment (`[bool]$env:GEE_PROJECT` = `False`).
- **Architectural Routing**:
  - `PlanetaryComputerProvider`: Primary live/network provider implemented via Microsoft Planetary Computer STAC API (Sentinel-2 L2A).
  - `FixtureProvider`: Fully offline provider reading synthetic observation records for deterministic unit tests and GitHub Actions CI without network access.
  - `GeeProvider`: Documented stub waiting for active Earth Engine project ID and authentication.

---

## 4. Environment & Tooling Alignment

- **Local Host**: Windows with PowerShell (`D:\SatBhoomi`).
- **Local Python Environment**: Python 3.13.5 virtualenv (`.venv`).
- **CI Environment**: GitHub Actions runner on Ubuntu with Python 3.11.
- **Rule**: Code must be strictly compatible with both Python 3.11 and Python 3.13 without deprecation warnings.
