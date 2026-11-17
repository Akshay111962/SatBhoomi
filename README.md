# SatBhoomi Score + Raksha

> **AI farm credit scoring and early-warning decision-support tool for bank loan officers.**

[![CI](https://github.com/Akshay111962/SatBhoomi/actions/workflows/ci.yml/badge.svg)](https://github.com/Akshay111962/SatBhoomi/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## What It Is & What It Is Not

### What It Is
- **Explainable Decision-Support System**: Assists bank loan officers in appraising smallholder farm credit risk and managing in-season agricultural distress.
- **Pre-Disbursal Scoring (SatBhoomi Score)**: Combines multi-season Sentinel-2 NDVI, NASA POWER / CHIRPS precipitation, and APMC mandi price volatility to generate an explainable 0–100 risk score, risk band, top 3 plain-language reasons, right-sized loan limit suggestions, and what-if sensitivity simulations.
- **In-Season Monitoring & Relief (Raksha)**: Tracks crop health and winter rainfall deficits, triggering supportive action playbooks (field visits, restructuring) and objective calamity evidence reports benchmarked against the statutory **RBI 33% crop loss threshold**.

### What It Is NOT
- **NOT an Automated Loan Decision System**: SatBhoomi **never approves or rejects loans**. Bank officers retain sole underwriting and sanction authority.
- **NOT Live Streaming Telemetry**: In-season monitoring operates on precomputed historical seasonal replays with temporal truncation; it is not real-time live satellite telemetry.
- **NOT Validated on Real Bank Defaults**: Models are calibrated on proxy vegetative stress labels; no commercial loan default ground truth is present.
- **NOT Real Farmer Records**: All farmer identities, land parcels, and plot boundaries are anonymized synthetic coordinates and centroids in Anand, Gujarat.
- **NOT Legal Advice**: DPDP Act compliance features align with technical principles but do not constitute legal certification or formal legal advice.

---

## Architecture

```text
+--------------------------------------------------------------------------+
|                     Streamlit Web Dashboard (S1 to S9)                   |
| (Officer Login, Portfolio, Assessment, What-If, Alerts, Relief Evidence) |
+--------------------------------------------------------------------------+
                                    │  HTTP / JSON
                                    ▼
+--------------------------------------------------------------------------+
|                  FastAPI REST Backend (API Contract v0.6.0)               |
|      (Auth & Lockout, Plot Ingestion, Scoring, What-If, Monitoring)      |
+--------------------------------------------------------------------------+
       │                             │                             │
       ▼                             ▼                             ▼
+---------------+             +---------------+             +--------------+
| Risk Engine   |             | Raksha Alerts |             | Features     |
| - Rules v2.0  |             | - NDVI Drop   |             | - Sentinel-2 |
| - What-If Sim |             | - Rain Deficit|             | - NASA POWER |
| - SHAP Reasons|             | - RBI 33% Loss|             | - AGMARKNET  |
+---------------+             +---------------+             +--------------+
       │                             │                             │
       +─────────────────────────────┼─────────────────────────────+
                                     │  SQLAlchemy 2.0 (ORM)
                                     ▼
+--------------------------------------------------------------------------+
|                SQLite Database (WAL Mode, Enforced Foreign Keys)         |
|  - Relational Schema (PostgreSQL-ready ANSI SQL types via Alembic)       |
|  - Immutable Audit Ledger (SQLite triggers blocking UPDATE / DELETE)     |
+--------------------------------------------------------------------------+
```

---

## Quick Start (Demo Setup)

The demo runs completely offline from local data using an isolated demonstration database:

### 1. Provision Demo Database
Run the automated setup script to create a fresh demo database (`data/satbhoomi_demo.db`), apply migrations, create a secure loan officer account, and import sample plots, pre-cutoff features, and alert replay:

```powershell
# PowerShell:
powershell -ExecutionPolicy Bypass -File scripts/demo_setup.ps1 -Reset

# Or using Make:
make demo-setup
```
*(Enter a secure password for `demo_officer` when prompted, minimum 12 characters).*

### 2. Start Services

Open two separate terminals:

**Terminal 1 — Backend API**:
```powershell
$env:DATABASE_URL = "sqlite:///./data/satbhoomi_demo.db"
.venv\Scripts\uvicorn.exe satbhoomi.api.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — Streamlit Frontend**:
```powershell
.venv\Scripts\streamlit.exe run src/satbhoomi/ui/app.py --server.port 8501
```

### 3. Verify System Health (Demo Check)
In a third terminal, run the one-command offline pre-flight check:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/demo_check.ps1
```

Access the user interface at [http://localhost:8501](http://localhost:8501) and API interactive documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

---

## Known Limitations

1. **Proxy Stress Label**: In the absence of real commercial bank loan default records, the system uses an objective proxy vegetative stress label derived from multi-season NDVI drops and yield anomalies.
2. **Synthetic Sample Points**: The 21 sample plots represent spatial centroids in Anand district, Gujarat, not verified land registry titles or surveyed individual farmers.
3. **ML Evaluation Frozen**: Due to low event scarcity in the 21-plot sample (only 4 stressed instances across 84 labelled observations), ML models (Logistic Regression, Random Forest, XGBoost) failed statistical feasibility criteria (held-out $\text{AUC} < 0.70$). Model training is frozen under Evaluation Protocol v2, and the transparent agronomic **Rules Baseline v2.0** (`rules_baseline_2.0`) is the active operational scorer.
4. **Sentinel-2 PB 04.00+ Radiometric Offset**: An ESA processing baseline shift (+1000 DN after January 2022) was identified and uniformly corrected across raw observation caches, with 3 persistent non-crop plots excluded under pre-declared Rule R1.
5. **In-Season Monitoring Is Replay**: The monitoring module executes offline historical seasonal replay with temporal truncation to ensure zero future data leakage. It does not ingest live streaming satellite passes.
6. **Unreviewed Vernacular Summaries**: Farmer-facing loan summaries in Gujarati and Hindi are generated from fixed templates and require human loan officer review before distribution.
7. **Representative Underwriting Parameters**: Scale of Finance rates (₹28,000/acre irrigated, ₹18,000/acre rainfed) and haircut bands are calibrated on regional guidance and must be aligned with partner bank internal credit circulars prior to production deployment.
8. **Prototype Security**: Authentication employs Argon2id password hashing, account lockout (5 failed attempts), and signed JWT bearer tokens. While SQLite immutability triggers protect the audit ledger, enterprise deployment requires dedicated key management and relational PostgreSQL backing.

---

## Documentation Index

- [docs/DEMO_RUNSHEET.md](docs/DEMO_RUNSHEET.md): 6–7 minute step-by-step demonstration run sheet, click sequence, and talk tracks.
- [docs/PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md): Permanent non-negotiable ethical, architectural, and development rules.
- [docs/FRONTEND_HANDOFF.md](docs/FRONTEND_HANDOFF.md): REST API Contract (v0.6.0) specifications and frontend integration guide.
- [docs/SECURITY_CHECKLIST.md](docs/SECURITY_CHECKLIST.md): Blueprint Section 10 threat matrix and technical mitigations.
- [docs/TEST_STATUS.md](docs/TEST_STATUS.md): Blueprint test cases TC-001 through TC-011 execution status.
- [docs/DECISIONS.md](docs/DECISIONS.md): Architecture Decision Records (ADR-1 through ADR-10).
- [docs/PROGRESS.md](docs/PROGRESS.md): Task-by-task implementation status and verification evidence.
- [docs/RISKS.md](docs/RISKS.md): Project risk register and mitigation protocols.
- [docs/SCORER_REVIEW.md](docs/SCORER_REVIEW.md): Agronomic review and relative scoring methodology for Rules Baseline v2.0.
- [docs/ALERTS.md](docs/ALERTS.md): In-season stress detection rules, threshold calibration, and historical replay logs.
