# SatBhoomi Score + Raksha

> **AI farm credit scoring and early-warning decision-support tool for bank officers.**

[![CI](https://github.com/Akshay111962/SatBhoomi/actions/workflows/ci.yml/badge.svg)](https://github.com/Akshay111962/SatBhoomi/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code style: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

---

## Overview

Smallholder farmers frequently lack formal credit histories, forcing financial institutions to rely on slow, manual field appraisals or arbitrary lending caps. When unseasonal rains, drought, or mandi price collapses occur, repayment stress builds up silently until an installment is missed.

**SatBhoomi Score + Raksha** bridges this information gap by delivering an explainable, satellite-driven decision-support platform for bank officers:

1. **SatBhoomi Score (Pre-Disbursal Assessment)**:
   - Evaluates multi-season satellite vegetation indices (Sentinel-2 NDVI), rainfall anomalies (CHIRPS/NASA POWER), and local mandi prices.
   - Computes a calibrated **0–100 risk score** with low/medium/high risk banding.
   - Surfaces **top 3 plain-language reasons** via SHAP feature attribution.
   - Recommends right-sized loan limits, harvest-aligned repayment schedules, and mandatory crop insurance flags.
   - Features an interactive **What-If Simulator** to project score changes given interventions (e.g. drip irrigation, insurance).

2. **Raksha (In-Season Early-Warning & Relief Support)**:
   - Monitors active plots throughout the cropping season to detect crop health decline, rainfall deficits, or market price shocks.
   - Generates supportive action playbooks (field visits, claims guidance, restructuring under RBI guidelines) — strictly focusing on **repayment stress and support needed**.
   - Produces objective **Relief Evidence Reports** evaluating crop damage against the **RBI 33% calamity threshold** to facilitate timely debt rescheduling.

*For full product specifications and functional requirements (FR-001 to FR-014), refer to the [Product Blueprint](file:///d:/SatBhoomi/docs/blueprint.pdf).*

---

## Architecture & Project Structure

The codebase is organized as a typed **modular monolith** in Python:

```text
SatBhoomi/
├── .github/workflows/ci.yml       # GitHub Actions CI (lint, format, test)
├── data/                          # Data directory (gitignored)
│   ├── raw/                       # Raw satellite & meteorological datasets
│   ├── processed/                 # Engineered seasonal features
│   └── synthetic/                 # Synthetic & mock farmer profiles
├── docs/
│   ├── blueprint.pdf              # Full product blueprint (FR-001 to FR-014)
│   ├── PROJECT_CONTEXT.md         # Permanent project rules & ethical guidelines
│   └── DECISIONS.md               # Architecture Decision Records (ADR-1 to ADR-5)
├── scripts/                       # Operational and migration scripts
├── src/satbhoomi/
│   ├── config/                    # Settings loaded from environment variables
│   ├── connectors/                # External data connectors (satellite, rainfall, mandi, yield)
│   ├── features/                  # Feature engineering & caching pipeline
│   ├── risk/                      # Rules baseline, ML models, SHAP explanations
│   ├── alerts/                    # In-season stress detection & action playbooks
│   ├── api/                       # FastAPI application layer (REST endpoints)
│   ├── db/                        # SQLAlchemy 2.0 ORM (SQLite for PoC, PostgreSQL-ready)
│   ├── reports/                   # Relief evidence & PDF report generation
│   ├── summary/                   # Farmer-facing summaries in English, Gujarati, Hindi
│   └── ui/                        # Streamlit web dashboard for bank officers
└── tests/
    ├── conftest.py                # Shared fixtures (FastAPI TestClient, settings)
    ├── unit/                      # Unit tests (config, validation)
    └── integration/               # Integration tests (health endpoint, API contracts)
```

---

## Getting Started

### 1. Prerequisites
- **Python 3.11+** (Python 3.11, 3.12, or 3.13)
- `git`
- `make` (optional, PowerShell/Bash compatible)

### 2. Environment Setup

Clone the repository and set up a virtual environment:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies

Install the package in editable mode along with development and testing tooling:

```bash
pip install --upgrade pip
pip install -e ".[dev]"
```

Or using the Makefile:
```bash
make install
```

### 4. Configure Environment Variables

Copy the example environment configuration:

```bash
cp .env.example .env
```

---

## Running Quality Checks

### Run Linting & Formatting Checks

```bash
# Check code style and formatting
ruff check src tests
ruff format --check src tests

# Or with Make:
make lint
```

### Automatically Fix Formatting & Lint Issues

```bash
ruff format src tests
ruff check --fix src tests

# Or with Make:
make format
```

### Run Tests with Coverage

```bash
pytest --cov=src/satbhoomi tests/

# Or with Make:
make test
```

---

## Running the Application

### 1. Run FastAPI Backend
Start the FastAPI server on `http://localhost:8000`:

```bash
uvicorn satbhoomi.api.main:app --reload --host 0.0.0.0 --port 8000

# Or with Make:
make run-api
```

- Health Check endpoint: `http://localhost:8000/health`
- Interactive OpenAPI documentation: `http://localhost:8000/docs`

### 2. Run Streamlit UI
Launch the bank officer dashboard on `http://localhost:8501`:

```bash
streamlit run src/satbhoomi/ui/app.py

# Or with Make:
make run-ui
```

---

## Permanent Project Guardrails

Every contribution must adhere strictly to the rules documented in [docs/PROJECT_CONTEXT.md](file:///d:/SatBhoomi/docs/PROJECT_CONTEXT.md):

1. **Human-in-the-Loop**: The platform NEVER approves or rejects loans; bank officers make all credit determinations.
2. **Supportive Framing**: Language must describe "repayment stress" and "support needed" — never personal distress or mental state.
3. **Data Privacy**: No real farmer records in the repo; synthetic and mock datasets only.
4. **Zero Hardcoded Secrets**: All credentials must use environment variables.
5. **Score Traceability**: Model versions are captured with every score.
6. **What-If Simulations**: Outputs are explicitly marked "estimate", not proof of causation.
7. **Positioning**: Acknowledge existing solutions (e.g. SatSure); position SatBhoomi as "score to action".
8. **Engineering Integrity**: Never state code is tested unless tests were actually executed.
