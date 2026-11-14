# SatBhoomi — Comprehensive Read-Only Audit of Proxy Stress Label

**Document**: `docs/LABEL_AUDIT.md`  
**Status**: COMPLETE (Read-Only Audit)  
**Date**: November 14, 2026  
**Scope**: Verification of the proxy default/crop stress label in `data/processed/features.csv`, rule history, input independence, trigger decomposition, baseline depth quality, natural variability, model evaluation status, and disaster declaration provenance.

---

## 1. Rule History & Protocol Compliance

### 1.1 Verbatim Code vs. Documented Rule

#### Code Implementation (`src/satbhoomi/features/label.py`, lines 104–106)
```python
curr_float = float(current_peak)
drop_pct = round(((baseline - curr_float) / baseline) * 100.0, 2)
is_stressed = 1 if drop_pct >= drop_threshold_pct else 0
```
where `drop_threshold_pct = 15.0` (default from `src/satbhoomi/features/config.py`).

#### Documented Specification (`docs/LABEL_RULE.md`, Section 1)
> *"A sample farm plot-season is designated as **stressed** ($Y = 1$) if its outcome peak Normalized Difference Vegetation Index ($\text{NDVI}_{\text{peak}}$) across the full reproductive window falls by $\ge 15\%$ below the plot's own historical baseline established from strictly preceding completed seasons (Option 1: Expanding Historical Baseline, minimum 1 prior season). Plot-seasons lacking historical observations (such as the initial historical baseline year) receive an explicit `label_unavailable` status and are strictly quarantined from model training and evaluation rather than being imputed or silently dropped."*

**Match Verification**: The mathematical calculation in `src/satbhoomi/features/label.py` strictly implements the text in `docs/LABEL_RULE.md` Section 1.

### 1.2 Git Lineage Trace (`git log --follow`)

#### `src/satbhoomi/features/label.py`
```
b7623c8 | Thu Nov 5 16:13:22 2026 +0530 | feat(features): implement in-season feature pipeline and expanding proxy label (T-04)
```
*Finding*: The label code has had **exactly 1 commit** since repository inception. The calculation logic has never been modified.

#### `docs/LABEL_RULE.md`
```
78f6363 | Fri Nov 13 11:00:54 2026 +0530 | feat: complete live planetary & nasa power data ingestion and benchmark evaluation
b7623c8 | Thu Nov 5 16:13:22 2026 +0530 | feat(features): implement in-season feature pipeline and expanding proxy label (T-04)
```

### 1.3 Dated Amendments & Evaluation Protocol Status
* **Dated Amendment in `docs/LABEL_RULE.md`**: Yes. Commit `78f6363` added Section 6, titled:
  `"## 6. Dated Amendment: Live Data Ingestion & Sample Plot Expansion (November 2026)"`
  dated `2026-11-12`. It explicitly stated the root cause from `docs/DATA_REVISIT.md` (the STAC metadata placeholder `0.65`) and recorded the expansion from 12 to 24 plots across 8 talukas, live Planetary Sentinel-2 COG reads, and live NASA POWER precipitation.
* **Evaluation Protocol Approval**: `docs/EVAL_PROTOCOL.md` was authored during task T-05 (commit `091077f`, Nov 5, 2026) for the original 12-plot dataset. After the live data expansion to 24 plots in commit `78f6363`, **no new written, approved evaluation protocol was submitted to or approved by the user**.

---

## 2. Label Inputs vs. Feature Inputs & Leakage Analysis

### 2.1 Label Code Input Columns
The label function in `src/satbhoomi/features/label.py` (`compute_proxy_labels`) reads **ONLY**:
- `plot_code` (plot identifier)
- `season` (season identifier)
- `ndvi_peak` (full-season outcome peak NDVI)

It does **NOT** read, evaluate, or depend upon any rainfall, precipitation, mandi price, or yield column.

### 2.2 Origin of the Phrase "or precipitation deficit"
Because the label code uses NDVI only, the phrase *"or precipitation deficit"* in earlier descriptions did **not** originate from code, dataset schemas, or `docs/LABEL_RULE.md`.

* **Root Cause**: The phrase was an **erroneous conflation introduced in the assistant's previous chat summaries** (specifically in Step 3797 and Step 4069 of the conversation transcript). The assistant mistakenly blended the **T-09 Raksha alert engine rule** (which triggers in-season early warnings on winter precipitation deficit in `src/satbhoomi/alerts/engine.py`) with the **T-04 proxy credit default label rule**.
* **Audit of files containing "precipitation deficit"**:
  1. `src/satbhoomi/alerts/engine.py` (lines 141, 145): Raksha alert rule severity note and headline (`f"Winter precipitation deficit ({rain_deficit_pct:0.1f}% anomaly)"`). Legitimate alert engine logic.
  2. `src/satbhoomi/api/schemas/assessments.py` (line 138): Example string in Pydantic schema for `protective_factor` (`"example": "Assured tubewell irrigation buffers plot from winter precipitation deficit."`).
  3. `src/satbhoomi/api/mock_data.py` (line 141): Mock data payload providing the example text.
  4. `docs/api/openapi.json`: Deterministically generated OpenAPI contract reflecting `assessments.py`.

Nowhere in `src/satbhoomi/features/` or `data/processed/` does rainfall enter the proxy stress label.

### 2.3 Raw Columns Entering Label vs. Raw Columns Entering Features

| Category | Raw Column | In Label? | In Features? | Feature Column Produced |
| :--- | :--- | :---: | :---: | :--- |
| **Identifiers** | `plot_code` | **Yes** | **Yes** | Metadata identifier |
| | `season` | **Yes** | **Yes** | Metadata identifier |
| **Satellite** | `ndvi_peak` (full season) | **Yes** | **No** | Excluded from features (outcome variable) |
| | Scene NDVI ($\le$ Jan 31) | **No** | **Yes** | `ndvi_early`, `ndvi_pre_cutoff_mean`, `ndvi_pre_cutoff_std`, `ndvi_trend_pre_cutoff` |
| | Historical `ndvi_peak` ($t-1$) | **No** | **Yes** | `prev_season_ndvi_peak` (strictly prior season) |
| **Rainfall** | Daily Rain ($\le$ Jan 31) | **No** | **Yes** | `rain_pre_cutoff_total_mm`, `rain_pre_cutoff_deficit_pct` |
| | Post-cutoff Rain (Feb–Apr) | **No** | **No** | Excluded by Jan 31 cut-off gate |
| **Prices** | Mandi Modal ($\le$ Jan 31) | **No** | **Yes** | `mandi_pre_cutoff_volatility` |
| **Plot Static** | `area_acre`, `irrigation`, `insured` | **No** | **Yes** | `area_acre`, `irrigation`, `insured` |
| **Historical Label** | Prior `stressed` ($< t$) | **No** | **Yes** | `past_stressed_seasons_count` (strictly prior seasons) |

### 2.4 Truncation Test Scope
`tests/unit/test_features.py::test_truncation_test_guarantees_zero_temporal_leakage` tests the **feature pipeline** (`build_feature_dataset`). It deliberately corrupts all post-January 31 data (February–April rain, prices, and harvest yield) and proves that `FEATURE_COLUMNS` remain bit-for-bit identical. It does **not** cover label inputs because the label is by design computed from full-season `ndvi_peak` (which peaks in February during heading/flowering).

### 2.5 Single-Sentence Leakage Risk Statement
> *"Because the label uses full-season peak NDVI while features are strictly truncated on or before January 31, there is zero direct contemporaneous leakage between predictors and target, though an autoregressive link exists through strictly preceding seasons via `prev_season_ndvi_peak` and `past_stressed_seasons_count`."*

---

## 3. What Drives the Positives

For the 96 labelled plot-seasons in `data/processed/features.csv` (24 plots $\times$ 4 labelled seasons `2021-22` to `2024-25`):
- **Total Labelled Rows**: 96
- **Total Stressed Rows ($Y = 1$)**: **54 (56.25%)**
- **Total Normal Rows ($Y = 0$)**: **42 (43.75%)**

### Trigger Decomposition
Because the code evaluates only `peak_drop_pct >= 15.0%`:
- **NDVI condition only**: **54 rows (100% of positives, 56.25% of dataset)**
- **Rainfall condition only**: **0 rows (0.0%)** (no rainfall condition exists in label code)
- **Both conditions**: **0 rows (0.0%)**

### Breakdown by Season

| Season | Total Rows | Label Available | Stressed ($Y=1$) | Normal ($Y=0$) | Stressed Share (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **2020-21** | 24 | 0 | 0 | 0 | *Unlabelled Baseline* |
| **2021-22** | 24 | 24 | 5 | 19 | 20.83% |
| **2022-23** | 24 | 24 | 22 | 2 | **91.67%** |
| **2023-24** | 24 | 24 | 16 | 8 | **66.67%** |
| **2024-25** | 24 | 24 | 11 | 13 | 45.83% |
| **Total** | **120** | **96** | **54** | **42** | **56.25%** |

---

## 4. Descriptive Only: Drop Threshold Distribution

*Descriptive only: no label is being chosen here*

Distribution of rows classified as stressed across candidate percentage drop thresholds ($\tau$) applied to `peak_drop_pct` for all 96 labelled rows:

| Percentage Drop Threshold ($\tau$) | Stressed Count ($N=96$) | Share of Labelled Dataset (%) |
| :---: | :---: | :---: |
| $\ge 5.0\%$ | 83 | 86.46% |
| $\ge 10.0\%$ | 77 | 80.21% |
| **$\ge 15.0\%$ (Current Active Rule)** | **54** | **56.25%** |
| $\ge 20.0\%$ | 45 | 46.88% |
| $\ge 25.0\%$ | 31 | 32.29% |
| $\ge 30.0\%$ | 19 | 19.79% |

---

## 5. Baseline Quality & Depth Analysis

### 5.1 Drop-Versus-Baseline Distribution by Season and Depth

Distribution of `peak_drop_pct` across the 24 plots for each labelled season:

| Season | Baseline Depth (Prior Seasons) | N | Min Drop | 25th Pct | Median Drop | 75th Pct | Max Drop | Mean Drop | Stressed ($Y=1$) | Stress Rate (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2021-22** | 1 (`2020-21`) | 24 | -39.28% | +2.97% | +10.74% | +13.92% | +35.15% | +8.23% | 5 | 20.83% |
| **2022-23** | 2 (`2020-21`–`2021-22`) | 24 | -5.32% | +22.24% | **+27.73%** | +31.16% | +48.94% | +27.24% | 22 | **91.67%** |
| **2023-24** | 3 (`2020-21`–`2022-23`) | 24 | -22.03% | +13.30% | +21.94% | +28.63% | +47.89% | +19.53% | 16 | 66.67% |
| **2024-25** | 4 (`2020-21`–`2023-24`) | 24 | -5.93% | +11.16% | +14.77% | +24.66% | +39.11% | +17.17% | 11 | 45.83% |

### 5.2 Is 2021-22 Driving Most of the Positives?
**No.** Season `2021-22` (which relies on only 1 prior season as baseline) generated only **5 stressed rows out of 24 (20.83%)**, the lowest stress incidence in the entire dataset.

Instead, the overwhelming majority of positives is driven by **season 2022-23**, where **22 out of 24 plots (91.67%)** were flagged as stressed.
* **Mechanism**: In `season_dataset.csv`, the mean `ndvi_peak` across all 24 plots was `0.5589` in `2020-21` and `0.5013` in `2021-22`. In `2022-23`, regional Sentinel-2 optical reflectance dropped sharply to a mean of `0.3821` (median `0.4376`). Because the expanding historical baseline was anchored to the higher 2020–2022 values, almost every single plot in Anand district registered a drop $> 15\%$, producing an artificial 92% district-wide "distress" event.

### 5.3 Data Gaps in Baselines
* **Dataset Integrity Check**: In `data/processed/season_dataset.csv`, `data_gap_ndvi`, `data_gap_rainfall`, `data_gap_price`, and `data_gap_yield` are `False` across all 120 rows. All 120 plot-seasons have complete joined observations.
* **Observation Count Profile**: Valid optical scenes per season range between 19 and 33 across all plots (mean 28.8 scenes).
* **Biological Data Anomalies in Baseline**: Two coordinates exhibit persistently abnormal, non-vegetative signals across all 5 years:
  - `UMRETH_WHEAT_09`: `ndvi_peak` ranges between `0.0713` and `0.1436` across all 5 seasons (5-year mean `0.1079`).
  - `KHAMBHAT_WHEAT_12`: `ndvi_peak` ranges between `0.0469` and `0.0960` across all 5 seasons (5-year mean `0.0742`).
  *Finding*: These values reflect bare soil, fallow ground, or paved surface, rather than active wheat canopy (healthy wheat typically reaches NDVI 0.60–0.85). Computing a percentage drop on an initial baseline of `0.096` causes a tiny absolute sensor fluctuation ($\pm 0.02$) to generate massive swings from $-40\%$ to $+50\%$.

---

## 6. Natural Variability Benchmark

### 6.1 Comparison with Official District Statistics (`docs/DATA_REVISIT.md`)
In `docs/DATA_REVISIT.md` Section 5, official agricultural statistics from the Directorate of Agriculture, Gujarat for Anand district wheat show:

| Season | District Wheat Area (ha) | Production (t) | Official Yield (kg/ha) | YoY Yield Change | Yield vs. 5-Yr Mean | Labelled Stress Rate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **2020-21** | 48,200 | 168,700 | 3,500 | — | +1.86% | *Baseline* |
| **2021-22** | 51,400 | 174,760 | 3,400 | -2.86% | -1.05% | 20.83% |
| **2022-23** | 49,600 | 161,200 | 3,250 | **-4.41%** | **-5.41%** | **91.67%** |
| **2023-24** | 52,100 | 184,955 | 3,550 | +9.23% | +3.32% | 66.67% |
| **2024-25** | 50,800 | 176,784 | 3,480 | -1.97% | +1.28% | 45.83% |

### 6.2 Is a 15% Drop Smaller than Normal Variation?
**Yes.**
1. **Macro Agricultural Reality**: The largest official regional yield decline in Anand district wheat over the 5-year study was **-4.41%** (in 2022-23). Production varied by less than $\pm 6\%$ around the 5-year mean of 3,436 kg/ha.
2. **Sensor vs. Crop Divergence**: In satellite optical imagery, raw pixel NDVI naturally fluctuates between 15% and 25% across years due to atmospheric water vapor differences, slight calendar shifts in sowing dates (early November vs. early December), weed clearance timing, and satellite view angle differences.
3. **Implication**: Setting a flat $\ge 15\%$ drop threshold on raw Sentinel-2 peak pixel reflectance without calibrating against phenological shift or soil background noise treats routine inter-annual agricultural variation as severe default risk, labeling 56% of a highly productive, canal/tubewell irrigated farming region as "stressed."

---

## 7. Model Status & Evaluation Reality

### 7.1 Label Version Used in Evaluation
`docs/MODEL_EVAL.md` and `reports/metrics.json` were computed using the **current live data label version** (the 24-plot dataset with 54 stressed / 42 normal rows).

### 7.2 Were Models Re-Run After the Label Change?
**Yes.** Both `reports/metrics.json` and `docs/MODEL_EVAL.md` were re-run and updated in commit `78f6363` (Fri Nov 13 11:00:54 2026 +0530).

### 7.3 Model Artifacts in `models/`
- Active model: `models/satbhoomi-risk-v1.0-logreg-feat1-opt1th15-8bac5ab0-20261112.joblib`  
  - Timestamp: `2026-11-12 22:44:10`
  - Metadata: `models/satbhoomi-risk-v1.0-logreg-feat1-opt1th15-8bac5ab0-20261112.meta.json`
  - Input Data Hash: `8bac5ab0f36888deeef2fa53882de82faaa7cd608e359140afd9bdb146908ade`
- Historical fixture model: `models/satbhoomi-risk-v1.0-logreg-feat1-opt1th15-f85e5949-20261105.joblib` (initial run on synthetic data, Nov 5).

### 7.4 Model Performance Against Acceptance Criteria
In `reports/metrics.json`, the pre-registered model evaluation on the held-out `2024-25` test season ($N=24$: 11 stressed, 13 normal) produced:

| Model Architecture | Held-Out ROC-AUC | 95% Bootstrap CI | Brier Score | Decision Gate Status |
| :--- | :---: | :---: | :---: | :---: |
| **Rules Baseline** | — | — | 0.285 | Active Scorer (ADR-2) |
| **Logistic Regression** | **0.336** | [0.10, 0.58] | 0.324 | **CRITERIA_NOT_MET** |
| **Random Forest** | **0.427** | [0.18, 0.67] | 0.276 | **CRITERIA_NOT_MET** |
| **XGBoost** | **0.538** | [0.28, 0.79] | 0.291 | **CRITERIA_NOT_MET** |

*Official Verdict in `reports/metrics.json`*:
`"criteria_status": "CRITERIA_NOT_MET"`  
`"narrative": "Held-out AUC is below 0.70 or confidence interval spans 0.50. Model predictive signal is statistically unvalidated on small sample."`

Because every ML model performed at or below random guessing (AUC $\le 0.538$ with 95% CI spanning 0.50), the system strictly enforced ADR-2 and kept `AgronomicRulesBaseline` as the active scoring engine.

---

## 8. Provenance of Disaster Declaration Claim

### 8.1 Investigation of the Statement
The statement *"zero official disaster declarations in Anand 2020-2025"* appears in `docs/ALERTS.md`, `docs/PROGRESS.md`, and `docs/RISKS.md`.

### 8.2 Origin and Verification Status
* **Origin**: In `docs/DATA_REVISIT.md` (lines 6–7), the initial note was:
  `"Known Bad Events Reported by User: None reported (2020-21 to 2024-25)."`
* **Subsequent Narrative Expansion**: When drafting `docs/ALERTS.md`, this user-reported absence of known events was paraphrased into:
  `"zero official disaster, flood, or drought declarations were recorded for Anand district rabi wheat between 2020 and 2025 (Gujarat State Disaster Management Authority / Relief Commissionerate historical gazettes...)"`
* **Audit Finding**: **This was an unverified research assumption.**  
  There is **no** cited government gazette notification number, **no** GSDMA URL, and **no** downloaded official disaster declaration report stored or referenced in the repository. The reference to official gazettes was an assumed characterization of the user's reporting rather than an independently audited government citation.

---

## 9. Synthesis: Verdict, Established Facts, Unproven Claims, and Decisions Needed

### 9.1 Plain Verdict
**Is the current label scientifically sound, defensible for credit underwriting, and compliant with the approved protocol?**

**Verdict: NO.**
1. **Defensibility for Credit Underwriting**: A proxy label that designates **56.25% of all farming seasons (and 91.67% of farmers in 2022-23)** as "stressed/default" in a district with $>90\%$ tubewell/canal irrigation and stable yields ($\pm 5\%$) is economically unviable. In a commercial lending deployment, it would cause an underwriting engine to penalize, reduce limits for, or reject more than half of all creditworthy smallholders.
2. **Scientific Soundness**: The label applies a flat $15\%$ relative drop on uncalibrated single-pixel peak NDVI without accounting for phenological shifts, sensor viewing angles, or non-crop landcover (as evidenced by coordinates like `UMRETH_WHEAT_09` having sub-0.15 peak NDVI in every year).
3. **Protocol Compliance**: While the code implements the formula described in Section 1 of `docs/LABEL_RULE.md`, the sample expansion from 12 to 24 plots was implemented without an updated, formally approved evaluation protocol.

---

### 9.2 Established Facts vs. Unproven Claims

#### Established Facts (What We Are Certain Of)
1. **Label Code Inputs**: `src/satbhoomi/features/label.py` uses strictly `ndvi_peak`, `plot_code`, and `season`. It has never evaluated or read any rainfall or precipitation column.
2. **Positive Distribution**: Exactly 54 of 96 labelled plot-seasons (56.25%) are marked `stressed = 1.0`.
3. **Season 2022-23 Concentration**: Season 2022-23 accounts for 22 of the 54 positive rows (a 91.67% stress rate), caused by a broad drop in Sentinel-2 pixel peak reflectance across Anand district relative to the 2020–2022 baseline.
4. **2021-22 Baseline Depth**: Single-season baseline depth in 2021-22 does not drive the positives (only 5 out of 24 plots stressed, 20.83%).
5. **Leakage Protection**: No look-ahead temporal leakage flows into predictive features; all features are strictly truncated on or before January 31, while `ndvi_peak` occurs in February.
6. **Model Failure**: Every trained ML model failed pre-registered performance gates (held-out AUC $\le 0.54$, `CRITERIA_NOT_MET`), and the active scorer remains the agronomic rules baseline per ADR-2.

#### Unproven Claims (Claims Made Without Sufficient Evidence)
1. **Proxy Ground Truth Validity**: The foundational hypothesis that a $\ge 15\%$ drop in Sentinel-2 pixel peak NDVI corresponds to financial repayment default or economic crop loss is unvalidated by any empirical loan repayment or insurance claims dataset.
2. **Zero Disaster Declarations**: The assertion that "zero official disaster declarations were recorded by GSDMA in Anand 2020–2025" is an unverified narrative assumption lacking a primary government citation.
3. **Sample Plot Purity**: The assumption that all 24 sample coordinates represent active wheat fields is contradicted by persistent sub-0.15 peak NDVI values for plots `UMRETH_WHEAT_09` and `KHAMBHAT_WHEAT_12`.

---

### 9.3 Neutral Decision Formulations for User Decision

The following architectural and methodological decisions are formulated for your review and direction before further modeling or underwriting logic is built:

#### Decision 1: Ground Truth Target Formulation & Threshold Calibration
* **Option A**: Retain the relative optical drop rule but calibrate the threshold to true tail-risk (e.g., $\tau \ge 25\%$ or $\ge 30\%$) and require an absolute baseline floor (e.g., `historical_baseline_ndvi >= 0.35`) so bare-soil plots are quarantined.
* **Option B**: Formulate a composite agronomic stress label combining peak NDVI drop with extreme local weather deficit (e.g., both vegetative drop AND verified severe precipitation/temperature stress).
* **Option C**: Anchor proxy stress directly to official district/taluka yield shortfall thresholds (e.g., seasons where yield falls $> 10\%$ below the 5-year rolling average).

#### Decision 2: Sample Coordinate Quality & Crop Mask Verification
* **Option A**: Audit all 24 plot coordinate centroids against ESA WorldCover or high-resolution imagery, replace non-crop or bare-soil coordinates (such as `UMRETH_WHEAT_09` and `KHAMBHAT_WHEAT_12`) with verified cultivated wheat parcel polygons, and re-extract satellite time-series.
* **Option B**: Retain the 24 coordinates but implement an automated quality-filter rule that flags any parcel with multi-year peak NDVI $< 0.30$ as non-cultivated and marks its label as `insufficient_data` / quarantined.

#### Decision 3: Official Disaster Declaration Provenance
* **Option A**: Retrieve and cite official Gujarat Revenue Department / Relief Commissionerate / GSDMA annual calamity notifications for Anand district (2020–2025) and document them with gazette dates.
* **Option B**: Update documentation across `docs/ALERTS.md`, `docs/PROGRESS.md`, and `docs/RISKS.md` to remove the reference to official gazettes, stating transparently that no field-reported calamities were available for the sample.

#### Decision 4: Evaluation Protocol Re-Approval Gate
* **Option A**: Draft an updated `docs/EVAL_PROTOCOL.md` reflecting the 24-plot dataset and chosen label threshold, and require formal user approval before any retraining or scoring promotion.
* **Option B**: Freeze machine learning retraining entirely and continue exclusively with the interpretable `AgronomicRulesBaseline` until real banking loan outcome data or PMFBY claim records can be obtained.

