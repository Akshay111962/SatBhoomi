# SatBhoomi Score + Raksha — Blueprint Progress Tracker

This document tracks the implementation status of blueprint tasks **T-01 through T-14** for **SatBhoomi Score + Raksha**.

> **Mandatory Rule**: Update this file at the conclusion of every task. Never mark any task `DONE` without concrete evidence (such as passing automated test runs executed in the current session or verified implementation files). If verification cannot be executed, mark as `UNVERIFIED` and state the limitation openly.

---

## Progress Table

| Task | Description | Status | Evidence | Date |
| :--- | :--- | :--- | :--- | :--- |
| **T-01** | **Repo and CI**<br>Repository structure, tooling (ruff, pytest), GitHub Actions CI, dependencies. | **DONE** | Commit `c5e9eae`, `.github/workflows/ci.yml`, `pyproject.toml`, `.gitignore`, `Makefile`, `README.md` verified in repo. | 2026-10-27 |
| **T-02** | **Satellite NDVI fetch**<br>Sentinel-2 / Copernicus connector for multi-season NDVI time-series. | **DONE** | Package `src/satbhoomi/connectors/satellite/` (base, fixture, planetary, gee stub, loader, aggregate, seasons); CLI `scripts/fetch_ndvi.py`; dataset `data/processed/ndvi_plot_season.csv` rebuilt with PB 04.00 offset correction for 21 active plots (105 plot-seasons across 5 rabi seasons, 0 data gaps); unit tests passing; docs/DATA_SOURCES.md and docs/PLOT_SELECTION.md updated. | 2026-11-14 |
| **T-03** | **Rainfall, price and yield loaders**<br>CHIRPS / NASA POWER rainfall, AGMARKNET mandi prices, district yield data. | **DONE** | Packages `connectors/rainfall/`, `connectors/mandi/`, `connectors/yield_stats/`; CLIs `scripts/fetch_rainfall.py`, `scripts/fetch_prices.py`, `scripts/build_dataset.py`; dataset `data/processed/season_dataset.csv` rebuilt for 21 active plots across 5 seasons (105 rows, 100% complete, 0 data gaps); 100% non-fixture live data provenance; `docs/DATA_SOURCES.md` updated. | 2026-11-14 |
| **T-04** | **Features and proxy label**<br>Multi-season feature engineering pipeline and synthetic proxy default label. | **DONE** | Package `src/satbhoomi/features/` (`config.py`, `label.py`, `build_features.py`); CLI `scripts/build_features.py`; dataset `data/processed/features.csv` rebuilt for 21 active plots across 5 seasons (105 rows: 21 unlabelled historical initialization + 84 labelled rows [4 stressed, 80 normal]); automated Truncation Test proving zero temporal leakage; documentation in `docs/LABEL_RULE.md`, `docs/FEATURES.md`, `docs/NDVI_CORRECTION.md`, and `docs/PLOT_SELECTION.md`. | 2026-11-14 |
| **T-05** | **Baseline and ML models**<br>Heuristic rules baseline, Logistic Regression, Random Forest, XGBoost models. | **CURRENT** | Package `src/satbhoomi/risk/` (`config.py`, `baseline.py`, `models.py`, `evaluate.py`, `train.py`). Active scorer updated to **`AgronomicRulesBaseline` v2.0 (`satbhoomi-rules-v2.0-relative-20261114`)** implementing relative NDVI drop ($\ge 15\%$ moderate, $\ge 25\%$ acute) and differentiated rainfall deficit ($\le -25\%$ on rainfed tracts; secondary on irrigated tracts) per approved review (`docs/SCORER_REVIEW.md`). Season 1 (`2020-21`) strictly returns `insufficient_data`. All thresholds centralized in `src/satbhoomi/risk/config.py`. ML model training remains frozen under Evaluation Protocol v2 Feasibility Gate (`docs/EVAL_PROTOCOL.md`). Unit tests passing in `tests/unit/test_rules_v2.py`. | 2026-11-14 |
| **T-06** | **Explainable reasons & scoring**<br>Exact additive probability contributions translated into top 3 plain reasons. | **CURRENT** | Modules `src/satbhoomi/risk/scoring.py`, `explain.py`, `reason_templates.py`; CLI `scripts/score_plot.py` + `scripts/analysis/recompute_scores.py`; `docs/SCORING.md`. Active scorer is `rules_baseline` (`satbhoomi-rules-v2.0-relative-20261114`). Recomputed scores across all 105 active plot-seasons saved in `reports/scores_summary.json`: 21 `insufficient_data` (Season 1), 73 `low` (86.9%), 9 `medium` (10.7%), 2 `high` (2.4%). Zero plots permanently flagged across all seasons (flag persistence: 0 in 4 seasons, 0 in 3 seasons, 1 in 2 seasons, 9 in 1 season, 11 in 0 seasons). Exact additivity ($base + \sum contributions == p$) and zero blame language verified. | 2026-11-14 |
| **T-07** | **Loan suggestion rules**<br>Right-sized loan limits, harvest-aligned repayment schedules, crop insurance flags. | **CURRENT** | Module `src/satbhoomi/risk/loan_suggestions.py`; CLI `scripts/score_plot.py --suggest-loan`; `docs/UNDERWRITING_RULES.md`. All underwriting parameters centralized in `src/satbhoomi/risk/config.py`. Sizing haircuts aligned with v2.0 risk bands. Season 1 returns `manual_appraisal_required`. Verified examples documented in `reports/scores_summary.json` and unit tests passing in `tests/unit/test_loan_suggestions.py`. | 2026-11-14 |
| **T-08** | **What-if engine**<br>Simulator projecting risk score changes given controllable mitigations. | **CURRENT** | Module `src/satbhoomi/risk/what_if.py`; CLI `scripts/score_plot.py --what-if-input <var> --what-if-val <val>`; `docs/WHAT_IF.md`. Schema updated with `effect_basis` (`scorer_input`, `scenario_assumption`, `not_modelled`) and `assumption` fields. Zero-delta behavior cleanly documented. Recomputed simulation examples saved in `reports/scores_summary.json`. 17/17 tests passing in `tests/unit/test_what_if.py`. | 2026-11-14 |
| **T-09** | **Alert engine and replay**<br>Raksha in-season stress monitoring and historical seasonal replay harness. | **CURRENT** | Modules `src/satbhoomi/alerts/` (`config.py`, `models.py`, `engine.py`, `replay.py`); CLI `scripts/replay_alerts.py`; `docs/ALERTS.md`. Historical replay recomputed across 21 active plots on corrected data and saved in `reports/replay_alerts.json` (46 total alerts: 34 crop health, 12 rainfall, 0 price). TC-007 synthetic stress scenario passes with 11.0 weeks early warning lead time before harvest. | 2026-11-14 |
| **T-10** | **Database and API**<br>SQLAlchemy 2.0 schema, Alembic migrations, synthetic seed script, FastAPI REST endpoints. | **IN PROGRESS** | T-10 part 2: assessments (`POST /plots/{id}/assessments`, `GET /assessments/{id}`) and what-if (`POST /assessments/{id}/what-if`) real; monitoring and alert actions pending. Alembic migration `f1a2b3c4d5e6` applied (status, nullable score/band, idempotency key on assessment; result_json on what_if). Contract v0.3.0 additive field `cutoff_date_iso` implemented. In-memory integration tests passing in `tests/unit/test_real_assessments_what_if.py`. | 2026-11-15 |
| **T-11** | **Dashboard**<br>Streamlit web application for bank officers (screens S1 through S9). | **IN PROGRESS** | Placeholder home page implemented in `src/satbhoomi/ui/app.py`. Full multi-screen dashboard S1–S9 paused behind Frontend Gate awaiting user branding and layout choices. | 2026-10-27 |
| **T-12** | **Playbook, relief report, farmer summary**<br>Supportive action playbooks, RBI 33% relief report generator, vernacular summaries. | **NOT STARTED** | `reports/` and `summary/` packages contain only empty `__init__.py` files. | 2026-11-04 |
| **T-13** | **Audit log, consent, security checks**<br>Audit logging, DPDP consent tracking & cascading erasure, pre-commit secret scans. | **IN PROGRESS** | ORM models `audit_log.py` and `consent.py` implemented; ADR-8 deletion strategy documented; pre-commit secrets detection configured. Full consent enforcement workflows pending. | 2026-10-27 |
| **T-14** | **Interviews, paper, demo**<br>Bank officer interviews, research paper draft (rules vs ML), video demo script. | **IN PROGRESS** | Ground-truth outcome data discovery plan and interview questions published in `docs/OUTCOME_DATA_PLAN.md` (unverified research questions). Honest research paper findings, disclosures, and limitations drafted in `docs/PAPER_NOTES.md` (sourced from `reports/label_counts.json` and `reports/ndvi_summary.json`). | 2026-11-14 |

---

## Status Legend
- **NOT STARTED**: No implementation exists.
- **IN PROGRESS**: Partial implementation exists (e.g., schemas or placeholders defined, full functionality pending).
- **DONE**: Fully implemented, verified against acceptance criteria with passing test evidence.
- **SUPERSEDED**: Implementation or artifact was completed against pre-correction satellite data and is superseded pending data rebuild and protocol revisit.

---

## Downstream Artifacts Superseded by Sentinel-2 PB 04.00 Correction & Plot Exclusion (R1)

The discovery of the uncorrected ESA Sentinel-2 Processing Baseline 04.00 radiometric offset (+1000 DN from 25 January 2022) and the subsequent uniform exclusion of 3 persistent non-crop plots (`PETLAD_WHEAT_05`, `UMRETH_WHEAT_09`, `KHAMBHAT_WHEAT_12` per `docs/PLOT_SELECTION.md`) updated the upstream feature dataset to 21 active plots (105 plot-seasons). 

### Disclosures & Ground Data Limitations:
- **Sample Centroids, Not Real Farmers**: Sample plots represent spatial centroids in Anand district, not individual surveyed farmers or land registry records.
- **Unverified Ground Truth Crop Type**: Crop cover has not been physically verified on the ground for any plot.
- **Assigned Static Attributes**: `irrigation` and `insured` are assigned experimental attributes, not verified ground records.

The following downstream artifacts were derived from pre-correction data and/or the old 24-plot set and are **SUPERSEDED** (marked as needing recomputation in a future task; do not recompute in this task):

1. **Model Training & Evaluation Artifacts (T-05)**:
   - Serialized model: `models/satbhoomi-risk-v1.0-logreg-feat1-opt1th15-8bac5ab0-20261112.joblib`
   - Model metadata: `models/satbhoomi-risk-v1.0-logreg-feat1-opt1th15-8bac5ab0-20261112.meta.json`
   - Evaluation metrics: `reports/metrics.json`
   - Benchmark report: `docs/MODEL_EVAL.md`
2. **SHAP Explanations & Scoring Examples (T-06)**:
   - Example score runs and SHAP factor attributions in `docs/SCORING.md`
3. **Loan Suggestion Evaluations (T-07)**:
   - Evaluated loan haircuts and limit bands in `docs/UNDERWRITING_RULES.md`
4. **What-If Simulations (T-08)**:
   - Baseline risk scores and simulated delta values in `docs/WHAT_IF.md`
5. **In-Season Alert Replay Runs (T-09)**:
   - Historical replay alert logs and event counts in `docs/ALERTS.md`

### Rules Baseline Threshold Review Requirement (Next Task):
The `AgronomicRulesBaseline` thresholds (`ndvi_early <= 0.35`, `ndvi_trend_pre_cutoff <= 0.0`, `rain_pre_cutoff_deficit_pct <= -20%`) were established prior to the Sentinel-2 PB 04.00+ radiometric offset correction and non-crop plot exclusion. Because wheat in Anand is $>85\%$ tube-well/canal irrigated, winter rainfall anomalies have limited direct correlation with crop vigour. These heuristic thresholds must be formally reviewed from agronomic reasoning and corrected distributions in the next scheduled task. No threshold or scorer code is modified in this documentation task.


