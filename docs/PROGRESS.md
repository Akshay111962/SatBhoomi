# SatBhoomi Score + Raksha — Blueprint Progress Tracker

This document tracks the implementation status of blueprint tasks **T-01 through T-14** for **SatBhoomi Score + Raksha**.

> **Mandatory Rule**: Update this file at the conclusion of every task. Never mark any task `DONE` without concrete evidence (such as passing automated test runs executed in the current session or verified implementation files). If verification cannot be executed, mark as `UNVERIFIED` and state the limitation openly.

---

## Progress Table

| Task | Description | Status | Evidence | Date |
| :--- | :--- | :--- | :--- | :--- |
| **T-01** | **Repo and CI**<br>Repository structure, tooling (ruff, pytest), GitHub Actions CI, dependencies. | **DONE** | Commit `c5e9eae`, `.github/workflows/ci.yml`, `pyproject.toml`, `.gitignore`, `Makefile`, `README.md` verified in repo. | 2026-10-27 |
| **T-02** | **Satellite NDVI fetch**<br>Sentinel-2 / Copernicus connector for multi-season NDVI time-series. | **DONE** | Package `src/satbhoomi/connectors/satellite/` (base, fixture, planetary, gee stub, loader, aggregate, seasons); CLI `scripts/fetch_ndvi.py`; dataset `data/processed/ndvi_plot_season.csv` generated (15 records); 11/11 satellite unit tests passing; 81% test coverage; docs/DATA_SOURCES.md created. | 2026-11-04 |
| **T-03** | **Rainfall, price and yield loaders**<br>CHIRPS / NASA POWER rainfall, AGMARKNET mandi prices, district yield data. | **DONE** | Packages `connectors/rainfall/`, `connectors/mandi/`, `connectors/yield_stats/`; CLIs `scripts/fetch_rainfall.py`, `scripts/fetch_prices.py`, `scripts/build_dataset.py`; Makefile targets added; `data/processed/season_dataset.csv` generated (60 rows, 12 plots x 5 seasons, 100% complete); 49/49 tests passing offline in 2.54s; `docs/DATA_SOURCES.md` updated with leakage prevention warnings and full schemas. | 2026-11-04 |
| **T-04** | **Features and proxy label**<br>Multi-season feature engineering pipeline and synthetic proxy default label. | **NOT STARTED** | `src/satbhoomi/features/__init__.py` is empty; no feature extractors exist. | 2026-11-04 |
| **T-05** | **Baseline and ML models**<br>Heuristic rules baseline, Logistic Regression, Random Forest, XGBoost models. | **NOT STARTED** | `src/satbhoomi/risk/__init__.py` is empty; no scoring engines present. | 2026-11-04 |
| **T-06** | **SHAP reasons**<br>TreeSHAP / LinearSHAP feature attributions translated into top 3 plain reasons. | **NOT STARTED** | No explainer modules implemented in `src/satbhoomi/risk/`. | 2026-11-04 |
| **T-07** | **Loan suggestion rules**<br>Right-sized loan limits, harvest-aligned repayment schedules, crop insurance flags. | **NOT STARTED** | No underwriting suggestion logic implemented. | 2026-11-04 |
| **T-08** | **What-if engine**<br>Simulator projecting risk score changes given controllable mitigations. | **NOT STARTED** | ORM model `db/models/what_if.py` exists; simulator computation engine missing. | 2026-11-04 |
| **T-09** | **Alert engine and replay**<br>Raksha in-season stress monitoring and historical seasonal replay harness. | **NOT STARTED** | ORM model `db/models/alert.py` exists; `alerts/__init__.py` is empty. | 2026-11-04 |
| **T-10** | **Database and API**<br>SQLAlchemy 2.0 schema, Alembic migrations, synthetic seed script, FastAPI REST endpoints. | **IN PROGRESS** | DB models, Alembic initial migration `35c220ad71ed_initial_schema.py`, seed script `scripts/seed_synthetic.py` exist (commit `da12551`). API `/health` endpoint exists in `main.py`; domain REST endpoints pending. *(Local test suite run in Windows sandbox failed with handle exception 0xc0000008, so full automated test verification remains unverified in this session).* | 2026-10-27 |
| **T-11** | **Dashboard**<br>Streamlit web application for bank officers (screens S1 through S9). | **IN PROGRESS** | Placeholder home page implemented in `src/satbhoomi/ui/app.py`. Full multi-screen dashboard S1–S9 paused behind Frontend Gate awaiting user branding and layout choices. | 2026-10-27 |
| **T-12** | **Playbook, relief report, farmer summary**<br>Supportive action playbooks, RBI 33% relief report generator, vernacular summaries. | **NOT STARTED** | `reports/` and `summary/` packages contain only empty `__init__.py` files. | 2026-11-04 |
| **T-13** | **Audit log, consent, security checks**<br>Audit logging, DPDP consent tracking & cascading erasure, pre-commit secret scans. | **IN PROGRESS** | ORM models `audit_log.py` and `consent.py` implemented; ADR-8 deletion strategy documented; pre-commit secrets detection configured. Full consent enforcement workflows pending. | 2026-10-27 |
| **T-14** | **Interviews, paper, demo**<br>Bank officer interviews, research paper draft (rules vs ML), video demo script. | **NOT STARTED** | No interview notes, academic paper drafts, or demo recordings present. | 2026-11-04 |

---

## Status Legend
- **NOT STARTED**: No implementation exists.
- **IN PROGRESS**: Partial implementation exists (e.g., schemas or placeholders defined, full functionality pending).
- **DONE**: Fully implemented, verified against acceptance criteria with passing test evidence.
- **UNVERIFIED**: Implementation exists in codebase but test execution could not be verified in current environment.
