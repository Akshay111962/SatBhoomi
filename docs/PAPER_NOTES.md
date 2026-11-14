# SatBhoomi Research Paper Notes: Findings, Limitations & Honest Wording

**Document Type**: Draft Manuscript Notes & Scientific Disclosures  
**Date**: November 2026  
**Target Submission / Working Paper**: Applied Earth Observation & Agricultural Risk Intelligence  
**Primary Sourced Reports**: `reports/ndvi_summary.json`, `reports/label_counts.json` (Rule 10 Traceable)  

---

## 1. Core Contribution: An Operational, Audit-Traceable Pipeline

SatBhoomi establishes a complete, open, and reproducible engineering pipeline for smallholder agricultural risk assessment:
- Ingests raw Copernicus Sentinel-2 L2A Harmonized STAC imagery, ERA5 reanalysis agro-meteorological metrics, and Agmarknet wholesale commodity prices.
- Implements strict temporal leakage boundaries: features are derived exclusively prior to the **January 31 stem elongation cut-off**, ensuring risk predictions reflect pre-harvest underwriting windows rather than post-harvest hindsight.
- Provides end-to-end provenance: every figure, table, and data split is deterministically reproducible from versioned scripts and SHA-256 data hashes.

---

## 2. Essential Earth Observation Finding: The Sentinel-2 PB 04.00+ Offset

A central empirical finding of this work is the critical necessity of harmonizing Sentinel-2 Level-2A radiometric processing baselines:

- **The Artifact**: On January 25, 2022, ESA deployed Processing Baseline (PB) 04.00, introducing a radiometric offset of $-1000$ Digital Numbers (DN) to surface reflectance bands to preserve negative reflectances for low-reflectance targets.
- **The Impact on Uncorrected Time Series** (Source: `reports/ndvi_summary.json`):
  - Without offset correction, the apparent mean peak NDVI across Anand wheat plots fell abruptly from **0.6172** in 2020-21 to **0.5497** in 2021-22 (-12.12%), and collapsed to **0.4209** in 2022-23 (-51.15%), **0.4235** in 2023-24 (-50.70%), and **0.4298** in 2024-25 (-48.28%).
  - In an uncorrected longitudinal baseline, this sensor processing artifact masquerades as catastrophic, persistent regional vegetative distress, falsely labeling 54 of 96 plot-seasons as stressed.
- **Post-Correction Harmonization**:
  - Restoring the true surface reflectance yields remarkably stable multi-year phenological trajectories: mean peak NDVI across the 21 plots is **0.6172** (2020-21), **0.6164** (2021-22), **0.6362** (2022-23), **0.6383** (2023-24), and **0.6372** (2024-25).
- **Paper Recommendation**: Any agricultural monitoring study or commercial fintech underwriting system spanning the 2021–2023 epoch that consumes Sentinel-2 L2A STAC items without explicit `BOA_ADD_OFFSET` correction will generate severe false-positive distress classifications.

---

## 3. Event Scarcity & The Feasibility of Machine Learning Validation

A frequent hazard in applied remote sensing literature is the uncritical training of machine learning classifiers on small samples with synthetic or proxy labels. SatBhoomi adopts a policy of radical transparency regarding statistical power:

- **Active Dataset Scale** (Source: `reports/label_counts.json`):
  - 21 active wheat plots across 5 completed Rabi seasons (105 plot-seasons total).
  - 2020-21 serves as the historical baseline initialization ($N=21$, unlabelled).
  - 84 labelled instances across 2021-22 through 2024-25.
- **Prevalence of Vegetative Stress**:
  - Under the pre-registered 15% relative peak NDVI drop rule ($\tau = 15\%$), only **4 instances of vegetative stress** are observed (4.76% event rate), exactly 1 per season.
  - In Anand district, smallholder wheat is cultivated in fertile alluvial plains under $>85\%$ tube-well and canal irrigation. Severe vegetative crop failure is genuinely rare under typical management.
- **The Feasibility Gate Decision**:
  - Held-out evaluation set (`2024-25`): **1 positive** observed vs. $\ge 5$ required.
  - Pooled cross-validation folds: **4 positives** observed vs. $\ge 10$ required.
  - **Verdict**: The dataset is **NOT EVALUABLE** for machine learning benchmarking. Training high-capacity non-linear classifiers (Random Forest, XGBoost) on 4 positive cases across 84 rows produces trivial variance artifacts and misleading performance metrics.
  - **Action**: In accordance with pre-registered protocol v2 (`docs/EVAL_PROTOCOL.md`), machine learning training is frozen.

---

## 4. Operational Role of the Agronomic Rules Baseline

Rather than presenting an unvalidated machine learning model, the project relies on **`AgronomicRulesBaseline`** as the active risk engine:
- Operates on transparent, domain-grounded physical heuristics (early canopy density `ndvi_early <= 0.35`, growth trajectory `ndvi_trend_pre_cutoff <= 0.0`, and agro-meteorological rainfall deficits `rain_pre_cutoff_deficit_pct <= -20%`).
- Transparently calibrated: outputs explicit risk bands (`low`, `medium`, `high`) without black-box parameters.
- Descriptive examination of the 4 stressed instances ($n=4$, descriptive only) shows that 3 of the 4 cases were flagged in the `medium` risk category due to early vegetative growth lag, while 1 case had normal early canopy development before a late-season peak drop.
- Rules baseline thresholds were formulated prior to radiometric offset correction and will undergo a formal agronomic re-examination in subsequent work.

---

## 5. Comparative Framing Against Commercial Benchmarks (e.g., SatSure SAGE / SPARTA)

When discussing commercial crop intelligence solutions (such as SatSure SAGE or SPARTA), the paper maintains scientific humility:
- We formulate differences between SatBhoomi and commercial platforms as **testable scientific hypotheses**, not competitive claims.
- Commercial systems often incorporate:
  1. Synthetic Aperture Radar (SAR / Sentinel-1) backscatter time series insensitive to cloud cover.
  2. Proprietary soil moisture and thermal evapotranspiration indices.
  3. Regional scale aggregation over tens of thousands of hectares.
  4. Proprietary historical loan repayment registers from banking partners.
- SatBhoomi's open-source architecture highlights what is achievable solely with open public Earth observation assets and publicly accessible data, demonstrating both the viability and the distinct data boundaries of purely open agricultural risk intelligence.

---

## 6. Honest Limitations & Research Frontier

The paper concludes with an unvarnished enumeration of research boundaries:
1. **Proxy Limitation**: Satellite vegetative anomalies measure greenness and canopy vigour, not borrower creditworthiness, harvest marketing price realization, or household debt dynamics.
2. **Sample Geographic Scope**: The current active set of 21 plots provides proof-of-concept pipeline validation in Anand district, but does not represent statewide agro-climatic variability across rainfed or semi-arid districts.
3. **Requirement for Ground Truth**: Overcoming the Feasibility Gate requires empirical ground truth (CCE yield surveys, PMFBY claim settlement ratios, or anonymized KCC repayment records), for which a field discovery plan has been pre-registered (`docs/OUTCOME_DATA_PLAN.md`).
