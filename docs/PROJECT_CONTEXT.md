# SatBhoomi Score + Raksha — Project Context & Guardrails

This document establishes the permanent ethical, architectural, operational, and development rules for **SatBhoomi Score + Raksha**. Every developer, contributor, and AI assistant working on this project must strictly abide by these rules for every task.

---

## 0. Rule Precedence & Development Clarifications

When rules conflict, this strict precedence order applies:
1. **PROJECT_CONTEXT.md safety and honesty rules** (highest priority)
2. **[docs/ENGINEERING_RULES.md](file:///d:/SatBhoomi/docs/ENGINEERING_RULES.md)**
3. **The instructions in the current task prompt**

### Project-Specific Operational Clarifications
- **Mandatory Plan Approval**: For every task, produce a short plan and wait for my approval before writing code. This explicitly overrides "make reasonable assumptions and proceed" at the start of a task. Keep assumptions short and state them in the plan.
- **Strict Scope Boundaries**: Implement only the task given. No extra features.
- **Radical Verification Honesty**: Never claim anything is tested, verified, or working unless you actually ran it. Say "not verified" when you could not run or verify it.
- **Safe Operations**: Never perform destructive, irreversible, or expensive actions, or deploy anywhere, without explicit approval.
- **Mandatory Reporting**: Use the Task Completion Report format from [docs/ENGINEERING_RULES.md](file:///d:/SatBhoomi/docs/ENGINEERING_RULES.md) Section 8 at the end of every task.

---

## 1. Product Identity & Purpose
- **Product Name**: SatBhoomi Score + Raksha
- **Domain**: AI farm credit scoring and early-warning decision-support tool for bank loan officers.
- **Core Value Proposition**: A farm-based risk assessment that goes from "score to action" — providing transparent risk scores with plain-language reasons, right-sized loan suggestions, in-season stress alerts, and relief evidence reports.
- **Reference Blueprint**: [docs/blueprint.pdf](file:///d:/SatBhoomi/docs/blueprint.pdf) (v0.1 draft).

---

## 2. Permanent Non-Negotiable Rules

### Rule 1: Human-in-the-Loop Decision Making
- The system **NEVER approves or rejects a loan**.
- A human bank officer always makes the final credit decision and logs their rationale.
- The system is purely an explanatory decision-support and early-warning aid.

### Rule 2: Ethical Framing & Sensitive Language (Raksha Module)
- Alerts describe **farm and repayment stress** (e.g. crop health decline, rainfall deficit, mandi price drop), **NEVER a person's mental health or psychological state**.
- Always use the precise wording **"repayment stress"** and **"support needed"**.
- Absolutely no individual-level predictions of self-harm or psychological distress.
- Alert playbooks lead to supportive, constructive actions first (field visit, insurance claim assistance, rescheduling under RBI relief guidelines, aligning repayment with produce sale). Harsh recovery pressure is prohibited.

### Rule 3: Privacy & Data Safeguards
- **No real farmer data in the repository**. Only synthetic, anonymized, or mock data is permitted.
- Never store national identity numbers (e.g., Aadhaar), bank account numbers, or PAN numbers.
- Derived season features (NDVI aggregates, rainfall totals) are stored, not raw satellite imagery.
- Respect consent requirements (aligned with India's DPDP Act, 2023 principles) and support data deletion on request.

### Rule 4: Zero Secrets in Code
- **No API keys, database credentials, or secret tokens in code or commits**.
- All configuration and secrets must be loaded via environment variables using Pydantic Settings and documented in `.env.example`.
- Secret scanning is enforced in pre-commit hooks and CI.

### Rule 5: Traceability & Model Versioning
- **Every credit score must store its model version** alongside the score value, risk band, and feature snapshot.
- Assessments must be reproducible: identical inputs with the same model version must yield identical outputs.

### Rule 6: What-If Simulator Integrity
- What-if outputs are explicitly labeled **"estimate"** on screen, in reports, and in documentation.
- What-if simulations show prospective model sensitivity given altered controllable inputs (e.g., adding irrigation or crop insurance); they are **not proof of causation**.

### Rule 7: Positioning & Academic Honesty
- **Do not claim novelty**. Established commercial platforms (notably SatSure's SatSource and Sage) already provide satellite-based agri-lending scoring.
- Position SatBhoomi clearly as a transparent, student-built prototype focused on **"score to action"** (right-sizing loans, what-if simulations, early warning, and RBI 33% relief evidence).
- Reference SatSure and existing literature as related work. Differences are treated as hypotheses to validate, not undisputed commercial claims.

### Rule 8: Radical Engineering Honesty
- **Never state that something is tested unless tests were actually run and passed**.
- When reporting results, evaluations, or benchmarks, report real held-out metrics and acknowledge gaps or limitations openly.
- If data is missing (e.g., cloud cover over satellite passes), surface a **"data gap"** banner and use fallback logic; never invent or hallucinate data points.

### Rule 9: Frontend Gate (UI Screens S1–S9)
- Do **NOT** build any real UI screens (blueprint S1 to S9) until the user provides frontend details (design preferences, branding, languages, and layout choices).
- Until then, only the existing placeholder Streamlit home page is allowed.
- When a task reaches the dashboard, stop and ask the user for these details.

---

## 3. Architecture & Tech Stack Highlights
- **Style**: Modular Monolith (`src/satbhoomi/`).
- **Language**: Python 3.11+.
- **Backend**: FastAPI with typed Pydantic models.
- **Frontend**: Streamlit dashboard for bank officers (screens S1–S9).
- **Database**: SQLite with WAL mode & foreign keys for PoC, designed with SQLAlchemy 2.0 so migration to PostgreSQL requires zero query changes.
- **Explainability**: SHAP values translated into top 3 plain-language reasons.
