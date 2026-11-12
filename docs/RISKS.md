# SatBhoomi Score + Raksha — Risk Register

This document tracks identified architectural, operational, and ethical risks for **SatBhoomi Score + Raksha**, along with their severity, likelihood, and mitigation strategies.

---

## Agent Layer Risks

### RISK-01: Agent Hallucination
- **Category**: AI / Reliability / Credit Ethics
- **Description**: An LLM agent may fabricate data points, misquote numerical metrics (such as NDVI values, rainfall deficits, or credit scores), invent loan terms, or hallucinate causation when synthesizing farm stress reports or loan proposals.
- **Severity**: High
- **Likelihood**: Medium
- **Mitigation & Guardrails**:
  1. **Deterministic Tool Grounding**: Agents do not compute numbers or generate facts independently; they strictly invoke deterministic backend tools (`score`, `what_if`, `alerts`, `relief_evidence`).
  2. **Verbatim Metric Pass-Through**: Agents are restricted to reporting the exact numerical values returned by tool outputs.
  3. **Zero Free-Form Lending Decisions**: Agents are prohibited from proposing arbitrary loan limits or terms outside the deterministic underwriting engine rules.
  4. **Strict System Prompts & Grounding Checks**: Prompts forbid speculation or unsupported claims. Tool responses are injected into typed structured schemas.
  5. **Human Officer Review**: All agent outputs are explicitly presented as drafts; the bank loan officer must review and verify all statements against raw tool outputs before taking action.

---

### RISK-02: Agent Over-Autonomy
- **Category**: Security / Governance / Regulatory Compliance
- **Description**: An autonomous agent might independently execute state-changing actions without human intervention, such as approving/rejecting loan applications, contacting farmers directly, modifying database records, or sending unauthorized notifications.
- **Severity**: Critical
- **Likelihood**: Low (governed by design)
- **Mitigation & Guardrails**:
  1. **Read-Only / Draft-Only Scope (ADR-7)**: Agents only investigate and draft. They have no write permissions to alter application statuses or disburse funds.
  2. **No Direct Farmer Contact**: The agent layer has zero communication channels to farmers (no SMS, WhatsApp, email, or IVR tools). Only bank loan officers communicate with farmers.
  3. **No Psychological State Inference**: The agent is strictly barred from interpreting, guessing, or discussing a borrower's mental or emotional state. Language is restricted to "repayment stress" and "support needed".
  4. **No Personal Data Exposure**: Agents never receive personally identifiable information (Aadhaar, PAN, phone numbers, or bank account numbers). Only synthetic identifiers or anonymized plot metrics are exposed.
  5. **Mandatory Human Approval Gate**: Every state modification requires explicit, authenticated human officer approval in the UI.
  6. **Comprehensive Audit Trail**: Every agent tool invocation, prompt payload, draft proposal, and officer review decision is recorded immutably in `audit_log`.

---

## Modeling & Scoring Risks

### RISK-03: Zero Stressed Labels & Unvalidated Scoring / ML Models
- **Category**: Data Quality / Model Validity / Credit Risk
- **Description**: In `data/processed/features.csv`, all available training seasons (`2021-22` to `2023-24`) and the held-out test season (`2024-25`) had **zero stressed labels** (`ndvi_peak = 0.65` across all plots in the cached T-02 satellite file). Consequently, **ROC-AUC was not evaluable, and the ML models (`logreg`, `random_forest`, `xgboost`) could not be validated**. Live scoring currently relies on the unvalidated `AgronomicRulesBaseline` heuristic.
- **Severity**: High
- **Likelihood**: High (observed in current dataset)
- **Mitigation & Guardrails**:
  1. **Rules Baseline Active Scorer**: Saved single-class Logistic Regression is barred from live scoring; `AgronomicRulesBaseline` (`rules_baseline`) is used instead per ADR-2.
  2. **Mandatory Reliability Note**: Every `RiskScoreResult` outputs the fixed `reliability_note`: *"Not validated: no stressed outcomes were available in the sample data, so this score has not been shown to predict crop stress."*
  3. **Data Acquisition Requirement**: Before any pilot deployment, replace placeholder NDVI reflectance with real Sentinel-2 L2A band-level NDVI time-series across multi-district plots and historical drought seasons containing genuine stressed and default outcomes.

---

## Open Questions

### OPEN QUESTION-01: Pre-Sowing Loan Approval vs. In-Season (January 31) Assessment
- **Context**: The current T-04/T-06 scoring pipeline uses in-season observations up to **January 31** (mid-season wheat vegetative growth). It cannot be used at **pre-sowing loan origination** (November), when current-season NDVI and winter rainfall do not yet exist.
- **What a Pre-Sowing Assessment Would Need Instead**: Multi-year historical plot NDVI/yield resilience, field-verified irrigation and soil moisture capacity, seasonal monsoon/reservoir outlook, and historical repayment track record.
- **Decision Needed from Team**: Should SatBhoomi define a separate pre-sowing historical-resilience score for origination and keep the January 31 score strictly for in-season interim review, top-up, and Raksha restructuring? *(Not built in T-06.)*

---

## Rule for Risk Management
- Any new architectural component or feature that introduces autonomous behavior, external data dependency, or AI generation must record an entry in this risk register with concrete mitigations before implementation.
