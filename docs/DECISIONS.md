# Architecture Decision Records (ADRs)

This document records the architectural decisions made for **SatBhoomi Score + Raksha**, based on Section 6 of the Product Blueprint.

---

## ADR-1: Modular Monolith Architecture
* **Status**: Accepted
* **Context**: The project is being developed by a small team (3 developers) targeting a student PoC and draft research paper. Microservices introduce distributed tracing, multi-repo or multi-container deployment overhead, and networking complexity that are unwarranted for this scale.
* **Decision**: Adopt a modular monolith architecture organized under `src/satbhoomi/` with distinct module boundaries (`config`, `connectors`, `features`, `risk`, `alerts`, `api`, `db`, `reports`, `summary`, `ui`).
* **Consequences**:
  * *Positive*: Single codebase, frictionless local development, easy integration testing, fast end-to-end demo execution.
  * *Negative*: Requires discipline to enforce clean module boundaries and avoid tight coupling between domain modules.

---

## ADR-2: Rules Baseline First, Machine Learning Second
* **Status**: Accepted
* **Context**: Credit scoring models in sensitive agricultural domains must be explainable, robust, and benchmarked against transparent domain rules (e.g., low NDVI + severe rain deficit = high risk). Additionally, there is a risk that complex ML models overfit or fail to beat simple heuristics.
* **Decision**: Implement and validate a transparent, rule-based baseline before training and evaluating ML models (Logistic Regression, Random Forest, XGBoost). ML is adopted only if it demonstrates a statistically significant improvement on held-out test data.
* **Consequences**:
  * *Positive*: Provides an immediate fallback if ML models underperform; proves incremental ML value for the academic paper; establishes a transparent benchmark.
  * *Negative*: Requires developing and maintaining two scoring paths (heuristic rules engine and ML pipeline) initially.

---

## ADR-3: Streamlit for PoC UI, React Later if Needed
* **Status**: Accepted
* **Context**: The primary user is a bank loan officer who needs interactive assessment views, what-if simulators, and alert dashboards (screens S1–S9). Building a separate React/Vue frontend requires significant frontend overhead and separate API client state management.
* **Decision**: Use Streamlit for the rapid PoC user interface, while maintaining clean FastAPI service boundaries and standardized REST JSON contracts (`/api/v1/...`).
* **Consequences**:
  * *Positive*: Fastest path to a functional, interactive UI with native Python data visualizations and low boilerplate.
  * *Negative*: Less UI customization flexibility than a dedicated React single-page app; state management across complex multi-step wizards requires careful Streamlit session state handling.

---

## ADR-4: SQLite for PoC, Schema Written so PostgreSQL Works Seamlessly
* **Status**: Accepted
* **Context**: Setting up and hosting PostgreSQL adds external dependency friction during local development and testing, yet production bank deployments require an enterprise relational database like PostgreSQL.
* **Decision**: Use SQLite with WAL (Write-Ahead Logging) mode and enforced foreign keys for local development and PoC demonstrations. Implement all data models via SQLAlchemy 2.0 ORM using ANSI-SQL compliant types so switching to PostgreSQL only requires changing the `DATABASE_URL` connection string.
* **Consequences**:
  * *Positive*: Zero external database server setup for developers and CI; zero hosting costs for PoC; frictionless reproducible test runs.
  * *Negative*: SQLite has concurrency limitations for high write loads (though WAL mode mitigates this for PoC read-heavy officer workflows).

---

## ADR-5: LLM Only Rewrites Approved Text into Local Language; Never Decides
* **Status**: Accepted
* **Context**: Generating farmer-facing loan summaries in vernacular languages (e.g., Gujarati, Hindi) requires simple, non-patronizing, and easily understandable language. However, generative LLMs can hallucinate loan figures, introduce misleading financial advice, or introduce bias.
* **Decision**: LLMs are strictly restricted to translating and rewriting pre-approved deterministic templates into plain Gujarati or Hindi. LLMs are never permitted to make, modify, or infer credit decisions, risk bands, or loan amounts. No personally identifiable farmer information is sent to external LLM APIs.
* **Consequences**:
  * *Positive*: Guarantees that decisions remain deterministic, fully explainable, audit-compliant, and grounded in human review.
  * *Negative*: Farmer summaries are constrained to templated structures rather than fully open-ended conversational advice.

---

## ADR-6: LangGraph for Future Agent Layer
* **Status**: DECIDED, NOT IMPLEMENTED
* **Context**: The future agent layer will orchestrate multi-step research, assessment drafting, and in-season stress investigations for bank officers. This requires stateful workflows, persistence checkpoints, reversible turns, and strict human approval gates.
* **Decision**: The future agent layer will use LangGraph (stateful graph, checkpointing, human approval gates). Do not install it or write agent code until explicitly requested by the user.
* **Consequences**:
  * *Positive*: Provides native cyclic graph execution, checkpointed conversation/investigation states, and programmatic breakpoints for human-in-the-loop validation.
  * *Negative*: Avoids premature dependency bloat and keeps current development focused on core deterministic data models and ML pipelines.

---

## ADR-7: Agent Boundaries & Human Approval Gates
* **Status**: DECIDED, NOT IMPLEMENTED
* **Context**: Autonomous AI agents operating in agricultural lending risk making hallucinated assertions, taking unintended actions, or violating borrower privacy if boundaries are loose.
* **Decision**: Agents only investigate and draft. They call deterministic tools (score, what-if, alerts, relief evidence). Humans approve every write action. Agents never approve or reject a loan, never contact farmers, never infer anyone's mental state, only state numbers returned by tools, and receive no personal data. Every tool call is written to the audit log.
* **Consequences**:
  * *Positive*: Preserves strict human accountability, eliminates hallucinated financial commitments, enforces ethical restrictions regarding farmer welfare, and ensures complete auditability.
  * *Negative*: Precludes zero-touch automated lending; bank officers must review and approve all agent-drafted actions.

---

## ADR-8: Farmer Data Deletion Strategy (Right to Erasure & Audit Trail)
* **Status**: Accepted
* **Context**: India's Digital Personal Data Protection (DPDP) Act, 2023 grants data principals the right to withdraw consent and request erasure of personal data. In SatBhoomi, farmers can request deletion of their records. The system must completely remove all identifiable agricultural records, plots, and credit assessments associated with that farmer, while preserving an immutable operational audit log for financial compliance.
* **Decision**: Implement a database-level cascading deletion (`ON DELETE CASCADE`) rooted at the `farmer` entity. Deleting a farmer automatically cascades and purges all related `plots`, `consents`, `season_observations`, `assessments`, `what_ifs`, `alerts`, and `action_logs`. The `audit_log` records system events (e.g. `event='farmer_deleted'`, `entity='farmer'`, `entity_id=<id>`) with `user_id` set via `ON DELETE SET NULL`, retaining an immutable compliance ledger without preserving any farmer personal or geospatial data.
* **Consequences**:
  * *Positive*: Guarantees clean, zero-leak erasure of all farmer records on request, satisfying DPDP Act requirements and preventing orphaned plot assessments.
  * *Negative*: Irreversible removal of historical observations associated with that farmer's plots (aggregate regional yield and mandi price baselines remain preserved separately).


---

## ADR-9: Python Runtime Compatibility (Local Python 3.13 vs Blueprint Python 3.11)
* **Status**: Accepted
* **Context**: The project blueprint initially recommended Python 3.11 for maximal compatibility with existing agricultural ML libraries. However, the local development workstation host environment uses Python 3.13.5 (`.venv`), while the remote GitHub Actions CI environment tests on Ubuntu with Python 3.11 (`python-version: "3.11"`). Incompatible syntax or deprecated library features could cause divergence between local runs and automated CI.
* **Decision**: Maintain strict bi-directional compatibility across Python 3.11, 3.12, and 3.13. All code, data connectors, and test fixtures must execute without deprecation warnings or platform-specific failures on both Python 3.11 and Python 3.13. Dependencies added to `pyproject.toml` must provide pre-built wheels and verified support for Python 3.13 without modifying or forcing a downgrade of the developer's local runtime.
* **Consequences**:
  * *Positive*: Enables seamless local development on modern Python 3.13 while guaranteeing green CI verification on standard Python 3.11 runners.
  * *Negative*: Restricts adoption of bleeding-edge or legacy C-extensions that lack Python 3.13 wheel distributions (mitigated by selecting lightweight, pure-Python or universally supported geospatial tools).

---

## ADR-10: API Contract-First Development & Mock Server Default Off
* **Status**: Accepted
* **Context**: Two independent frontend implementations are being developed concurrently: a Streamlit dashboard and a React single-page application built by a frontend teammate. If the frontend teams build against ad-hoc backend assumptions, UI components will diverge, break, or require costly rework once real business logic lands. Furthermore, business logic for loan suggestions, what-if simulations, alerts, and vernacular summaries is still evolving across tasks T-07, T-08, T-09, and T-12.
* **Decision**: Adopt a strict contract-first API design based on Blueprint Section 8. Publish a versioned, deterministic OpenAPI specification (`docs/api/openapi.json`) with contract version `0.1.0`. Provide a standalone synthetic mock server activated strictly by environment variable `MOCK_API=true`. By default (`MOCK_API=false` or unset), all `/api/v1` endpoints return HTTP `501 Not Implemented`. In production (`ENVIRONMENT=production`), the application refuses to start if `MOCK_API=true` is set.
* **Consequences**:
  * *Positive*: Unblocks parallel frontend development immediately; guarantees both React and Streamlit frontends integrate against the identical typed schema; prevents premature or fake business logic from masquerading as real code; eliminates risk of mock data leaking into production.
  * *Negative*: Requires maintaining schema synchronicity between Pydantic API schemas and internal risk/feature calculation models as later tasks advance.

