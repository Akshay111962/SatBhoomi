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

## Rule for Risk Management
- Any new architectural component or feature that introduces autonomous behavior, external data dependency, or AI generation must record an entry in this risk register with concrete mitigations before implementation.
