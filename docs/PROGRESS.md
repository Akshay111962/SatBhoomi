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
| **T-05** | **Baseline and ML models**<br>Heuristic rules baseline, Logistic Regression, Random Forest, XGBoost models. | **SUPERSEDED** | Package `src/satbhoomi/risk/` (`baseline.py`, `models.py`, `evaluate.py`, `train.py`); CLI `scripts/train_models.py`; Makefile target `train`; pre-registered protocol in `docs/EVAL_PROTOCOL.md` (APPROVED); evaluated on 100% live dataset (24 plots $\times$ 5 seasons = 120 rows). **SUPERSEDED**: Computed on pre-correction NDVI without PB 04.00 offset (+1000 DN); model artifacts and metrics in `docs/MODEL_EVAL.md` and `reports/metrics.json` are superseded and ML training is frozen. Rules baseline stays active scorer. | 2026-11-12 |
| **T-06** | **SHAP reasons**<br>TreeSHAP / LinearSHAP feature attributions translated into top 3 plain reasons. | **SUPERSEDED** | Modules `src/satbhoomi/risk/scoring.py`, `explain.py`, `reason_templates.py`; CLI `scripts/score_plot.py` + Makefile `score`; `docs/SCORING.md` & `docs/RISKS.md`. Active scorer is `rules_baseline` (`AgronomicRulesBaseline`). **SUPERSEDED**: Scored outputs and example explanations were computed on pre-correction features. Code logic remains intact; downstream outputs require recomputation in a future task. | 2026-11-12 |
| **T-07** | **Loan suggestion rules**<br>Right-sized loan limits, harvest-aligned repayment schedules, crop insurance flags. | **SUPERSEDED** | Module `src/satbhoomi/risk/loan_suggestions.py`; CLI `scripts/score_plot.py --suggest-loan`; documentation in `docs/UNDERWRITING_RULES.md`. **SUPERSEDED**: Rule logic is intact (100% test coverage), but risk-band inputs and haircuts were evaluated against pre-correction risk scores. Recomputation deferred to future task. | 2026-11-13 |
| **T-08** | **What-if engine**<br>Simulator projecting risk score changes given controllable mitigations. | **SUPERSEDED** | Module `src/satbhoomi/risk/what_if.py`; CLI `scripts/score_plot.py --what-if-input <var> --what-if-val <val>`; documentation in `docs/WHAT_IF.md`. **SUPERSEDED**: Engine logic is intact, but baseline scores and delta evaluations were run on pre-correction features. Recomputation deferred to future task. | 2026-11-13 |
| **T-09** | **Alert engine and replay**<br>Raksha in-season stress monitoring and historical seasonal replay harness. | **SUPERSEDED** | Modules `src/satbhoomi/alerts/` (`config.py`, `models.py`, `engine.py`, `replay.py`); CLI `scripts/replay_alerts.py`; documentation in `docs/ALERTS.md` and `docs/RISKS.md` (RISK-04). **SUPERSEDED**: Alert engine and replay harness code intact (9/9 tests passing), but historical replay results were evaluated against uncorrected NDVI series (where drop was artificial). Historical replay requires re-running in a future task after data rebuild. | 2026-11-13 |
| **T-10** | **Database and API**<br>SQLAlchemy 2.0 schema, Alembic migrations, synthetic seed script, FastAPI REST endpoints. | **IN PROGRESS** | DB models, initial migration `35c220ad71ed`, and seed script exist. Versioned API contract v0.2.0 (Blueprint Section 8) aligned directly with verified domain result objects (`LoanSuggestionResult`, `WhatIfResult`, `AlertItem`, `EvaluationCheckpointResult`) via explicit adapter layer in `src/satbhoomi/api/adapters.py`. Deterministic OpenAPI specification exported to `docs/api/openapi.json` (v0.2.0). When `MOCK_API=false` (default), all business routes return 501 `NOT_IMPLEMENTED`. In mock mode (`MOCK_API=true`), returns typed synthetic datasets with `"synthetic": true`. Production startup guard refuses mock mode in production. 14/14 API contract, adapter, and mock integration tests passing with 90.11% total coverage; ADR-10 & ADR-11 documented in `docs/DECISIONS.md`; frontend handoff guide published in `docs/FRONTEND_HANDOFF.md`. | 2026-11-13 |
| **T-11** | **Dashboard**<br>Streamlit web application for bank officers (screens S1 through S9). | **IN PROGRESS** | Placeholder home page implemented in `src/satbhoomi/ui/app.py`. Full multi-screen dashboard S1–S9 paused behind Frontend Gate awaiting user branding and layout choices. | 2026-10-27 |
| **T-12** | **Playbook, relief report, farmer summary**<br>Supportive action playbooks, RBI 33% relief report generator, vernacular summaries. | **NOT STARTED** | `reports/` and `summary/` packages contain only empty `__init__.py` files. | 2026-11-04 |
| **T-13** | **Audit log, consent, security checks**<br>Audit logging, DPDP consent tracking & cascading erasure, pre-commit secret scans. | **IN PROGRESS** | ORM models `audit_log.py` and `consent.py` implemented; ADR-8 deletion strategy documented; pre-commit secrets detection configured. Full consent enforcement workflows pending. | 2026-10-27 |
| **T-14** | **Interviews, paper, demo**<br>Bank officer interviews, research paper draft (rules vs ML), video demo script. | **NOT STARTED** | No interview notes, academic paper drafts, or demo recordings present. | 2026-11-04 |

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

