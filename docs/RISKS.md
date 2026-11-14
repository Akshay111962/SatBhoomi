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

### RISK-04: In-Season Farm Stress Alerts Not Validated on Real Disaster Events
- **Category**: Agronomic Sensing / Early Warning Validity / Credit Risk
- **Description**: While satellite NDVI, NASA POWER precipitation, APMC mandi prices, and government yield statistics in `season_dataset.csv` are 100% empirical live data, **no adverse events were reported to us; not checked against official records**. Historical replay results are purely descriptive. The early-warning lead time and alert detection efficacy cannot be validated on historical data and were verified exclusively on a labelled **synthetic stress scenario** (TC-007).
- **Severity**: Medium
- **Likelihood**: High (no adverse events reported in the sample window)
- **Mitigation & Guardrails**:
  1. **Zero Overclaiming**: The system explicitly disclaims early warning proof or calamity detection on historical data; docs and CLI reports clearly label historical replay as descriptive only.
  2. **TC-007 Synthetic Stress Validation**: Early alert lead time (11.0 weeks before harvest vs. $\ge 6$-week requirement) is tested and passed strictly on a labelled synthetic scenario (`SYNTHETIC_STRESS_SCENARIO` with a simulated 30% vegetative drop).
  3. **Strict Data Gap Separation**: Missing or sparse scene data ($\le 1$ prior season or $< 2$ clear scenes) is recorded as a `data_gap`, never raising an alert and never imputing or guessing values.
  4. **Supportive-Only Playbooks**: Alerts trigger supportive actions for the bank loan officer (field moisture check, PMFBY insurance claim assistance, harvest-aligned repayment scheduling). They never trigger coercive recovery pressure or farmer blame.

---

### RISK-05: Cutoff Date Temporal Ambiguity in Scoring Results
- **Category**: Data Quality / API Contract / Temporal Ambiguity
- **Description**: In `src/satbhoomi/risk/scoring.py`, `RiskScoreResult.cutoff_date` is hardcoded as a static string `CUTOFF_DATE_LABEL = "January 31"` without a calendar year. Across multi-season historical evaluations and API integrations (e.g. comparing season `2023-24` vs `2024-25`), a static month-day string is ambiguous and cannot be parsed as a standard ISO-8601 calendar date (`YYYY-MM-DD`).
- **Severity**: Low
- **Likelihood**: High (inherent in current `scoring.py` definition)
- **Mitigation & Guardrails**:
  1. **API Parity Preserved**: API contract v0.2.0 maintains exact parity with `RiskScoreResult.cutoff_date: str = "January 31"`, preventing uncoordinated breaking changes to underlying scoring logic.
  2. **Audit & Log Tracking**: Persisted database records (`assessment.created_at`) store full timezone-aware ISO timestamps.
  3. **Future Scoring Refactoring**: A future scoring refactoring task will derive a seasonal ISO calendar date (e.g. `2024-01-31`) directly from the evaluated `season` string.

---

### RISK-06: Sentinel-2 Processing-Baseline 04.00 Offset Inconsistency
- **Category**: Remote Sensing Data Quality / Calibration Inconsistency / Model Degradation
- **Description**: Beginning 25 January 2022 with ESA Processing Baseline 04.00, Sentinel-2 L2A surface reflectance digital numbers ($\text{DN}$) introduced an offset of $+1000$ ($\text{DN} = 10000 \cdot \rho + 1000$). Reading raw DNs without subtracting this offset introduces an artificial $+0.20$ term in the denominator of the NDVI calculation: $(NIR - RED) / (NIR + RED + 0.20)$, attenuating peak vegetative reflectance by ~30% and causing a severe artificial step drop from 2022-23 onwards.
- **Severity**: High
- **Likelihood**: High (encountered in Planetary Computer raw pixel reads)
- **Mitigation & Guardrails**:
  1. **Per-Scene Metadata & Baseline Detection**: `PlanetaryComputerProvider` inspects STAC item metadata (`raster:bands` offset) and `s2:processing_baseline` to determine the exact BOA offset per scene ($-1000.0$ for baseline $\ge 04.00$), using date fallback only as a logged last resort.
  2. **Raw Nodata Masking Pre-Offset**: Pixel value 0 is masked as nodata on raw digital numbers before offset subtraction.
  3. **Versioned Cache Separation**: Raw observation caches include `processing_baseline`, `offset_applied`, `offset_rule`, and `provider_logic_version="v2_pb_offset_corrected"`, preventing reuse of uncorrected scenes.
  4. **Downstream Invalidation**: All ML models, evaluations, and replays computed on uncorrected NDVI are marked `SUPERSEDED` pending recomputation.

---

## Open Questions

### OPEN QUESTION-01: Pre-Sowing Loan Approval vs. In-Season (January 31) Assessment
- **Context**: The current T-04/T-06 scoring pipeline uses in-season observations up to **January 31** (mid-season wheat vegetative growth). It cannot be used at **pre-sowing loan origination** (November), when current-season NDVI and winter rainfall do not yet exist.
- **What a Pre-Sowing Assessment Would Need Instead**: Multi-year historical plot NDVI/yield resilience, field-verified irrigation and soil moisture capacity, seasonal monsoon/reservoir outlook, and historical repayment track record.
- **Decision Needed from Team**: Should SatBhoomi define a separate pre-sowing historical-resilience score for origination and keep the January 31 score strictly for in-season interim review, top-up, and Raksha restructuring? *(Not built in T-06.)*

---

## Rule for Risk Management
- Any new architectural component or feature that introduces autonomous behavior, external data dependency, or AI generation must record an entry in this risk register with concrete mitigations before implementation.
