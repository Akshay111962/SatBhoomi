# Frontend Handoff Guide: SatBhoomi API Contract (v0.2.0)

This document serves as the integration contract and onboarding guide for frontend developers building the **React web app** and **Streamlit dashboard** for **SatBhoomi Score + Raksha**.

> **Crucial Rule**: Both the React and Streamlit frontends must consume the same versioned API contract (`/api/v1`). Neither frontend may invent endpoints, bypass the contract, or write business logic directly in UI code.

> **CRITICAL DECISION-SUPPORT NOTICE**:
> Scores, risk bands, and indicative credit limits originate from an agronomic research prototype calibrated on regional sample data. They are decision-support aids for bank loan officers only—**never an automated bank credit decision**.
> **The UI must NEVER display an "Approve Loan" or "Reject Loan" button or workflow action.**

---

## 0. What Changed in Contract v0.2.0 (Breaking Changes & Screen Impact)

Release `0.2.0` aligns the API contract directly with the verified domain objects in `src/satbhoomi/risk/` and `src/satbhoomi/alerts/` via an explicit adapter layer.

### Breaking Field & Shape Renames
1. **Screen S4 (Assessment Result — Loan Suggestion)**:
   - **Old Shape**: Preliminary `DraftLoanSuggestion` with flat `suggested_limit_inr: float` and `risk_haircut_pct: float`.
   - **New Shape**: `LoanSuggestionResponse` mirroring `LoanSuggestionResult` (T-07):
     - `limit_band`: Structured object with `min_amount_inr` (int), `max_amount_inr` (int), `scale_of_finance_per_acre_inr` (int), `gross_scale_limit_inr` (int), `collateral_free_cap_applied` (bool), and `haircut_percentage_range` (str).
     - `repayment_schedule`: Structured object with `repayment_month` (str), `schedule_type` (str), `harvest_window` (str), `marketing_window` (str), and `rationale` (str).
   - **Status**: Promoted to **STABLE** (T-07 is verified DONE).
2. **Screen S5 (What-If Simulator)**:
   - **Field Renames**:
     - `original_score` $\to$ `old_score` (int)
     - `simulated_score` $\to$ `new_score` (int)
     - `original_band` $\to$ `old_band` ("low" | "medium" | "high")
     - `simulated_band` $\to$ `new_band` ("low" | "medium" | "high")
     - `causation_disclaimer` $\to$ `disclaimer` (str)
   - **New Fields**:
     - `old_limit_band` & `new_limit_band` (`LimitBand | None`): Shows projected credit limit impact under intervention.
     - `effect_basis`: Enum (`scorer_input`, `scenario_assumption`, `not_modelled`).
     - `assumption`: Detailed text if `effect_basis == "scenario_assumption"` (e.g. secondary watering timing).
     - `reliability_note`: Model validation status disclosure.
   - **Status**: Promoted to **STABLE** (T-08 is verified DONE).
3. **Screen S6 (In-Season Monitoring & Alerts)**:
   - Replaced preliminary flags (`data_gap_flag`, `data_gap_note`) with `status` (`ok` | `data_gap`), `data_gap_reason`, `checkpoint_label`, and `evaluation_date` mirroring `EvaluationCheckpointResult` (T-09).
   - `AlertSummary` fields mirror `AlertItem` and Alert ORM check constraints (`severity`: `low` | `medium` | `high`; `status`: `open` | `acknowledged` | `resolved` | `dismissed`), with `data_gap_warning` support.
   - **Status**: Promoted to **STABLE** for monitoring time-series and alert detection.
4. **Screens S7, S8, S9**:
   - `AlertActionRequest` & `AlertActionResponse` (S7): Kept **DRAFT** (playbooks finalised in T-12).
   - `ReliefReportResponse` (S8): Kept **DRAFT** (relief report generator finalised in T-12).
   - `FarmerSummaryResponse` (S9): Kept **DRAFT** (vernacular generator finalised in T-12).

---

## 1. Quickstart: Running the Mock API Locally

The mock API runs on FastAPI with zero database dependencies in mock mode.

### PowerShell Command (Windows)
```powershell
# Set mock mode flag and start uvicorn
$env:MOCK_API="true"
.venv\Scripts\python.exe -m uvicorn satbhoomi.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Make Equivalent (Linux/macOS)
```bash
make run-api-mock
```

* **Base URL**: `http://localhost:8000/api/v1`
* **Swagger UI (Interactive Docs)**: `http://localhost:8000/docs`
* **Health Check**: `http://localhost:8000/health`
* **OpenAPI Specification**: [`docs/api/openapi.json`](file:///d:/SatBhoomi/docs/api/openapi.json)

---

## 2. Authentication & Authorization in Mock Mode

* **Fake Token**: Pass `Authorization: Bearer mock-officer-token-xyz` on all protected routes.
* **Login Endpoint**: `POST /api/v1/auth/login`
  * Any username/password combination succeeds and returns `mock-officer-token-xyz`, except `password="wrong_password"` which triggers a `401 INVALID_CREDENTIALS` error for testing.
* **Security Disclaimer**: This token is strictly for local synthetic prototyping. It is not reusable as real authentication.

---

## 3. Endpoints Status & Screen Mapping

This table maps the **9 UI screens (S1–S9)** defined in Blueprint Section 5 to the corresponding API v1 endpoints.

| Screen ID | Screen Name | HTTP Method & Path | Contract Status | Notes & Guardrails |
| :--- | :--- | :--- | :---: | :--- |
| **S1** | Login | `POST /api/v1/auth/login` | **STABLE** | Returns bearer token. Simulates 401 on `wrong_password`. |
| **S2** | Dashboard | `GET /api/v1/plots?limit=10&offset=0` | **STABLE** | Paginated plot envelope (`items`, `total`, `limit`, `offset`). |
| **S3** | Add / Select Plot | `POST /api/v1/plots` | **STABLE** | Validates `area_acre > 0`. |
| **S4** | Assessment Result | `POST /api/v1/plots/{id}/assessments`<br>`GET /api/v1/assessments/{id}` | **STABLE** | Evaluates credit score. Returns score, band, exactly 3 reasons, `protective_factor`, and indicative `loan_suggestion` with structured `limit_band` and `repayment_schedule`. |
| **S5** | What-If Simulator | `POST /api/v1/assessments/{id}/what-if` | **STABLE** | Simulates `insured`, `irrigation`, `supplementary_irrigation`. Returns `old_score`, `new_score`, `score_delta`, `old_limit_band`, `new_limit_band`, `effect_basis`, and `assumption`. Mandatory `"estimate"` label. |
| **S6** | Monitoring & Alerts | `GET /api/v1/plots/{id}/monitoring` | **STABLE** | In-season timeline of NDVI/rain, data-gap status, active alerts matching `AlertItem` and database ORM enums. |
| **S7** | Alert Action Playbook | `POST /api/v1/alerts/{id}/actions` | **DRAFT** | Audited logging of supportive loan officer visits and relief actions. Finalised in T-12. |
| **S8** | Relief Evidence Report| `GET /api/v1/plots/{id}/relief-report` | **DRAFT** | Before/after NDVI, loss band vs. RBI 33% threshold. Mandatory disclaimer. Finalised in T-12. |
| **S9** | Farmer Vernacular Summary | `GET /api/v1/assessments/{id}/farmer-summary?lang=en\|gu\|hi` | **DRAFT** | Plain-language summaries in English (`en`), Gujarati (`gu`), and Hindi (`hi`). Finalised in T-12. |

---

## 4. Standard Error Response Envelope

All API errors return standard HTTP status codes (`400`, `401`, `403`, `404`, `429`, `500`, `501`) and conform strictly to the blueprint error schema:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "area_acre must be above 0",
    "field": "area_acre"
  }
}
```

### Mock Error Simulation Triggers
Frontend developers can test error states by:
* Supplying header `X-Mock-Error: <status_code>` (e.g. `X-Mock-Error: 429`).
* Requesting sentinel IDs: `id=999` (404 Not Found), `id=400` (400 Bad Request), `id=403` (403 Forbidden).

---

## 5. Non-Negotiable UI Design Rules (PROJECT_CONTEXT.md)

1. **Colour is Never the Only Signal**:
   * Risk bands (`low`, `medium`, `high`) and alert severities must **always include clear text labels**, not just green/amber/red colours (accessibility requirement).
2. **What-If Results Must Be Labeled "Estimate"**:
   * Any score produced by the what-if simulator must be prominently labeled as an **"estimate"** on screen, accompanied by the causation disclaimer (*"What-if simulations show model sensitivity under prospective mitigations; they do not prove causation."*).
3. **Relief Report Must Display Statutory Disclaimer**:
   * Screen S8 must always display: *"Official crop loss assessment and calamity declaration remain strictly with government and bank relief committees."*
4. **No Loan Approval or Rejection Actions**:
   * The UI **must never display an "Approve Loan" or "Reject Loan" button**. The tool is purely an explanatory decision-support aid; human loan officers log their own independent decisions in bank core systems.
5. **Strict Ethical Language (Rule 2)**:
   * Use strictly **"farm stress"**, **"repayment stress"**, and **"support needed"**.
   * Never display mental health terms, psychological diagnoses, or accusatory language towards farmers.
6. **No Personal Identifying Information (PII)**:
   * The UI must never request or display national identity numbers (Aadhaar, PAN), bank account numbers, or phone numbers. Only synthetic farmer codes (`Farmer-001`) and plot codes (`PLOT-001`) are used.

