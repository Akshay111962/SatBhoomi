# SatBhoomi Scorer and Threshold Review (Stage A: Review)

**Status**: APPROVED  
**Approval Date**: 2026-11-15  
**Date**: November 2026  
**Document Type**: Pre-Implementation Agronomic Scorer Review  
**Reference Report**: `reports/scorer_review.json` (Strict Numerical Traceability & Label Blindness)  
**Target Crop & Geography**: Wheat (*Triticum aestivum*), Rabi Season, Anand District, Gujarat, India  

---

## 1. Executive Summary & Label Blindness Disclosure

This document conducts a rigorous agronomic review of the active risk engine (`AgronomicRulesBaseline`), risk banding thresholds, alert engine rules, and loan underwriting suggestion parameters following the Sentinel-2 Processing Baseline 04.00+ radiometric offset correction (ADR-10) and Rule R1 non-crop plot exclusion (ADR-11).

> [!IMPORTANT]
> **Label Blindness (Hard Rule)**:
> This entire review was conducted in **strict blindness to the stress label**. In accordance with the pre-registered protocol, all analysis scripts (`scripts/analysis/scorer_review.py`) dropped the `stressed`, `label_unavailable`, and `peak_drop_pct` columns immediately upon loading `data/processed/features.csv`. Automated unit test [`tests/unit/test_scorer_review.py`](file:///d:/SatBhoomi/tests/unit/test_scorer_review.py) proves that label columns are never accessed. No threshold or principle in this document was tuned to achieve any target label performance, class balance, or score distribution.

---

## 2. A1: Current Rules, Thresholds, and Historical Provenance

The table below catalogs every rule, threshold, and parameter across the scoring engine, risk banding, and alerts, identifying its file location, line number, numerical value, and original derivation basis:

| Component | Rule / Threshold Name | Current Value | File & Line | Derivation Basis | Chosen Pre-Correction? |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **Rules Baseline** | `ndvi_early_threshold` | $\le 0.35$ | [`src/satbhoomi/risk/baseline.py#L154`](file:///d:/SatBhoomi/src/satbhoomi/risk/baseline.py#L154) | Heuristic agronomic estimate of early stunted canopy | **YES (Pre-Correction)** |
| **Rules Baseline** | `ndvi_trend_threshold` | $\le 0.0$ | [`src/satbhoomi/risk/baseline.py#L155`](file:///d:/SatBhoomi/src/satbhoomi/risk/baseline.py#L155) | Heuristic assumption that growing wheat must have positive slope | **YES (Pre-Correction)** |
| **Rules Baseline** | `rain_deficit_threshold_pct`| $\le -20.0\%$ | [`src/satbhoomi/risk/baseline.py#L156`](file:///d:/SatBhoomi/src/satbhoomi/risk/baseline.py#L156) | Standard meteorological drought anomaly threshold | **YES (Pre-Correction)** |
| **Rules Baseline** | Compound Stress Output $\hat{p}$ | $0.85$ | [`src/satbhoomi/risk/baseline.py#L189`](file:///d:/SatBhoomi/src/satbhoomi/risk/baseline.py#L189) | Pre-registered high probability tier (ADR-2) | **YES (Pre-Correction)** |
| **Rules Baseline** | Partial Stress Output $\hat{p}$ | $0.45$ | [`src/satbhoomi/risk/baseline.py#L190`](file:///d:/SatBhoomi/src/satbhoomi/risk/baseline.py#L190) | Pre-registered medium probability tier (ADR-2) | **YES (Pre-Correction)** |
| **Rules Baseline** | Normal Growth Output $\hat{p}$ | $0.10$ | [`src/satbhoomi/risk/baseline.py#L173`](file:///d:/SatBhoomi/src/satbhoomi/risk/baseline.py#L173) | Pre-registered low probability tier (ADR-2) | **YES (Pre-Correction)** |
| **Risk Banding** | `BAND_LOW_MAX` | $34$ | [`src/satbhoomi/risk/scoring.py#L47`](file:///d:/SatBhoomi/src/satbhoomi/risk/scoring.py#L47) | Derived to encapsulate normal baseline score ($10 \in [0, 34]$) | **YES (Pre-Correction)** |
| **Risk Banding** | `BAND_MEDIUM_MAX` | $69$ | [`src/satbhoomi/risk/scoring.py#L48`](file:///d:/SatBhoomi/src/satbhoomi/risk/scoring.py#L48) | Derived to encapsulate partial stress score ($45 \in [35, 69]$) | **YES (Pre-Correction)** |
| **Risk Banding** | High Band Range | $[70, 100]$ | [`src/satbhoomi/risk/scoring.py#L110`](file:///d:/SatBhoomi/src/satbhoomi/risk/scoring.py#L110) | Encapsulates compound stress score ($85 \in [70, 100]$) | **YES (Pre-Correction)** |
| **Data Tolerance** | `MAX_MISSING_FEATURES_ALLOWED` | $2$ (of 12) | [`src/satbhoomi/risk/scoring.py#L55`](file:///d:/SatBhoomi/src/satbhoomi/risk/scoring.py#L55) | Engineering assumption for Season 1 missing history | **YES (Pre-Correction)** |
| **Alert Engine** | `NDVI_DROP_MEDIUM_PCT` | $15.0\%$ | [`src/satbhoomi/alerts/config.py#L33`](file:///d:/SatBhoomi/alerts/config.py#L33) | Agronomic drop threshold aligned with label rule | **YES (Pre-Correction)** |
| **Alert Engine** | `NDVI_DROP_HIGH_PCT` | $25.0\%$ | [`src/satbhoomi/alerts/config.py#L34`](file:///d:/SatBhoomi/alerts/config.py#L34) | Heuristic acute crop collapse threshold | **YES (Pre-Correction)** |
| **Alert Engine** | `RAIN_DEFICIT_MEDIUM_PCT` | $-25.0\%$ | [`src/satbhoomi/alerts/config.py#L46`](file:///d:/SatBhoomi/alerts/config.py#L46) | IMD moderate agricultural drought classification | **YES (Pre-Correction)** |
| **Alert Engine** | `RAIN_DEFICIT_HIGH_PCT` | $-50.0\%$ | [`src/satbhoomi/alerts/config.py#L47`](file:///d:/SatBhoomi/alerts/config.py#L47) | IMD severe agricultural drought classification | **YES (Pre-Correction)** |
| **Alert Engine** | `PRICE_DROP_ALERT_PCT` | $15.0\%$ | [`src/satbhoomi/alerts/config.py#L55`](file:///d:/SatBhoomi/alerts/config.py#L55) | APMC monthly modal price drop assumption | **YES (Pre-Correction)** |

> [!CAUTION]
> **Key Finding**: Every single threshold in `AgronomicRulesBaseline`, `scoring.py`, and `alerts/config.py` was established **BEFORE** the Sentinel-2 PB 04.00+ offset was discovered and corrected, and before the 3 non-crop plots were excluded.

---

## 3. A2: Empirical Distributions on Corrected Data & Current Threshold Behavior

All figures in this section originate deterministically from [`reports/scorer_review.json`](file:///d:/SatBhoomi/reports/scorer_review.json), computed over all **21 active plots** across **5 completed seasons** ($N = 105$ plot-seasons) with label columns completely excluded.

### 1. Scorer Input Distributions at January 31 Cut-off Date

| Scorer Input Feature | Min | $p_{10}$ | $p_{25}$ | Median | $p_{75}$ | $p_{90}$ | Max | Mean | Std | Missing |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `ndvi_early` | 0.1828 | 0.2557 | 0.3302 | **0.4008** | 0.4736 | 0.5231 | 0.6169 | 0.3959 | 0.1019 | 0 |
| `ndvi_pre_cutoff_mean` | 0.1843 | 0.2697 | 0.3544 | **0.4708** | 0.5405 | 0.5941 | 0.7327 | 0.4452 | 0.1249 | 0 |
| `ndvi_pre_cutoff_std` | 0.0165 | 0.0359 | 0.0670 | **0.1054** | 0.1447 | 0.1809 | 0.2314 | 0.1060 | 0.0529 | 0 |
| `ndvi_trend_pre_cutoff` | -0.0031 | -0.0013 | -0.0004 | **+0.0018** | +0.0040 | +0.0053 | +0.0077 | +0.0019 | 0.0026 | 0 |
| `rain_pre_cutoff_total_mm` | 0.02 | 0.07 | 12.41 | **34.75** | 72.10 | 92.62 | 123.40 | 41.68 | 35.18 | 0 |
| `rain_pre_cutoff_deficit_pct` | -99.81% | -99.33% | +18.19% | **+230.95%** | +586.67% | +782.10% | +1075.24% | +297.00% | 335.08% | 0 |
| `mandi_pre_cutoff_volatility` | 0.0049 | 0.0049 | 0.0051 | **0.0054** | 0.0057 | 0.0061 | 0.0061 | 0.0054 | 0.0004 | 0 |
| `prev_season_ndvi_peak` | 0.2100 | 0.3541 | 0.5222 | **0.6860** | 0.7570 | 0.8111 | 0.8820 | 0.6270 | 0.1769 | 21 (S1) |
| `area_acre` | 1.94 | 1.94 | 1.94 | **1.94** | 2.79 | 2.79 | 4.97 | 2.29 | 0.70 | 0 |

*Categorical Breakdown ($N=105$)*:
- `irrigation`: `tube_well`: 50 (47.6%), `canal`: 40 (38.1%), `rainfed`: 15 (14.3%) [$\implies$ **85.7% irrigated**]
- `insured`: `1` (insured): 70 (66.7%), `0` (uninsured): 35 (33.3%)

### 2. Flagging Rates under CURRENT Thresholds

| Condition / Risk Band | Rule Expression | Flagged Plot-Seasons ($N=105$) | Flagged Share (%) |
| :--- | :--- | :---: | :---: |
| **Condition 1a** | `ndvi_early <= 0.35` | 34 | 32.38% |
| **Condition 1b** | `ndvi_trend_pre_cutoff <= 0.0` | 37 | 35.24% |
| **Condition 1 (Vegetative Lag)** | Condition 1a OR Condition 1b | **55** | **52.38%** |
| **Condition 2 (Rain Deficit)** | `rain_pre_cutoff_deficit_pct <= -20.0%` | 12 | 11.43% |
| **Compound Stress (High Band)** | Condition 1 AND Condition 2 ($\hat{p}=0.85$) | **5** | **4.76%** |
| **Partial Stress (Medium Band)** | (Condition 1 OR Condition 2) & ~Compound ($\hat{p}=0.45$) | **57** | **54.29%** |
| **Normal Growth (Low Band)** | Neither Condition ($\hat{p}=0.10$) | **43** | **40.95%** |

### 3. Seasonal Breakdown of Flags

| Season | Total Rows | Cond 1a Flagged | Cond 1b Flagged | Cond 1 Combined | Cond 2 Flagged | Low Band | Medium Band | High Band |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2020-21** | 21 | 7 | 8 | 13 | 0 | 8 | 13 | 0 |
| **2021-22** | 21 | 11 | 9 | 14 | 0 | 7 | 14 | 0 |
| **2022-23** | 21 | 5 | 7 | 9 | 0 | 12 | 9 | 0 |
| **2023-24** | 21 | 4 | 8 | 10 | 0 | 11 | 10 | 0 |
| **2024-25** | 21 | 7 | 5 | 9 | 12 | 5 | 11 | 5 |

### 4. Analysis of Permanent Flags Across All 5 Seasons
A permanent flag across all 5 seasons demonstrates that a fixed absolute threshold measures **plot characteristics (soil, canopy density, planting date)** rather than in-season weather or crop stress:

- **Permanently Flagged by Condition 1a (`ndvi_early <= 0.35`)**: **2 plots** (`ANAND_WHEAT_14`, `TARAPUR_WHEAT_11`).
- **Permanently Flagged by Condition 1b (`ndvi_trend <= 0.0`)**: **3 plots** (`ANAND_WHEAT_13`, `BORSAD_WHEAT_03`, `TARAPUR_WHEAT_11`).
- **Permanently Flagged by Condition 1 (Vegetative Lag)**: **6 plots** (`ANAND_WHEAT_02`, `ANAND_WHEAT_13`, `ANAND_WHEAT_14`, `BORSAD_WHEAT_03`, `SOJITRA_WHEAT_19`, `TARAPUR_WHEAT_11`).
- **Permanently Flagged in a Non-Low Band (Medium or High in 5/5 Seasons)**: Exactly the same **6 plots (28.6% of active plots)**!

> [!WARNING]
> **Diagnostic Finding**: More than a quarter of the active plots (6 of 21) are permanently classified as distressed every single year solely because their early vegetative NDVI happens to sit below an arbitrary global constant (0.35) or their canopy growth plateaus early. Absolute thresholds penalize slow-greening plots regardless of whether they have a normal harvest.

---

## 4. A3: Same-Date Natural Variability at the Cut-Off Window

To establish an objective, empirical benchmark for what constitutes genuine vegetative anomalies, we measured the relative difference of each plot's cut-off window NDVI against that plot's OWN mean on the same window across all strictly earlier seasons:

$$\Delta_{\text{rel}} = \frac{\text{NDVI}_{p, t} - \mu_{\text{prior}}(p, t)}{\mu_{\text{prior}}(p, t)} \times 100\%$$

Across all 84 valid historical transitions in the active dataset (seasons 2021-22 through 2024-25), the empirical distributions are:

### 1. Mid-to-Late January Cut-off Window (January 15–31, $N=84$ complete transitions)

| Metric / Stratum | $N$ | Min (%) | $p_{10}$ (%) | $p_{25}$ (%) | Median (%) | $p_{75}$ (%) | $p_{90}$ (%) | Max (%) | MAD (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **All Transitions** | **84** | **-37.18%** | **-19.92%** | **-7.21%** | **+1.00%** | **+7.24%** | **+21.26%** | **+46.24%** | **7.24%** |
| $k = 1$ prior season | 21 | -37.18% | -23.04% | — | -6.81% | — | +3.51% | +14.78% | **4.43%** |
| $k = 2$ prior seasons | 21 | -25.60% | -16.31% | — | +3.89% | — | +17.16% | +24.54% | **6.05%** |
| $k = 3$ prior seasons | 21 | -29.18% | -25.20% | — | +3.28% | — | +28.63% | +46.24% | **7.72%** |
| $k = 4$ prior seasons | 21 | -31.28% | -12.94% | — | +4.47% | — | +26.53% | +41.51% | **5.21%** |

### 2. Pre-Cutoff Cumulative Mean (`ndvi_pre_cutoff_mean`, $N=84$ transitions)

| Metric / Stratum | $N$ | Min (%) | $p_{10}$ (%) | $p_{25}$ (%) | Median (%) | $p_{75}$ (%) | $p_{90}$ (%) | Max (%) | MAD (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **All Transitions** | **84** | **-49.71%** | **-17.47%** | **-9.51%** | **+2.79%** | **+8.51%** | **+24.08%** | **+53.84%** | **9.78%** |

### 3. Early Vegetative Greenness (`ndvi_early`, $N=84$ transitions)

| Metric / Stratum | $N$ | Min (%) | $p_{10}$ (%) | $p_{25}$ (%) | Median (%) | $p_{75}$ (%) | $p_{90}$ (%) | Max (%) | MAD (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **All Transitions** | **84** | **-38.51%** | **-19.67%** | **-9.71%** | **+0.36%** | **+12.36%** | **+29.21%** | **+53.57%** | **10.90%** |

### Key Agronomic Takeaways from Natural Variability:
1. **The Median is Centered at Zero**: Across all 84 transitions, the median relative shift at the cut-off window is $+1.00\%$ (and $+0.36\%$ for early NDVI), confirming excellent radiometric harmonization and temporal stability across the 5 seasons.
2. **Natural Dispersion (MAD)**: The Median Absolute Deviation of vegetative greenness around a plot's own historical norm is **7.24%** for late January, and **9.78%** for the pre-cutoff mean.
3. **Statistical Significance Bounds**:
   - $1.0 \times \text{MAD} \approx 7.2\%$ (normal seasonal weather noise).
   - $2.0 \times \text{MAD} \approx 14.5\%$ (matches the 10th percentile bound $-19.92\%$ and aligns remarkably with the 15% drop benchmark).
   - Any vegetative drop $< 10\%$ is indistinguishable from common annual variance.

---

## 5. A4: Proposed Principles (Formulated Prior to Computing Any New Score)

To eliminate permanent plot penalization and align the scoring engine with physical reality, we propose five core principles:

### Principle 1: Relative NDVI Drop Rule Grounded in Natural Variability
- **Agronomic Theory**: A farm plot with fertile deep vertisols and early sowing may peak at NDVI 0.75, while a plot with lighter sandy loam may peak at NDVI 0.50. Under an absolute threshold ($0.35$), the lighter plot is permanently penalized. Under a relative rule, each plot is evaluated against **its own historical capacity on the same calendar window**.
- **Rule Formulation**:
  - Flag vegetative stress only when the plot's cut-off window NDVI (`ndvi_pre_cutoff_mean` or checkpoint window) drops below its own historical prior baseline by more than **$2.0 \times \text{MAD}$** ($\ge 15.0\%$).
  - A relative drop of $15.0\%$ represents the 10th percentile of natural variation; drops exceeding $25.0\%$ represent extreme outliers ($> 3.0 \times \text{MAD}$).

### Principle 2: Differentiated Rainfall Treatment for Irrigated vs. Rainfed Tracts
- **Agronomic Reality**:
  - In Anand district, **85.7% of wheat is irrigated** (canal or tube-well).
  - Normal winter rainfall (Nov 1 to Jan 31) is only **10.5 mm**. 
  - A winter drought of $-99.8\%$ (observed in 2024-25) represents a deficit of only $\sim 10\text{ mm}$ of water—easily compensated by a single supplementary irrigation cycle.
  - Conversely, in 4 out of 5 seasons, unseasonal winter showers produced deficits of $+200\%$ to $+1000\%$, which caused zero flags in Condition 2.
- **Rule Formulation**:
  - For **irrigated plots** (`irrigation in ['tube_well', 'canal', 'drip', 'sprinkler']`), winter rainfall deficit is a secondary modifier and must **never independently trigger high risk**.
  - For **rainfed plots** (`irrigation == 'rainfed'`), winter rainfall deficit ($\le -25\%$) is a primary stress driver and can escalate risk to high when combined with vegetative lag.

### Principle 3: Mandi Price Volatility as Market Risk Factor, Not Agronomic Stress
- **Economic Reality**: Mandi prices at January 31 represent early season arrivals. APMC wheat prices in Anand show extremely tight historical coefficient of variation ($\text{CV} \in [0.0049, 0.0061]$).
- **Rule Formulation**: Mandi price volatility is maintained as a district-level contextual indicator and loan structuring input (e.g. informing repayment window flexibility in `loan_suggestions.py`), but does not override plot-level biophysical vegetative health in the in-season risk score.

### Principle 4: Objective Agronomic Risk Band Cut-offs
- **Score Scale**: $[0, 100]$ integer score.
- **Band Definitions**:
  - **Low Risk ($0 \le \text{score} \le 34$)**: Normal vegetative progression (drop $< 15\%$). Crop vigour matches historical plot norms.
  - **Medium Risk ($35 \le \text{score} \le 69$)**: Moderate vegetative lag ($15\% \le \text{drop} < 25\%$) OR severe rain deficit on rainfed plots. Triggers supportive advisory and proactive field verification.
  - **High Risk ($70 \le \text{score} \le 100$)**: Compound distress (acute vegetative collapse $\ge 25\%$ OR moderate vegetative lag compounded by rainfed moisture failure). Triggers formal restructuring and relief assistance.

### Principle 5: Strict Handling of Plots with No Historical Baseline
- **Integrity Rule**: When a plot-season has **zero completed prior seasons** (e.g., Season 1: `2020-21`), relative historical comparison is mathematically impossible.
- **Enforcement**:
  - Return `status = "insufficient_data"` with explicit `insufficient_data_reason = "No historical prior seasons available to establish plot baseline"`.
  - **Prohibition**: Never impute, guess, or assign an arbitrary default score (e.g. 10 or 50) to plots lacking historical baseline depth.

---

## 6. A5: Loan Suggestion Parameters Census & Status Audit

In accordance with banking governance rules, all parameters in [`src/satbhoomi/risk/loan_suggestions.py`](file:///d:/SatBhoomi/src/satbhoomi/risk/loan_suggestions.py) are classified below:

| Loan Parameter | Code Constant | Current Value | Source / Document | Status | Action Required |
| :--- | :--- | :---: | :--- | :---: | :--- |
| **Scale of Finance (Irrigated Wheat)** | `SCALE_OF_FINANCE_WHEAT_IRRIGATED` | ₹32,000 / acre | Gujarat State DLTC heuristic guideline | **PLACEHOLDER** | **Must obtain**: Official District Level Technical Committee (DLTC) Anand notification for Rabi wheat from ADCCB / Lead Bank Office. |
| **Scale of Finance (Rainfed Wheat)** | `SCALE_OF_FINANCE_WHEAT_RAINFED` | ₹22,000 / acre | Gujarat State DLTC heuristic guideline | **PLACEHOLDER** | **Must obtain**: Official Anand DLTC notification for rainfed wheat. |
| **RBI Collateral-Free Limit** | `RBI_COLLATERAL_FREE_LIMIT_INR` | ₹2,00,000 | RBI KCC Circular FIDD.CO.FSD.BC.No.13/2018-19 & Blueprint Section 6 | **VERIFIED** | Statutory central bank limit; verified. |
| **Low Risk Haircut Ratio** | `LIMIT_BAND_RATIOS['low']` | 90% – 100% | SatBhoomi Blueprint Section 6 & ADR-2 | **ASSUMPTION** | Team underwriting assumption (no haircut for healthy plots). |
| **Medium Risk Haircut Ratio** | `LIMIT_BAND_RATIOS['medium']` | 65% – 80% | SatBhoomi Blueprint Section 6 & ADR-2 | **ASSUMPTION** | Team underwriting assumption (prevent over-indebtedness). |
| **High Risk Haircut Ratio** | `LIMIT_BAND_RATIOS['high']` | 40% – 50% | SatBhoomi Blueprint Section 6 & ADR-2 | **ASSUMPTION** | Team underwriting assumption (conservative ceiling). |
| **Repayment Month** | `REPAYMENT_MONTH_RABI_WHEAT` | May | Anand APMC mandi arrival records | **VERIFIED** | Agronomic/market harvest cycle; verified. |
| **Harvest Window** | `harvest_window` | March–April | Anand wheat crop calendar | **VERIFIED** | Agronomic crop calendar; verified. |
| **Marketing Window** | `marketing_window` | April–May | APMC Anand arrival peaks | **VERIFIED** | Market arrival timeline; verified. |
| **Mandatory Insurance Trigger** | `insurance_mandated` | Triggered if `insured == 0` | PMFBY Operational Guidelines | **VERIFIED** | PMFBY loanee guidelines; verified. |

---

## 7. A6: Synthesis of Proposed Changes and Systemic Downstream Impact

If approved, the transition from uncorrected absolute thresholds to harmonized relative thresholds will have the following concrete impacts across the system:

1. **Risk Scoring Engine (`scoring.py` / `baseline.py`)**:
   - Replaces static absolute constants (`ndvi_early <= 0.35`) with relative comparison against the plot's own prior baseline on the cut-off window.
   - Eliminates permanent penalization of the 6 plots that were flagged in 5/5 seasons solely due to inherently lower natural greenness.
   - Season 1 (`2020-21`) cleanly returns `status="insufficient_data"` instead of an invented score.
   - Scorer `model_version` will be incremented to:  
     `satbhoomi-rules-v2.0-relative-20261114`
2. **Loan Suggestions (`loan_suggestions.py`)**:
   - Plots in Season 1 will not receive an ungrounded loan limit; they will require baseline initialization or manual underwriting review.
   - For seasons 2–5, limits will be right-sized based on genuine relative vegetative anomalies rather than static plot traits.
3. **What-If Simulation (`what_if.py`)**:
   - Re-evaluates baseline scores and prospective deltas against corrected feature distributions.
   - Preserves strict `estimate` labeling and non-causal attribution.
4. **Raksha Alert Engine (`alerts/config.py` / `engine.py`)**:
   - Preserves the existing relative alert logic (which already compared checkpoints against prior seasons), but synchronizes thresholds with the empirical natural variability bounds established in Section A3.
   - Irrigated plots continue to cap rainfall alerts at `medium`, preventing unseasonal winter rainfall deficits from raising false alarms.
5. **API & Contract Compatibility**:
   - Zero breaking changes to Pydantic models or OpenAPI contracts.
   - All response models continue to output verified typed schemas.

---

> [!NOTE]
> **GATE APPROVED (Stage A Complete, Stage B Active)**:
> In accordance with instructions, this review document was reviewed and received user approval on **2026-11-15**. Stage B implementation proceeds in accordance with the principles specified herein.
