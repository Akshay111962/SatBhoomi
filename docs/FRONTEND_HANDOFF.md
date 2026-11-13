# Frontend Handoff Guide: SatBhoomi API Contract v1 (Mock Mode)

This document serves as the integration contract and onboarding guide for frontend developers building the **React web app** and **Streamlit dashboard** for **SatBhoomi Score + Raksha**.

> **Crucial Rule**: Both the React and Streamlit frontends must consume the same versioned API contract (`/api/v1`). Neither frontend may invent endpoints, bypass the contract, or write business logic directly in UI code.

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
| **S4** | Assessment Result | `POST /api/v1/plots/{id}/assessments`<br>`GET /api/v1/assessments/{id}` | **STABLE** | Evaluates credit score. Returns score, band, exactly 3 reasons, `protective_factor`, and `loan_suggestion` (**DRAFT**). |
| **S5** | What-If Simulator | `POST /api/v1/assessments/{id}/what-if` | **DRAFT** | Simulates `insured`, `irrigation`. Mandatory `"estimate"` label. |
| **S6** | Monitoring & Alerts | `GET /api/v1/plots/{id}/monitoring` | **DRAFT** | In-season timeline of NDVI/rain, data-gap flags, active alerts list. |
| **S7** | Alert Action Playbook | `POST /api/v1/alerts/{id}/actions` | **DRAFT** | Audited logging of supportive loan officer visits and relief actions. |
| **S8** | Relief Evidence Report| `GET /api/v1/plots/{id}/relief-report` | **DRAFT** | Before/after NDVI, loss band vs. RBI 33% threshold. Mandatory disclaimer. |
| **S9** | Farmer Vernacular Summary | `GET /api/v1/assessments/{id}/farmer-summary?lang=en\|gu\|hi` | **DRAFT** | Plain-language summaries in English (`en`), Gujarati (`gu`), and Hindi (`hi`). |

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

