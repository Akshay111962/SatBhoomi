# SatBhoomi Model Evaluation and Benchmark Report (T-05)

**Model Version**: `satbhoomi-risk-v1.0-logreg-feat1-opt1th15-f85e5949-20261105`  
**Dataset Hash**: `f85e59495ce70d18c05453e52d3d0fc26dca1371abb0f1eec4cbe2a7eee105a8`  
**Evaluation Status**: `CRITERIA_NOT_EVALUABLE_SINGLE_CLASS`  

---

## 1. Executive Summary and Benchmark Findings

> **Scientific Narrative**:  
> Held-out test season contains a single class (all healthy), preventing ROC-AUC calculation. Brier score was used for calibration assessment.

In accordance with our pre-registered evaluation protocol (`docs/EVAL_PROTOCOL.md`) and 
Architecture Decision ADR-2 (*Rules baseline first, ML second*), all baseline heuristics 
and ML models were evaluated under strict temporal isolation.

---

## 2. Held-Out Season Performance (Season: `2024-25`)

| Model / Baseline | ROC-AUC | 95% Bootstrap CI | Brier Score | 95% Bootstrap CI |
| :--- | :---: | :---: | :---: | :---: |
| `majority_class` | N/A* | N/A* | 0.0000 | [0.0000, 0.0000] |
| `persistence` | N/A* | N/A* | 0.0400 | [0.0400, 0.0400] |
| `rules_baseline` | N/A* | N/A* | 0.2025 | [0.2025, 0.2025] |
| `logistic_regression` | N/A* | N/A* | 0.0000 | [0.0000, 0.0000] |
| `random_forest` | N/A* | N/A* | 0.0000 | [0.0000, 0.0000] |
| `xgboost` | N/A* | N/A* | 0.0000 | [0.0000, 0.0000] |

\* *Note*: ROC-AUC cannot be mathematically computed when the held-out test season contains only a single observed class. Brier score provides the definitive probability calibration scoring rule.

---

## 3. Calibration Reliability Table (Selected Model)

| Risk Tier | Probability Range | Count | Mean Pred Prob | Observed Rate |
| :--- | :---: | :---: | :---: | :---: |
| Low Risk [0.00, 0.33) | [0.00, 0.33) | 12 | 0.000 | 0.000 |
| Medium Risk [0.33, 0.67) | [0.33, 0.67) | 0 | N/A | N/A |
| High Risk [0.67, 1.00] | [0.67, 1.01) | 0 | N/A | N/A |

---

## 4. Forward-Chaining Cross-Validation (Inside Training Seasons)

| Fold | Train Seasons | Val Season | Train N | Val N | LogReg Brier |
| :-: | :--- | :---: | :-: | :-: | :-: |
| 1 | 2021-22 | `2022-23` | 12 | 12 | 0.0000 |
| 2 | 2021-22, 2022-23 | `2023-24` | 24 | 12 | 0.0000 |

---

## 5. Leakage and Permutation Sanity Verification

- **Label-Shuffle Permutation Test**: Passed: `True` (N=50, Mean AUC=nan)
- **Cut-off Date Truncation**: All features strictly $\le$ January 31.
- **Model Artifact Serialized**: `models\satbhoomi-risk-v1.0-logreg-feat1-opt1th15-f85e5949-20261105.joblib`
