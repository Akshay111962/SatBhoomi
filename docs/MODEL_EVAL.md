# SatBhoomi Model Evaluation and Benchmark Report (T-05)

**Model Version**: `satbhoomi-risk-v1.0-logreg-feat1-opt1th15-8bac5ab0-20261112`  
**Dataset Hash**: `8bac5ab0f36888deeef2fa53882de82faaa7cd608e359140afd9bdb146908ade`  
**Evaluation Status**: `CRITERIA_NOT_MET`  

---

## 1. Executive Summary and Benchmark Findings

> **Scientific Narrative**:  
> Held-out AUC is below 0.70 or confidence interval spans 0.50. Model predictive signal is statistically unvalidated on small sample.

In accordance with our pre-registered evaluation protocol (`docs/EVAL_PROTOCOL.md`) and 
Architecture Decision ADR-2 (*Rules baseline first, ML second*), all baseline heuristics 
and ML models were evaluated under strict temporal isolation.

---

## 2. Held-Out Season Performance (Season: `2024-25`)

| Model / Baseline | ROC-AUC | 95% Bootstrap CI | Brier Score | 95% Bootstrap CI |
| :--- | :---: | :---: | :---: | :---: |
| `majority_class` | 0.500 | [0.500, 0.500] | 0.2676 | [0.2270, 0.3081] |
| `persistence` | 0.500 | [0.500, 0.500] | 0.3650 | [0.2400, 0.4900] |
| `rules_baseline` | 0.413 | [0.219, 0.636] | 0.3533 | [0.2533, 0.4592] |
| `logistic_regression` | 0.336 | [0.098, 0.600] | 0.4382 | [0.2818, 0.5955] |
| `random_forest` | 0.427 | [0.203, 0.667] | 0.3108 | [0.2301, 0.3892] |
| `xgboost` | 0.538 | [0.500, 0.625] | 0.2948 | [0.2231, 0.3726] |

\* *Note*: ROC-AUC cannot be mathematically computed when the held-out test season contains only a single observed class. Brier score provides the definitive probability calibration scoring rule.

---

## 3. Calibration Reliability Table (Selected Model)

| Risk Tier | Probability Range | Count | Mean Pred Prob | Observed Rate |
| :--- | :---: | :---: | :---: | :---: |
| Low Risk [0.00, 0.33) | [0.00, 0.33) | 1 | 0.048 | 0.000 |
| Medium Risk [0.33, 0.67) | [0.33, 0.67) | 6 | 0.512 | 0.667 |
| High Risk [0.67, 1.00] | [0.67, 1.01) | 17 | 0.899 | 0.412 |

---

## 4. Forward-Chaining Cross-Validation (Inside Training Seasons)

| Fold | Train Seasons | Val Season | Train N | Val N | LogReg Brier |
| :-: | :--- | :---: | :-: | :-: | :-: |
| 1 | 2021-22 | `2022-23` | 24 | 24 | 0.5858 |
| 2 | 2021-22, 2022-23 | `2023-24` | 48 | 24 | 0.2329 |

---

## 5. Leakage and Permutation Sanity Verification

- **Label-Shuffle Permutation Test**: Passed: `True` (N=50, Mean AUC=0.4688111888111888)
- **Cut-off Date Truncation**: All features strictly $\le$ January 31.
- **Model Artifact Serialized**: `models\satbhoomi-risk-v1.0-logreg-feat1-opt1th15-8bac5ab0-20261112.joblib`
