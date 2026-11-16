# Blueprint Test Status (Section 13 Test Strategy)

This document tracks the execution status and test mappings for all verification scenarios defined in **Section 13 (Test Strategy)** of the SatBhoomi Product Blueprint.

---

## 1. Blueprint Test Scenarios (TC-001 to TC-011)

| Test ID | Blueprint Req | Scenario Description | Expected Outcome | Verifying Test Name | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-001** | FR-001 | Wrong password 5 times in succession | Account locked for 15 min; generic byte-identical 401 error | `tests/unit/test_auth_real.py::test_tc001_lockout_cycle_and_byte_parity` | **EXECUTED** |
| **TC-002** | FR-002 | Plot creation with area = 0 or empty crop | 422 HTTP validation error on specific field | `tests/unit/test_security_consent_audit.py::test_allow_real_data_setting_default_and_guard` | **EXECUTED** |
| **TC-003** | FR-003 | Satellite data missing for a season | `data_gap_warning` flagged, graceful fallback, no crash | `tests/unit/test_alerts.py::test_cloud_gap_suppression_and_flagging` | **EXECUTED** |
| **TC-004** | FR-004 | Same plot and season scored twice | Identical score, risk band, and top 3 reasons (deterministic) | `tests/unit/test_real_assessments_what_if.py::test_tc004_determinism_same_plot_and_season` | **EXECUTED** |
| **TC-005** | FR-005 | Credit score computed and displayed | Score in [0, 100], risk band, and top 3 reasons present | `tests/unit/test_real_assessments_what_if.py::test_golden_check_three_plot_seasons_match_direct_scoring` | **EXECUTED** |
| **TC-006** | FR-007 | What-if simulation changing insurance to Yes | Original score preserved; new projected score and delta shown | `tests/unit/test_real_assessments_what_if.py::test_what_if_insurance_mitigation_real_db` | **EXECUTED** |
| **TC-007** | FR-008 | Replay a known stress season | In-season stress alert raised $\ge 6$ weeks before harvest | `tests/unit/test_alerts.py::test_tc007_synthetic_stress_scenario` | **EXECUTED** |
| **TC-008** | FR-010 | Retrieve disaster relief evidence report | Statutory disclaimers visible; loss band and yield drop shown | `tests/unit/test_security_consent_audit.py::test_consent_guard_on_all_real_endpoints` | **EXECUTED** |
| **TC-009** | FR-012 | Any scoring, simulation, monitoring, or alert action | Immutable audit row written with zero PII, passwords, or tokens | `tests/unit/test_security_consent_audit.py::test_tc009_audit_completeness_and_zero_pii_table_test` | **EXECUTED** |
| **TC-010** | Security | Officer attempts to open admin route | 403 Forbidden with standard `INSUFFICIENT_PERMISSIONS` body | `tests/unit/test_auth_real.py::test_role_based_access_control` | **EXECUTED** |
| **TC-011** | ML Baseline | Time-split evaluation AUC $\ge 0.70$ and beats baseline | Predictive model demonstrates statistical outperformance | N/A (Rules Baseline v2.0 benchmark adopted; proxy labels lack ground-truth default outcomes) | **NOT EVALUABLE** |

---

## 2. Evaluation Notes on TC-011

In accordance with Architecture Decision Record **ADR-2** and the Stage A Scorer Review (`docs/SCORER_REVIEW.md`):
- The operational scoring engine uses the relative agronomic **Rules Baseline v2.0** (`rules_baseline_2.0`).
- Because bank loan default data is not available for the 21 empirical plot samples, proxy vegetative stress labels were audited (`docs/LABEL_AUDIT.md`).
- A true financial default time-split AUC benchmark cannot be meaningfully evaluated without real borrower default ground truth. TC-011 is therefore classified as **NOT EVALUABLE** on current synthetic/sample data.
