# SatBhoomi — Read-Only Data Revisit Analysis (Post T-06)

**Status:** COMPLETE (Read-Only Analysis)  
**Analysis Script:** [revisit_data.py](file:///d:/SatBhoomi/scripts/analysis/revisit_data.py)  
**Smoke Test:** [test_revisit_data.py](file:///d:/SatBhoomi/tests/unit/test_revisit_data.py)  
**Known Bad Events Reported by User:** None reported (`2020-21` to `2024-25`).

> [!IMPORTANT]
> **Root Cause Summary:** Every valid Sentinel-2 observation across all 60 `ANAND_WHEAT_*` plot-seasons in `data/raw/satellite/*.json` has a **hardcoded placeholder `ndvi = 0.65`** (`0.20` when cloudy), because [PlanetarySatelliteProvider.fetch_observations](file:///d:/SatBhoomi/src/satbhoomi/connectors/satellite/planetary_provider.py#L104-L152) queries STAC scene metadata (`eo:cloud_cover`) without reading actual `B04`/`B08`/`SCL` raster pixels. Consequently, `ndvi_peak = 0.65` and `peak_drop_pct = 0.0%` for all 48 labelled rows, making `stressed = 1` mathematically impossible under any positive drop threshold.

---

## 1. Coverage

| Metric | Value |
| :--- | :--- |
| Plots (`plot_code`) | `12` (`ANAND_WHEAT_01` – `ANAND_WHEAT_12`) |
| Distinct `(lat, lon)` Locations | `12` (all in Anand district, `wheat`) |
| Seasons | `5` (`2020-21`, `2021-22`, `2022-23`, `2023-24`, `2024-25`) |
| Total Rows (`features.csv`) | `60` |
| Labelled Rows (`label_unavailable == False`) | `48` (`0` stressed, `48` not-stressed) |
| Unlabelled Rows (`label_unavailable == True`) | `12` (`2020-21` baseline season) |
| Dataset-level Data-Gap Rates (`season_dataset.csv`) | `0.0` across `data_gap_ndvi`, `data_gap_rainfall`, `data_gap_price`, `data_gap_yield`, `data_gap_any` |
| Raw Satellite Valid-Observation Ratio (`is_valid == True` / 100 scenes) | Min `0.8108`, Median `0.9315`, Max `1.0000` |
| Pairwise Plot Centroid Distances (`66` pairs) | Min `2.2621 km`, Median `24.4280 km`, Max `68.4282 km` |
| Plot Pairs Within `10 m` / `100 m` / `1 km` | `0` / `0` / `0` (`0` plots have a neighbor within `1 km`) |

---

## 2. Crop-Cycle Check

- **Total plot-seasons inspected in `data/raw/satellite/`:** `60` (`0` missing raw JSONs).
- **Flagged `flat_curve` (`ndvi_peak - ndvi_min < 0.05` or `ndvi_std < 0.02`):** **`60 / 60` (`100%`)**.
- **Observed valid NDVI across all 60 files:** `ndvi_min = 0.65`, `ndvi_peak = 0.65`, `ndvi_std = 0.0` (no rise-peak-fall phenology curve exists in any `ANAND_WHEAT_*` file; `argmax` simply picks the first valid scene date).
- **Low-peak (`< 0.35`) curves:** `0 / 60`.

---

## 3. Natural Variability

Distribution of `peak_drop_pct` (the label quantity) across the `48` labelled plot-seasons:

| Scope | Count | Min | 25th Pct | Median | 75th Pct | Max |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Overall (`2021-22`–`2024-25`)** | `48` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` |
| `2021-22` | `12` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` |
| `2022-23` | `12` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` |
| `2023-24` | `12` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` |
| `2024-25` | `12` | `0.0%` | `0.0%` | `0.0%` | `0.0%` | `0.0%` |

---

## 4. Why Zero Positives

1. The label rule in `LABEL_RULE.md` marks `stressed = 1` when `peak_drop_pct >= 15.0%` relative to the plot's expanding prior-season `historical_baseline_ndvi`.
2. Because every `ANAND_WHEAT_*` plot-season has `ndvi_peak = 0.65`, `historical_baseline_ndvi = 0.65` and `peak_drop_pct = 0.0%` for all `48` labelled rows.
3. The maximum observed drop is **`0.0%`**, leaving a **`15.0` percentage-point gap** to the threshold. Adjusting the threshold would not help: no positive drop exists anywhere in the cached satellite data.

---

## 5. External Check (District Yield, Rainfall, and Mandi Prices)

| Season | Area (ha) | Production (t) | District Yield (kg/ha) | YoY Yield Change | Yield vs 5-Yr Mean (`3,436.0`) | Mean Rain Total (mm) | Mean Rain Deficit (%) | Mean Price (₹/qtl) | Price Volatility (CV) | Mean Plot `ndvi_peak` |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `2020-21` | `48,200` | `168,700` | `3,500` | `—` | `+1.86%` | `140.66` | `+621.33%` | `2,004.36` | `0.0114` | `0.65` |
| `2021-22` | `51,400` | `174,760` | `3,400` | `-2.86%` | `-1.05%` | `138.41` | `+609.79%` | `2,114.36` | `0.0108` | `0.65` |
| `2022-23` | `49,600` | `161,200` | `3,250` | `-4.41%` | `-5.41%` | `135.58` | `+595.26%` | `2,234.36` | `0.0102` | `0.65` |
| `2023-24` | `52,100` | `184,955` | `3,550` | `+9.23%` | `+3.32%` | `141.86` | `+627.48%` | `2,364.36` | `0.0096` | `0.65` |
| `2024-25` | `50,800` | `176,784` | `3,480` | `-1.97%` | `+1.28%` | `123.73` | `+534.49%` | `2,494.36` | `0.0091` | `0.65` |

District wheat yield varied modestly (`3,250` to `3,550 kg/ha`, `-5.41%` dip in `2022-23`), while plot `ndvi_peak` remained frozen at `0.65`.

---

## 6. Feature Quality (`FEATURE_COLUMNS`, `n = 60`)

| Feature | Missing (`n`, `%`) | Unique Non-Null | Constant? | Min | Median | Max |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `ndvi_early` | `14` (`23.33%`) | `1` | **Yes** (`0.65`) | `0.65` | `0.65` | `0.65` |
| `ndvi_pre_cutoff_mean` | `0` (`0.0%`) | `1` | **Yes** (`0.65`) | `0.65` | `0.65` | `0.65` |
| `ndvi_pre_cutoff_std` | `0` (`0.0%`) | `1` | **Yes** (`0.0`) | `0.0` | `0.0` | `0.0` |
| `ndvi_trend_pre_cutoff` | `0` (`0.0%`) | `1` | **Yes** (`0.0`) | `0.0` | `0.0` | `0.0` |
| `rain_pre_cutoff_total_mm` | `0` (`0.0%`) | `58` | No | `22.0` | `74.35` | `123.4` |
| `rain_pre_cutoff_deficit_pct` | `0` (`0.0%`) | `58` | No | `+109.52` | `+608.10` | `+1075.24` |
| `mandi_pre_cutoff_volatility` | `0` (`0.0%`) | `5` | No (season-level) | `0.0049` | `0.0054` | `0.0061` |
| `past_stressed_seasons_count` | `0` (`0.0%`) | `1` | **Yes** (`0`) | `0.0` | `0.0` | `0.0` |
| `prev_season_ndvi_peak` | `12` (`20.0%`) | `1` | **Yes** (`0.65`) | `0.65` | `0.65` | `0.65` |
| `area_acre` | `0` (`0.0%`) | `4` | No (assigned) | `1.94` | `1.94` | `4.97` |
| `irrigation` | `0` (`0.0%`) | `2` | No (assigned) | `—` | `—` | `—` |
| `insured` | `0` (`0.0%`) | `2` | No (assigned) | `0.0` | `1.0` | `1.0` |

Feature-to-label correlations are undefined (`NaN`) because `stressed == 0.0` on all `48` labelled rows.

---

## 7. Data Issues Identified

1. **Hardcoded Placeholder NDVI in `PlanetarySatelliteProvider`:** All `60` `ANAND_WHEAT_*` satellite JSONs contain `0.65` for every valid scene and `0.20` for cloudy scenes instead of real Sentinel-2 `B04`/`B08`/`SCL` pixel values.
2. **Fixture Rainfall & Extreme Positive `rain_deficit_pct` (`+109.5%` to `+1075.2%`):** `season_dataset.csv` has `rain_source = fixture` with `123.7`–`141.9 mm` seasonal totals against a `19.5 mm` IMD normal, producing `+534%` to `+627%` surplus values rather than real Anand NASA POWER observations.
3. **`ndvi_early` Missingness (`23.33%`, `14 / 60` rows):** Plot-seasons with no valid scenes in the first 6 weeks (or affected by STAC `limit=100` truncation across overlapping tiles) have `NaN` `ndvi_early`.
4. **Assigned Static Plot Attributes:** `area_acre` (from `buffer_m`), `irrigation`, and `insured` come from `sample_plots.csv`, not observed farmer/land records.
5. **District-Level Granularity for Yield & Mandi:** `yield_kg_per_ha` and `mandi_pre_cutoff_volatility` are identical across all `12` plots within a season.
6. **Small Sample & Single-District Scope:** Only `12` plots in `1` district (`60` rows total, `48` labelled).

---

## 8. Recommendation

1. **Do NOT alter `LABEL_RULE.md` thresholds or retrain on the current `features.csv`.**
2. **Fix Satellite Ingestion First:** Implement real Sentinel-2 `B04`/`B08`/`SCL` pixel extraction (e.g., via `rasterio`/`odc-stac` on Planetary Computer COGs or `GEESatelliteProvider`) and re-ingest `data/raw/satellite/` for all plots (and consider expanding beyond 12 plots / 1 district to capture genuine stress events).
3. **Switch Rainfall Ingestion to Live `nasa_power`:** Replace `fixture` rainfall in `season_dataset.csv` with cached NASA POWER daily precipitation.
4. **Re-run T-04 → T-05 → T-06** once real NDVI curves and rainfall are ingested.

