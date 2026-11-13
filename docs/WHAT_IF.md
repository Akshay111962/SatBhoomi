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

| Controllable Input | Allowed Transitions | Agronomic / Financial Sensitivity Mechanism |
| :--- | :--- | :--- |
| **`insured`** | `0` $\to$ `1` (`False` $\to$ `True`)<br>`1` $\to$ `0` | Enrolling in PMFBY crop insurance provides financial indemnification against catastrophic crop failure. Under the Agronomic Rules Baseline, this applies a **10-point protective reduction** in repayment risk and waives mandatory pre-disbursal insurance flags. |
| **`irrigation`** | `rainfed` $\to$ `tube_well` / `canal` / `drip` | Upgrading from rainfed to assured irrigation removes vulnerability to winter dry spells (`rain_pre_cutoff_deficit_pct` is buffered) and increases the baseline DLTC Scale of Finance from ₹22,000 to ₹32,000 / acre. |
| **`supplementary_irrigation`** | `deficit` $\to$ `applied` (0% deficit) | Simulates applying 1–2 protective irrigations during critical winter vegetative stages (crown root initiation / tillering), neutralizing rainfall deficit. |

---

## 3. Database & API Contract

### 3.1 SQLAlchemy ORM Entity (`db/models/what_if.py`)

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

### 3.2 CLI Interface

```bash
# Simulate enrolling an uninsured plot in PMFBY crop insurance
python scripts/score_plot.py --plot BORSAD_WHEAT_03 --season 2024-25 --what-if-input insured --what-if-val 1

# Simulate upgrading rainfed plot to tubewell irrigation
python scripts/score_plot.py --plot BORSAD_WHEAT_03 --season 2024-25 --what-if-input irrigation --what-if-val tube_well
```

---

## 4. Verification & Testing

- **Module**: [`src/satbhoomi/risk/what_if.py`](file:///d:/SatBhoomi/src/satbhoomi/risk/what_if.py)
- **Unit Test Suite**: [`tests/unit/test_what_if.py`](file:///d:/SatBhoomi/tests/unit/test_what_if.py) (8/8 passed, 91% statement coverage).
- **Test Scenarios**:
  1. `test_what_if_enrolling_insurance`: 10-point protective reduction and limit update.
  2. `test_what_if_upgrading_irrigation`: SoF transition from ₹22k to ₹32k and deficit buffering.
  3. `test_what_if_supplementary_irrigation`: Deficit neutralization.
  4. `test_what_if_disallowed_input_rejected`: Rejection of non-controllable features (e.g. `ndvi_early`).
  5. `test_what_if_invalid_irrigation_value_rejected`: Rejection of invalid irrigation values.
  6. `test_what_if_insufficient_data_baseline_raises`: Guard against incomplete observations.
  7. `test_what_if_orm_model_compatibility`: Zero-drift persistence with SQLAlchemy schema.
  8. `test_score_plot_cli_what_if_options`: End-to-end CLI validation.

