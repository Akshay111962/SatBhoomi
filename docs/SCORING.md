# SatBhoomi In-Season Risk Scoring and Explanation Specification (T-06)

**Status**: IMPLEMENTED  
**Date**: November 2026  
**Active Scorer**: `rules_baseline` (`satbhoomi-rules-v1.0-agronomic-jan31`)  
**Cut-Off Date**: January 31 (in-season interim review)

---

## 1. Plain Statement of Empirical Finding (T-05 / T-06)

> **Critical Validation Limitation**:  
> All available training seasons (`2021-22`, `2022-23`, `2023-24`) and the held-out test season (`2024-25`) in `data/processed/features.csv` contained **zero stressed labels** (`0` stressed out of `48` labelled rows, because `ndvi_peak = 0.65` across all plots in the cached T-02 satellite file). Consequently, **ROC-AUC was not evaluable**, and **the ML models (`logreg`, `random_forest`, `xgboost`) could not be validated**.
>
> Per Architecture Decision ADR-2 (*Rules baseline first, ML second*) and project governance, the **active scorer for T-06 is `rules_baseline` (`AgronomicRulesBaseline`)**. The saved Logistic Regression artifact (`satbhoomi-risk-v1.0-logreg-feat1-opt1th15-f85e5949-20261105.joblib`) is **not** used for live scoring; its linear-contribution explainer was built and verified exclusively on synthetic multi-class fixtures.
>
> Every `RiskScoreResult` includes the fixed `reliability_note`:  
> *"Not validated: no stressed outcomes were available in the sample data, so this score has not been shown to predict crop stress."*

---

## 2. Score Definition

- **Formula**: $\text{score} = \text{round}(\hat{p} \times 100)$, clamped to $[0, 100]$.
- **Meaning**: An **in-season farm stress risk estimate as of the January 31 cut-off date**, computed from pre-cutoff satellite NDVI, rainfall, mandi price volatility, prior-season history, and officer-recorded plot attributes.
- **Not a Default Probability or Loan Decision**: The score is a model/heuristic estimate of proxy crop stress—not a measured probability of loan default, not a pre-sowing loan approval score, and never an automated approval or rejection. Every result includes the fixed `interpretation` field stating this explicitly.

---

## 3. Risk Band Thresholds (Single-Source Configuration)

Defined in one place in [`src/satbhoomi/risk/scoring.py`](file:///D:/SatBhoomi/src/satbhoomi/risk/scoring.py):

| Band | Score Range | Agronomic & Protocol Justification |
| :--- | :---: | :--- |
| **`low`** | `0 – 34` | Normal vegetative progression and adequate pre-cutoff moisture (`AgronomicRulesBaseline` normal tier $\hat{p} = 0.10 \rightarrow \text{score} = 10$; aligns with `EVAL_PROTOCOL.md` low-risk bucket `[0.00, 0.33)`). |
| **`medium`** | `35 – 69` | Partial stress—either vegetative lag (`ndvi_early <= 0.35` or `ndvi_trend_pre_cutoff <= 0.0`) OR pre-cutoff rainfall deficit (`<= -20.0%`) ($\hat{p} = 0.45 \rightarrow \text{score} = 45$; aligns with `[0.33, 0.67)`). |
| **`high`** | `70 – 100` | Compound stress—both vegetative lag AND pre-cutoff rainfall deficit ($\hat{p} = 0.85 \rightarrow \text{score} = 85$; aligns with `[0.67, 1.00]`). |

### Descriptive Distribution on Existing Dataset (`data/processed/features.csv`)
Scoring all **60** plot-seasons in `data/processed/features.csv` with the active `rules_baseline` scorer yields:
- **`low` (`0–34`)**: `0` rows
- **`medium` (`35–69`)**: `60` rows (all 60 rows score `45` because `ndvi_trend_pre_cutoff = 0.0` from constant cached NDVI `0.65`, triggering Condition 1)
- **`high` (`70–100`)**: `0` rows
- **`insufficient_data`**: `0` rows

*(Thresholds were fixed from agronomic reasoning prior to scoring and were not adjusted based on this distribution.)*

---

## 4. Explanation Method (Exact Additive Contributions)

No external `shap` dependency is required:
1. **Active Scorer (`rules_baseline`)**: Exact additive decomposition in **probability space** (`base_value = 0.10`):
   - Normal growth: `0.10 + 0.0 = 0.10`
   - Single condition (vegetative OR rainfall): `0.10 + 0.35 = 0.45`
   - Compound stress (both conditions): `0.10 + 0.375 + 0.375 = 0.85`
   - If both `ndvi_early <= 0.35` and `ndvi_trend_pre_cutoff <= 0.0` trigger Condition 1, the vegetative uplift is split equally between them.
2. **Logistic Regression (`logreg`, synthetic multi-class test path only)**: Exact linear contributions $\text{coef}_j \cdot x_{\text{scaled}, j}$ in **log-odds space**, with `intercept_` as `base_value` (one-hot `irrigation` columns summed into a single `irrigation` attribution).

In both modes, missing features are skipped from reasons, the top 3 risk-increasing contributors are selected deterministically (padded with observed contextual features when fewer than 3 terms are positive), and the top protective factor is reported separately when present.

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

