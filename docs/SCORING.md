# SatBhoomi In-Season Risk Scoring and Explanation Specification (T-06)

**Status**: CURRENT  
**Date**: 2026-11-14  
**Active Scorer**: `rules_baseline` (`satbhoomi-rules-v2.0-relative-20261114`)  
**Configuration**: Single Source of Truth in [`src/satbhoomi/risk/config.py`](file:///d:/SatBhoomi/src/satbhoomi/risk/config.py)  
**Governing Document**: [`docs/SCORER_REVIEW.md`](file:///d:/SatBhoomi/docs/SCORER_REVIEW.md) (Approved 2026-11-14)  
**Reference Report**: `reports/scores_summary.json`  
**Cut-Off Date**: January 31 (in-season interim review, strictly unshifted)

---

## 1. Governance & Protocol Context

In accordance with Architecture Decision ADR-2 (*Rules baseline first, ML second*) and the approved review (`docs/SCORER_REVIEW.md`), the **active scorer is `rules_baseline` (`AgronomicRulesBaseline` v2.0)**. 

Under Evaluation Protocol v2 (`docs/EVAL_PROTOCOL.md`), the Feasibility Gate fails ($n = 4$ pooled positives vs 10 required) $\implies$ machine learning model training remains strictly frozen. The rules baseline operates as a transparent, deterministic decision-support tool.

Every `RiskScoreResult` includes the fixed `reliability_note`:  
*"Descriptive heuristic rules baseline evaluated on Sentinel-2 offset-corrected data. Under Evaluation Protocol v2, machine learning evaluation remains frozen under the Feasibility Gate (feasibility gate failed; status: NOT EVALUABLE)."*

---

## 2. Score Definition & Rules Baseline v2.0 Logic

- **Formula**: $\text{score} = \text{round}(\hat{p} \times 100)$, clamped to $[0, 100]$.
- **Meaning**: An **in-season farm stress risk estimate as of the January 31 cut-off date**, evaluated against the plot's own strictly prior historical baseline.
- **Principles Implemented (ADR-12)**:
  1. **Relative Vegetative Anomaly**: Evaluates current `ndvi_pre_cutoff_mean` against the plot's historical expanding baseline from strictly prior completed seasons:
     $$\text{drop\_pct} = \frac{\text{baseline} - \text{current}}{\text{baseline}} \times 100.0$$
     - Moderate drop: $\ge 15.0\%$ ($\approx 2.0 \times \text{MAD}$ natural variability)
     - Acute drop: $\ge 25.0\%$ ($> 3.0 \times \text{MAD}$, canopy collapse)
  2. **Differentiated Rainfall Treatment**: Normal winter rainfall in Anand is only 10.5 mm and wheat is $>85\%$ irrigated. Winter rainfall deficits are buffered on irrigated tracts and act as a stress driver only on rainfed plots (`irrigation == 'rainfed'`).
  3. **Strict Baseline Depth Gate**: Season 1 (`2020-21`) or plots with 0 prior seasons strictly return `status = "insufficient_data"`. No scores or loan limits are ever invented.

---

## 3. Risk Band Thresholds & Recomputed Distribution

Single-source thresholds defined in [`src/satbhoomi/risk/config.py`](file:///d:/SatBhoomi/src/satbhoomi/risk/config.py):

| Band | Score Range | Assigned Probability $\hat{p}$ | Agronomic Definition |
| :--- | :---: | :---: | :--- |
| **`low`** | `0 – 34` | $0.10 \rightarrow \text{score } 10$ | Normal vegetative progression (drop $< 15.0\%$) and no unbuffered moisture deficit. |
| **`medium`** | `35 – 69` | $0.45 \rightarrow \text{score } 45$ | Moderate vegetative lag ($15.0\% \le \text{drop} < 25.0\%$) OR severe rain deficit on rainfed plots ($\le -25.0\%$). |
| **`high`** | `70 – 100` | $0.85 \rightarrow \text{score } 85$ | Acute vegetative collapse ($\ge 25.0\%$) OR compound distress (moderate lag + rainfed moisture failure). |

### Current Empirical Distribution (`reports/scores_summary.json`)

Scoring all **105** active plot-seasons (21 active plots across 5 seasons) on corrected Sentinel-2 data yields:

- **Total Active Plot-Seasons**: 105
- **`insufficient_data` (Season 1 `2020-21`)**: 21 rows (100% of Season 1 cleanly gated)
- **Total Evaluable Plot-Seasons (Seasons 2–5)**: 84 rows
  - **`low` (`0–34`, score 10)**: 73 rows (86.9%)
  - **`medium` (`35–69`, score 45)**: 9 rows (10.7%)
  - **`high` (`70–100`, score 85)**: 2 rows (2.4%)

#### Season-by-Season Census:

| Season | Insufficient Data | Low (Score 10) | Medium (Score 45) | High (Score 85) | Total |
| :---: | :---: | :---: | :---: | :---: | :---: |
| **2020-21** | 21 | 0 | 0 | 0 | 21 |
| **2021-22** | 0 | 15 | 5 | 1 | 21 |
| **2022-23** | 0 | 20 | 1 | 0 | 21 |
| **2023-24** | 0 | 21 | 0 | 0 | 21 |
| **2024-25** | 0 | 17 | 3 | 1 | 21 |
| **Total** | **21** | **73** | **9** | **2** | **105** |

#### Resolution of Permanent Flagging:
Under the pre-correction absolute rule (`ndvi_early <= 0.35`), 6 plots were flagged in 5/5 seasons. Under the relative rule:
- Flagged in 4 seasons: **0 plots**
- Flagged in 3 seasons: **0 plots**
- Flagged in 2 seasons: **1 plot** (`ANAND_WHEAT_05`)
- Flagged in 1 season: **9 plots**
- Flagged in 0 seasons: **11 plots**

---

### SUPERSEDED: Pre-Correction Distribution (Historical Reference Only)
> [!NOTE]
> The earlier distribution below was evaluated against uncorrected satellite data and is **SUPERSEDED**:
> - Low: 0 rows
> - Medium: 60 rows (all scored 45 due to constant cached NDVI)
> - High: 0 rows

---

## 4. Explanation Method (Exact Additive Contributions)

No external `shap` dependency is required:
1. **Active Scorer (`rules_baseline` v2.0)**: Exact additive decomposition in **probability space** (`base_value = 0.10`):
   - Normal growth: `0.10 + 0.0 = 0.10`
   - Moderate vegetative lag: `0.10 + 0.35 = 0.45`
   - Rainfed moisture deficit: `0.10 + 0.35 = 0.45`
   - Acute vegetative collapse: `0.10 + 0.75 = 0.85`
   - Compound distress (moderate lag + rainfed deficit): `0.10 + 0.375 + 0.375 = 0.85`
   - In every case: $\text{base\_value} + \sum \text{contributions} == \hat{p}$ (exact mathematical additivity verified by automated unit tests).

2. **Logistic Regression (`logreg`, synthetic multi-class test path only)**: Exact linear contributions $\text{coef}_j \cdot x_{\text{scaled}, j}$ in **log-odds space**.

In both modes, missing features are skipped, the top 3 risk-increasing contributors are selected deterministically, and the top protective factor is reported separately when present. Zero blame language is strictly enforced.

---

## 5. Plain-Language Reason Templates

Defined in [`src/satbhoomi/risk/reason_templates.py`](file:///D:/SatBhoomi/src/satbhoomi/risk/reason_templates.py) for all 12 features in `FEATURE_COLUMNS`:

1. `ndvi_early`: Early-season vegetation greenness (NDVI) compared with prior peak when available.
2. `ndvi_pre_cutoff_mean`: Average vegetation greenness (NDVI) up to January 31.
3. `ndvi_pre_cutoff_std`: Vegetation greenness standard deviation before January 31.
4. `ndvi_trend_pre_cutoff`: Crop canopy growth slope ($\Delta\text{NDVI}/\Delta\text{day}$) up to January 31.
5. `rain_pre_cutoff_total_mm`: Cumulative rainfall (mm) up to January 31.
6. `rain_pre_cutoff_deficit_pct`: Percentage departure from 30-year normal rainfall.
7. `mandi_pre_cutoff_volatility`: Pre-cutoff mandi wheat price coefficient of variation.
8. `past_stressed_seasons_count`: Count of prior stressed seasons in history.
9. `prev_season_ndvi_peak`: Previous season peak NDVI.
10. `area_acre`: Plot area in acres — explicitly phrased **"as recorded by the officer"**.
11. `irrigation`: Irrigation source — explicitly phrased **"as recorded by the officer"**.
12. `insured`: Crop insurance enrollment indicator — explicitly phrased **"as recorded by the officer"**.

All templates use `"farm stress"`, `"repayment stress"`, and `"support needed"`, contain only numbers present in the input row, and never reference psychological/mental states or blame.

---

## 6. Missing-Data / Insufficient-Data Rule

- **Never invent values**: Missing inputs are never filled with defaults for explanation.
- **Tolerance Limit (`MAX_MISSING_FEATURES_ALLOWED = 2`)**:
  - **$\le 2$ missing features** (and at least one core in-season signal present): Returns `status = "ok"`, score, band, 3 reasons (skipping missing features), and `data_warnings` listing every missing feature.
  - **$> 2$ missing features** OR **all 5 core in-season signals missing** (`ndvi_early`, `ndvi_pre_cutoff_mean`, `ndvi_trend_pre_cutoff`, `rain_pre_cutoff_total_mm`, `rain_pre_cutoff_deficit_pct`): Returns `status = "insufficient_data"`, `score = None`, `band = None`, `reasons = []`, and `insufficient_data_reason`, while still returning `scorer`, `model_version`, `data_warnings`, `interpretation`, and `reliability_note`.

---

## 7. Honest Limitations & Open Question

1. **In-Season Score vs. Pre-Sowing Approval (OPEN QUESTION)**:  
   This score is an **in-season farm stress estimate as of January 31**, not a pre-sowing loan origination score. A true **pre-sowing assessment** (at November sowing) cannot observe current-season NDVI or winter rainfall; it would instead require multi-year historical plot yield/NDVI resilience, verified irrigation/soil/water-table status, seasonal monsoon/reservoir outlook, and borrower repayment history. **OPEN QUESTION for the team** (logged in [`docs/RISKS.md`](file:///D:/SatBhoomi/docs/RISKS.md)): *Should pre-sowing underwriting rely strictly on multi-year historical baseline resilience + officer-verified assets, while reserving SatBhoomi's satellite score strictly for in-season monitoring and top-up/restructuring?*
2. **Zero Stressed Labels & Unvalidated Scoring**: Neither the rules baseline nor ML models have been empirically validated against stressed or default outcomes on this sample.
3. **Proxy Label & Small Sample**: Labels are a satellite NDVI proxy across 12 sample plots in one district, not real bank loan defaults.
4. **Assigned Attributes**: `area_acre`, `irrigation`, and `insured` are officer-assigned sample attributes, not field-verified observations.
5. **Non-Causal Explanations**: Additive contributions describe how the heuristic or model produced the score, **not** agronomic causation.

