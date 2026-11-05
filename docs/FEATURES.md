# SatBhoomi In-Season Feature Engineering Specification (T-04)

**Status**: APPROVED  
**Date**: November 2026  
**Crop & Season**: Wheat (*Triticum aestivum*), Rabi Season (November 1 to April 15)  
**Geography**: Anand District, Gujarat, India  
**Target Cut-Off Date**: **January 31** (23:59:59 local time)  

---

## 1. Overview and Design Principles

SatBhoomi Score + Raksha provides pre-harvest credit risk assessments and in-season early warnings to bank loan officers evaluating smallholder farmers. 

To eliminate **look-ahead temporal leakage** and ensure the underwriting score uses strictly information that was knowable at the time of interim credit review, all feature inputs are subject to an immutable **January 31 in-season cut-off barrier**.

```
Sowing & Germination     Vegetative Development        Heading & Flowering Peak      Maturity & Harvest
[Nov 1 ----------------- Dec 15 ----------------- Jan 31] || [Feb 1 ----------------- Mar 15 ---------- Apr 15]
<---------------- PRE-CUTOFF FEATURES -----------------> || <------------ OUTCOME PROXY LABEL ------------->
```

---

## 2. Feature Inventory

The 12 approved features in [`src/satbhoomi/features/config.py`](file:///d:/SatBhoomi/src/satbhoomi/features/config.py) are cataloged below:

| # | Feature Name | Category | Primary Source | Formal Computation Rule | Why Available $\le$ Jan 31 |
| :-: | :--- | :--- | :--- | :--- | :--- |
| **1** | `ndvi_early` | Satellite | Sentinel-2 L2A (S2) | Mean NDVI of valid cloud-free pixels over plot buffer during the first 6 weeks of the season ($\text{Nov } 1 \le t \le \text{Dec } 13$). If 0 valid scenes exist due to persistent early cloud cover, preserved as `None` without imputation. | Measurement period concludes on December 13 (Day 42), well before the January 31 cut-off. |
| **2** | `ndvi_pre_cutoff_mean` | Satellite | Sentinel-2 L2A (S2) | Arithmetic mean of valid cloud-free NDVI observations between November 1 and January 31. | Evaluates optical scenes acquired strictly on or before January 31. |
| **3** | `ndvi_pre_cutoff_std` | Satellite | Sentinel-2 L2A (S2) | Sample standard deviation ($s$, ddof=1) of valid NDVI observations between November 1 and January 31 (0.0 if single observation). | Evaluates optical scenes acquired strictly on or before January 31. |
| **4** | `ndvi_trend_pre_cutoff`| Satellite | Sentinel-2 L2A (S2) | Ordinary Least Squares (OLS) linear slope ($\Delta\text{NDVI}/\Delta\text{days}$) of valid scenes from November 1 to January 31. Measures vegetative growth momentum. | Evaluates optical scenes acquired strictly on or before January 31. |
| **5** | `rain_pre_cutoff_total_mm`| Weather | NASA POWER (0.5° AG) | Sum of daily precipitation: $\sum \text{rain}_{\text{Nov}} + \sum \text{rain}_{\text{Dec}} + \sum \text{rain}_{\text{Jan}}$. | Weather observations recorded on or before January 31. |
| **6** | `rain_pre_cutoff_deficit_pct`| Weather | NASA POWER | Percentage departure from Anand district long-term 30-year normal rainfall for the Nov–Jan period ($10.5\text{ mm}$):<br>$\frac{\text{Rain}_{\le\text{Jan}} - 10.5}{10.5} \times 100\%$. | Normal baseline is derived from historical IMD climatology; observed rain is pre-cutoff. |
| **7** | `mandi_pre_cutoff_volatility`| Commodity | AGMARKNET / CEDA | Sample Coefficient of Variation ($\text{CV} = s / \bar{x}$) of weekly modal wheat APMC prices for November, December, and January. | Measures pre-harvest sowing/vegetative market price volatility before harvest arrivals. |
| **8** | `past_stressed_seasons_count`| Track Record| Proxy Label History | Cumulative count of strictly prior completed Rabi seasons ($k < t$) where the plot was categorized as stressed ($Y = 1$). Set to 0 for Season 1 (`2020-21`). | Uses only completed historical seasons preceding the active year. |
| **9** | `prev_season_ndvi_peak`| Track Record| Sentinel-2 History | Outcome peak NDVI ($\text{NDVI}_{\text{peak}}$) of the immediately preceding completed season ($t-1$). Set to `None` for Season 1 (`2020-21`). | Historical outcome concluded in April of the previous year. |
| **10**| `area_acre` | Field Static | Sample Plot Registry | Plot landholding size in acres (derived from centroid buffer radius: $\pi \cdot r^2 / 4046.86$). | Static property recorded at loan origination. |
| **11**| `irrigation` | Field Static | Sample Plot Registry | Categorical source of water supply (`tube_well`, `canal`, `rainfed`). | Static property recorded at loan origination. |
| **12**| `insured` | Field Static | Sample Plot Registry | Binary indicator (1 if covered under Pradhan Mantri Fasal Bima Yojana (PMFBY), 0 otherwise). | Policy enrolled at or prior to sowing (November). |

---

## 3. Strict Look-Ahead Leakage Quarantine

To eliminate circular reasoning and artificial model accuracy, the following variables are **strictly excluded** from the feature engineering pipeline:

1. **`ndvi_peak` (current season)**: The primary input to the ground-truth proxy label formula.
2. **`ndvi_mean` & `ndvi_std` (full season)**: Integrates late-season observations from February, March, and April (heading, flowering, senescence, and harvest).
3. **`rain_feb_mm`, `rain_mar_mm`, `rain_apr_mm`, and `rain_total_mm`**: Terminal seasonal rainfall occurring after January 31.
4. **`price_feb`, `price_mar`, `price_apr`, and full-season `price_mean` / `price_volatility`**: Captures peak harvest market price gluts, arrival crashes, or procurement dynamics.
5. **`yield_kg_per_ha`, `yield_area_ha`, `yield_production_tonnes`**: Official district crop-cutting statistics published 3 to 6 months after harvest.

### Leakage Verification via Truncation Test
Our test suite implements an automated **Truncation Test** (`test_truncation_test_guarantees_zero_temporal_leakage` in [`tests/unit/test_features.py`](file:///d:/SatBhoomi/tests/unit/test_features.py)). 

The test corrupts all post-January 31 data (assigning sentinel values of 9,999.0 to February–April rain, prices, and yields) and verifies that every computed feature value remains **bit-for-bit identical** to the uncorrupted output. If any feature changes, the test fails immediately.

---

## 4. Methodological and Operational Caveats

1. **Assigned Attributes**:
   `area_acre`, `irrigation`, and `insured` are assigned experimental properties in `data/synthetic/sample_plots.csv`, not certified revenue records. Any feature attributions (e.g. SHAP values) in subsequent modeling are illustrative demonstrations of system capability.
2. **Missing Input Policy**:
   If satellite scenes are cloudy during a pre-cutoff window, the corresponding metrics (e.g., `ndvi_early`) remain `None` / `NaN` with explicit data gap tracking. Values are **never** silently zero-filled or imputed.
3. **Common Sensor Basis**:
   Because both pre-cutoff vegetative features (`ndvi_early`, `ndvi_trend_pre_cutoff`) and the outcome label are derived from Sentinel-2 optical imagery, enforcing the January 31 cut-off barrier is the primary technical defense against target leakage.
