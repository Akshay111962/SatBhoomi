# SatBhoomi Score + Raksha — What-If Simulator Specification (T-08, FR-007)

This document specifies the architecture, sensitivity logic, and operational guardrails for **Task T-08 (What-If Engine)**, implementing **FR-007** of the Product Blueprint.

---

## 1. Governance & Core Guardrails

1. **Rule 6: What-If Simulator Integrity**
   - What-if outputs are explicitly labeled **"estimate"** on screen, in API responses, and in reports.
   - What-if simulations show prospective model sensitivity given altered controllable interventions; they are **NOT proof of causation**.
   - The disclaimer is permanently attached to every simulation result.
2. **Strict Scope of Controllable Inputs**
   - The simulator only permits altering **actionable farmer interventions** (`insured`, `irrigation`, `supplementary_irrigation`).
   - Historical satellite observations (NDVI), weather records, historical yield, and prior season outcomes **cannot be tampered with**.
3. **Immutability of Baseline Assessments**
   - The original assessment record, score, risk band, and loan suggestions remain immutable.
   - What-if simulations are evaluated against a clone and recorded as separate `what_if` entity records linked via foreign key (`assessment_id`).

---

## 2. Allowed Controllable Interventions & Sensitivity Models

| Controllable Input | Allowed Transitions | Agronomic / Financial Sensitivity Mechanism | Effect Basis |
| :--- | :--- | :--- | :--- |
| **`insured`** | `0` $\to$ `1` (`False` $\to$ `True`)<br>`1` $\to$ `0` | Enrolling in PMFBY crop insurance provides financial indemnification against catastrophic crop failure. Under the Agronomic Rules Baseline, this applies a **10-point protective reduction** in repayment risk and waives mandatory pre-disbursal insurance flags. | `scenario_assumption` |
| **`irrigation`** | `rainfed` $\to$ `tube_well` / `canal` / `drip` | Upgrading from rainfed to assured irrigation removes vulnerability to winter dry spells (`rain_pre_cutoff_deficit_pct` is buffered to safe threshold $\ge -10\%$) and increases the baseline DLTC Scale of Finance from ₹22,000 to ₹32,000 / acre. | `scorer_input` |
| **`supplementary_irrigation`** | `deficit` $\to$ `applied` (0% deficit) | Simulates applying 1–2 protective irrigations during critical winter vegetative stages (crown root initiation / tillering), neutralizing rainfall deficit departure to 0.0%. | `scenario_assumption` |

---

## 3. Effect Basis Taxonomy & Zero-Delta Guardrails

To prevent misleading claims of direct algorithmic sensitivity, every what-if simulation explicitly categorizes the origin of the projected effect:

### 3.1 `effect_basis` Enumeration
1. **`scorer_input`**: The intervention directly modifies an input feature evaluated by the active scoring function (e.g. changing `irrigation` source from `rainfed` to `tube_well`).
2. **`scenario_assumption`**: The intervention applies a documented, structural policy or agronomic heuristic not directly modeled as a standalone feature in the scorer (e.g. 10-point protective discount for PMFBY enrollment; buffering rainfall deficit to 0.0% via supplementary watering).
3. **`not_modelled`**: The intervention produces zero net effect on the active model, or the target value equals the baseline value.

### 3.2 Zero-Delta Behavior
When `score_delta == 0`, the engine handles two distinct cases:
* **Intervention matches baseline**: If the user simulates a transition where `old_val == new_val` (e.g. simulating `insured=1` on an already insured plot), `effect_basis` transitions to `not_modelled`, and a note is appended: `"Zero delta: intervention value equals baseline value."`
* **Zero net impact**: If the intervention is distinct but yields no net shift in score under the active rules (e.g. supplementary irrigation applied to an already irrigated plot that suffers no moisture penalty), a note is appended: `"Zero delta: intervention produced no net change in risk score under active rules."`

---

## 4. Database & API Contract

### 4.1 Pydantic Model (`src/satbhoomi/risk/what_if.py`)

```python
class WhatIfResult(BaseModel):
    status: Literal["ok", "insufficient_data"] = "ok"
    assessment_id: int | None = None
    plot_code: str
    season: str
    changed_input: str
    old_value: str
    new_value: str
    old_score: int
    new_score: int
    score_delta: int
    old_band: RiskBand
    new_band: RiskBand
    old_limit_band: LoanLimitBand | None = None
    new_limit_band: LoanLimitBand | None = None
    estimate_label: str = "estimate"
    effect_basis: Literal["scorer_input", "scenario_assumption", "not_modelled"]
    assumption: str | None = None
    rationale: str
    disclaimer: str = DISCLAIMER_WHAT_IF
    notes: list[str] = Field(default_factory=list)
```

### 4.2 SQLAlchemy ORM Entity (`db/models/what_if.py`)

```python
class WhatIf(Base):
    __tablename__ = "what_if"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("assessment.id", ondelete="CASCADE"))
    changed_input: Mapped[str] = mapped_column(String(50))
    old_value: Mapped[str] = mapped_column(String(100))
    new_value: Mapped[str] = mapped_column(String(100))
    new_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

### 4.3 CLI Interface

```bash
# Simulate enrolling an uninsured plot in PMFBY crop insurance
python scripts/score_plot.py --plot BORSAD_WHEAT_03 --season 2024-25 --what-if-input insured --what-if-val 1

# Simulate upgrading rainfed plot to tubewell irrigation
python scripts/score_plot.py --plot BORSAD_WHEAT_03 --season 2024-25 --what-if-input irrigation --what-if-val tube_well
```

---

## 5. Verified Simulation Examples

### 5.1 Recomputed Active Examples (CURRENT: 2026-11-14, v2.0 Relative Rules Scorer)

#### Example 1: Enrolling Uninsured Plot (`BORSAD_WHEAT_03`, 2024-25)
* **Baseline State**: `insured=0`, Score: 10, Band: `low`, Limit: ₹72,000–₹80,000 (Scale: ₹32,000/acre, 2.5 acres).
* **Intervention**: `insured=1`
* **Simulated State**: Score: 0, Band: `low`, Limit: ₹72,000–₹80,000, Delta: -10
* **Effect Basis**: `scenario_assumption`
* **Assumption**: `"Enrolling in PMFBY crop insurance provides financial indemnification, applying a 10-point protective reduction in repayment risk score."`
* **Notes**: `["Simulated parameter: insured (0 -> 1)", "Prospective score transition: 10 (low) -> 0 (low) [delta: -10]"]`

#### Example 2: Cancellation of Insurance (`ANAND_WHEAT_02`, 2022-23)
* **Baseline State**: `insured=1`, Score: 45, Band: `medium`, Limit: ₹52,000–₹64,000.
* **Intervention**: `insured=0`
* **Simulated State**: Score: 55, Band: `medium`, Limit: ₹52,000–₹64,000, Delta: +10
* **Effect Basis**: `scenario_assumption`
* **Assumption**: `"Enrolling in PMFBY crop insurance provides financial indemnification, applying a 10-point protective reduction in repayment risk score."`
* **Notes**: `["Simulated parameter: insured (1 -> 0)", "Prospective score transition: 45 (medium) -> 55 (medium) [delta: +10]"]`

#### Example 3: Zero-Delta Case (`ANAND_WHEAT_02`, 2022-23)
* **Baseline State**: `insured=1`, Score: 45, Band: `medium`.
* **Intervention**: `insured=1` (Identical value to baseline)
* **Simulated State**: Score: 45, Band: `medium`, Delta: 0
* **Effect Basis**: `not_modelled`
* **Notes**: `["Simulated parameter: insured (1 -> 1)", "Prospective score transition: 45 (medium) -> 45 (medium) [delta: +0]", "Zero delta: intervention value equals baseline value."]`

### 5.2 Pre-Correction What-If Simulations (SUPERSEDED)
*Evaluated on legacy uncorrected NDVI data with absolute early NDVI threshold $\le 0.35$ and pre-offset correction scores*:
* Baseline scores were heavily inflated by PB 04.00 offset (e.g. artificial absolute early NDVI drops triggering spurious flags).
* Status: **SUPERSEDED** (replaced by v2.0 relative rules and explicit `effect_basis` classification).

---

## 6. Verification & Testing

- **Module**: [`src/satbhoomi/risk/what_if.py`](file:///d:/SatBhoomi/src/satbhoomi/risk/what_if.py)
- **Unit Test Suite**: [`tests/unit/test_what_if.py`](file:///d:/SatBhoomi/tests/unit/test_what_if.py) (9/9 passed, 91% statement coverage).
- **Test Scenarios**:
  1. `test_what_if_enrolling_insurance`: 10-point protective reduction, limit update, and `scenario_assumption` basis.
  2. `test_what_if_upgrading_irrigation`: SoF transition from ₹22k to ₹32k and deficit buffering with `scorer_input` basis.
  3. `test_what_if_supplementary_irrigation`: Deficit neutralization.
  4. `test_what_if_disallowed_input_rejected`: Rejection of non-controllable features (e.g. `ndvi_early`).
  5. `test_what_if_invalid_irrigation_value_rejected`: Rejection of invalid irrigation values.
  6. `test_what_if_insufficient_data_baseline_raises`: Guard against incomplete observations.
  7. `test_what_if_orm_model_compatibility`: Zero-drift persistence with SQLAlchemy schema.
  8. `test_score_plot_cli_what_if_options`: End-to-end CLI validation.
  9. `test_what_if_effect_basis_and_zero_delta`: Verification of `effect_basis` classification and zero-delta note generation.

