# SatBhoomi Model Evaluation and Validation Protocol (Protocol v2)

**Status**: PROPOSED (Awaiting User Approval)  
**Date**: November 2026  
**Document Type**: Evaluation Protocol & Feasibility Gate Pre-Registration  
**Target Crop & Geography**: Wheat (*Triticum aestivum*), Rabi Season, Anand District, Gujarat, India  
**Reference Artifact**: `reports/label_counts.json`  

---

## 1. Executive Summary & Feasibility Gate Status

Following radiometric correction of Sentinel-2 processing-baseline offsets (PB 04.00+ / ADR-10) and exclusion of non-crop plots under Rule R1 (ADR-11), the active dataset comprises **21 plots** across 5 seasons (105 plot-seasons total, of which 21 in 2020-21 initialize plot baseline history, leaving **84 labelled instances**).

Under the unchanged 15% relative drop rule ($\tau = 15\%$), exactly **4 stressed rows** exist across all 5 seasons (exactly 1 per season from 2021-22 to 2024-25), with 80 normal rows (4.76% stressed rate).

### The Feasibility Gate
To guard against evaluating machine learning classifiers on statistically trivial samples, we pre-register a formal **Feasibility Gate** that must be met before any model training, hyperparameter tuning, or held-out evaluation can be conducted:

1. **Test Set Minimum Positives**: The held-out evaluation set (`2024-25`) must contain at least **5 positive (stressed) instances** and at least **5 negative (normal) instances**.
2. **Pooled Folds Minimum Positives**: The pooled forward-chaining cross-validation folds across all labelled seasons must contain at least **10 positive (stressed) instances**.

### Gate Evaluation (Source: `reports/label_counts.json`)

| Gate Criterion | Required | Observed (2026-11-14) | Result |
| :--- | :---: | :---: | :---: |
| Held-out Test Set (`2024-25`) Positives | $\ge 5$ | **1** | **FAILED** |
| Held-out Test Set (`2024-25`) Negatives | $\ge 5$ | **20** | **PASSED** |
| Pooled Forward-Chaining Positives | $\ge 10$ | **4** | **FAILED** |
| **Overall Feasibility Gate** | — | — | **NOT EVALUABLE** |

### Policy Action: ML Training Frozen
Because the feasibility gate fails, **Machine Learning model training and evaluation remain strictly frozen**. 
- No scikit-learn or XGBoost training runs may be executed against this dataset.
- The baseline heuristic **`AgronomicRulesBaseline` remains the sole active risk scorer** for SatBhoomi Score.
- `docs/MODEL_EVAL.md` remains **SUPERSEDED** and historical.

---

## 2. Descriptive Analysis of Agronomic Rules Baseline on Stressed Rows

> [!NOTE]
> **Disclaimer**: $n = 4$, descriptive only, no inference. No accuracy, precision, or recall claims are made from this sample.

Below is the complete census of all 4 stressed plot-seasons identified in the active dataset, showing their vegetative drop, the `AgronomicRulesBaseline` predicted probability $\hat{p}$, assigned risk band, early NDVI, and pre-cutoff rainfall anomaly:

| Plot Code | Season | Relative Drop | Predicted $\hat{p}$ | Risk Band | Early NDVI (`ndvi_early`) | Rain Deficit (`rain_pre_cutoff_deficit_pct`) | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `TARAPUR_WHEAT_22` | 2021-22 | -16.55% | **0.10** | Low | 0.4303 | +73.43% | Canopy developed normally by Jan 31; peak failure occurred late season. Rain surplus present. |
| `ANAND_WHEAT_02` | 2022-23 | -27.01% | **0.45** | Medium | 0.2417 | +680.00% | Early NDVI $\le 0.35$ triggered Condition 1 (stunted canopy). Rain anomaly surplus (irrigated tract). |
| `ANAND_WHEAT_01` | 2023-24 | -18.09% | **0.45** | Medium | 0.5118 | +341.90% | Pre-cutoff trend negative triggered Condition 1. Rain surplus. |
| `ANAND_WHEAT_02` | 2024-25 | -15.25% | **0.45** | Medium | 0.2509 | +663.81% | Early NDVI $\le 0.35$ triggered Condition 1. Rain surplus. |

### Agronomic Context & Upcoming Threshold Review
The rules baseline thresholds (`ndvi_early <= 0.35`, `ndvi_trend_pre_cutoff <= 0.0`, `rain_pre_cutoff_deficit_pct <= -20%`) were established prior to the Sentinel-2 PB 04.00+ radiometric offset correction and before non-crop exclusion. 
- In Anand district, wheat is $>85\%$ tube-well/canal irrigated; rainfall surplus or deficit during Rabi has limited direct correlation with irrigation availability.
- The rules baseline thresholds require a principled agronomic review based on the corrected NDVI distributions and local wheat phenology in the next scheduled task. **No thresholds are changed in this protocol document.**

---

## 3. Label Robustness & Sensitivity Analysis

> [!NOTE]
> **Disclaimer**: *Descriptive only: no label is being chosen here.* The 15% threshold ($\tau = 15\%$) remains the pre-registered label definition.

The following figures from `reports/label_counts.json` illustrate how label prevalence responds to alternative definitions, historical baseline depth, and plot filtering:

### 1. Relative Drop Threshold Variation ($\tau$)

| Threshold ($\tau$) | Stressed Count ($N=84$) | Stressed Share (%) | Interpretation |
| :---: | :---: | :---: | :--- |
| **10% drop** | 11 | 13.10% | Captures minor vegetative fluctuations; potentially conflates normal weather variation with true stress. |
| **15% drop (Active)** | **4** | **4.76%** | Pre-registered threshold; identifies pronounced vegetative anomalies. Exactly 1 event per season. |
| **20% drop** | 1 | 1.19% | Identifies only extreme crop failure (`ANAND_WHEAT_02` in 2022-23 at -27.01%). |

### 2. Historical Baseline Depth Requirement ($\ge 2$ prior seasons)
Restricting analysis to seasons where at least 2 historical seasons are available (seasons 2022-23, 2023-24, 2024-25; $N = 63$ rows):
- **Stressed count**: 3 rows (`ANAND_WHEAT_02` in 2022-23, `ANAND_WHEAT_01` in 2023-24, `ANAND_WHEAT_02` in 2024-25).
- **Stressed rate**: **4.76%** (identical rate to the full 84-row sample).

### 3. Sensitivity to Borderline Plots Exclusion
Excluding the 3 borderline plots (`ANAND_WHEAT_13`, `ANAND_WHEAT_14`, `TARAPUR_WHEAT_11`), leaving 18 core plots ($N = 72$ labelled rows):
- **Stressed count**: 4 rows (none of the 3 borderline plots ever triggered a stress label).
- **Stressed rate**: **5.56%** (4 / 72).

---

## 4. What Would Unlock ML Evaluation?

Machine learning evaluation cannot be unlocked by tweaking thresholds, hyperparameter grids, or resynthesizing labels. It can only be unlocked by **ground truth outcome data** and **substantive geographic/temporal expansion**:

1. **Panchayat/Village-Level Crop Insurance Claims**: Historical PMFBY payout records or loss ratios for Anand district Rabi wheat.
2. **Crop-Cutting Experiment (CCE) Yield Data**: Government or district agriculture department yield measurements per unit area.
3. **Anonymized Loan Repayment Records**: Commercial bank or Primary Agricultural Credit Society (PACS) Kisan Credit Card (KCC) delinquency/repayment outcomes.
4. **Geographic and Sample Expansion**: Expanding from 21 plots to 200+ verified smallholder wheat plots across diverse agro-climatic zones in Gujarat, observed over 5+ seasons.

> [!IMPORTANT]
> The availability and accessibility of these datasets remain **UNVERIFIED**. A structured field inquiry plan is documented in `docs/OUTCOME_DATA_PLAN.md`.

---

## 5. Synthetic Stress Policy

SatBhoomi includes capabilities for synthetic stress simulation (e.g., injecting synthetic vegetative decay or weather anomalies for what-if scenarios and alert pipeline demonstrations in Raksha).

- **Strict Constraint**: Synthetic stress data is permitted **STRICTLY for end-to-end alert pipeline testing, UI demonstration, and what-if scenario exploration**.
- **Prohibition**: Synthetic stress data must **NEVER be used to calculate model accuracy, train predictive models, claim ML validation, or satisfy the Feasibility Gate**.

---

## 6. Forbidden Claims & Scientific Integrity

To maintain strict compliance with SatBhoomi's radical honesty guidelines, the following statements and claims are **STRICTLY FORBIDDEN** in all project documentation, code comments, reports, and academic papers:

1. **Do NOT claim the model is "accurate", "validated", or "production-ready"**: With only 4 stressed events across 84 instances, statistical power is insufficient to validate predictive performance.
2. **Do NOT claim that satellite NDVI drop "predicts loan default"**: Satellite vegetation anomalies measure biophysical canopy greenness, not borrower willingness or ability to repay financial obligations.
3. **Do NOT claim that machine learning outperforms agronomic heuristics**: ML models cannot be reliably trained or evaluated on this distribution; the rules baseline remains the operative scorer.
4. **Do NOT conflate lack of stress signal with creditworthiness**: A thriving crop does not guarantee market realization, price stability, or debt repayment.
