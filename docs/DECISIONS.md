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
