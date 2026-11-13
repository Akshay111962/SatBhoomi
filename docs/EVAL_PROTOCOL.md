# SatBhoomi Model Evaluation and Validation Protocol (T-05)

**Status**: APPROVED  
**Date**: November 2026  
**Document Type**: Evaluation Protocol & Experimental Pre-Registration  
**Target Crop & Geography**: Wheat (*Triticum aestivum*), Rabi Season, Anand District, Gujarat, India  

---

## 1. Protocol Pre-Registration Notice

In accordance with the radical honesty and scientific integrity rules of SatBhoomi Score + Raksha (`docs/PROJECT_CONTEXT.md` and `docs/ENGINEERING_RULES.md`), this protocol is committed and fixed **prior to executing any model training, hyperparameter tuning, or held-out scoring**. 

No modelling choices, thresholds, or feature selections may be altered based on retrospective held-out performance.

---

## 2. A1: Temporal Split and Forward-Chaining Protocol

### Primary Split: Strictly Time-Based Train / Held-Out Test
To mirror real-world agricultural credit underwriting, where historical observations are used to evaluate upcoming loans, evaluation strictly enforces a temporal train-test partition:

- **Historical Baseline Initialization Season**: `2020-21` (24 rows).  
  *Quarantined from training and testing* due to `label_unavailable = True` under the approved expanding baseline rule (Option 1 in `docs/LABEL_RULE.md`).
- **Training Seasons ($t < \text{newest}$)**: `2021-22`, `2022-23`, `2023-24`.  
  *Total Training Instances*: **72 labelled rows** (24 plots $\times$ 3 completed seasons: 43 stressed, 29 normal).
- **Held-Out Test Season ($t = \text{newest}$)**: `2024-25`.  
  *Total Held-Out Test Instances*: **24 labelled rows** (24 plots $\times$ 1 season: 11 stressed, 13 normal).

> **Strict Holdout Boundary**:  
> The newest season (`2024-25`) is quarantined from all model exploration, feature selection, scaling transformations, and hyperparameter tuning. It is evaluated **exactly once** at the conclusion of model selection.

### Secondary Split: Multi-Season Forward-Chaining (Rolling Temporal CV)
Because a single held-out season with 24 plots is subject to seasonal weather anomalies, we pre-register forward-chaining cross-validation inside the 96 labelled rows as a secondary, more stable cross-temporal generalization estimate:

| Fold | Training Seasons | Training Rows | Test Season | Test Rows | Purpose |
| :-: | :--- | :-: | :---: | :-: | :--- |
| **Fold 1** | `2021-22` | 24 | `2022-23` | 24 | In-training model selection & hyperparameter tuning |
| **Fold 2** | `2021-22`, `2022-23` | 48 | `2023-24` | 24 | In-training model selection & hyperparameter tuning |
| **Fold 3** (Final) | `2021-22`, `2022-23`, `2023-24` | 72 | `2024-25` | 24 | **Final Held-Out Benchmark** (evaluated once) |

---

## 3. A2: Baseline Models

Per Architecture Decision ADR-2 (*"Rules baseline first, ML second"*), Machine Learning is justified only if it outperforms transparent, agronomic heuristic baselines. We evaluate three distinct baselines, each exposing a calibrated probability output $\hat{p} \in [0, 1]$:

### 1. Majority-Class / No-Skill Baseline
- **Definition**: Predicts the constant empirical event rate of the training dataset:
  $$\hat{p}_i = \frac{1}{N_{\text{train}}} \sum_{j=1}^{N_{\text{train}}} y_j$$
- **Theoretical AUC**: Exactly $0.500$.

### 2. Persistence Baseline (Markovian Lag)
- **Definition**: Assumes that plot health is temporally autocorrelated; a plot suffering vegetative stress in the immediately preceding completed season ($t-1$) is likely to remain stressed in season $t$ (e.g. persistent soil degradation, drainage issues, or continued water scarcity).
- **Rule**:
  $$\hat{p}_i = \begin{cases} 0.80 & \text{if } \text{past\_stressed\_seasons\_count increased at } t-1 \\ 0.20 & \text{otherwise} \end{cases}$$

### 3. Agronomic Rules Baseline
- **Agronomic Theory**: Wheat in Anand is sown in November and reaches stem elongation by January 31. Stunted early canopy greenness (`ndvi_early` below historical plot norms, or negative growth velocity `ndvi_trend_pre_cutoff` $< 0$) compounded by winter rainfall deficits indicates early crop distress.
- **Rule and Fixed Thresholds** (derived strictly from historical training knowledge):
  - Condition 1 (Vegetative Lag): `ndvi_early` $\le 0.35$ OR `ndvi_trend_pre_cutoff` $\le 0.0$
  - Condition 2 (Pre-Cutoff Rain Deficit): `rain_pre_cutoff_deficit_pct` $\le -20.0\%$
- **Scoring Function**:
  $$\hat{p}_i = \begin{cases} 0.85 & \text{if Condition 1 AND Condition 2 both hold (Compound Stress)} \\ 0.45 & \text{if either Condition 1 OR Condition 2 holds (Partial Stress)} \\ 0.10 & \text{if neither condition holds (Normal Vegetative Progression)} \end{cases}$$
- **Agronomic Qualification**: Rainfall is a secondary signal for Anand district wheat because $> 85\%$ of plots operate under canal or tube-well irrigation; vegetative satellite indices (`ndvi_early`, `ndvi_trend_pre_cutoff`) carry the dominant early diagnostic weight.

---

## 4. A3: Model Candidates and Hyperparameter Search Grids

With small sample datasets (36 training rows), high-capacity non-linear models face severe risks of overfitting. We enforce a **strong simplicity preference**: if a regularized linear model performs within $1.0$ standard error of an ensemble model during cross-validation, the simpler model is selected.

All models are seeded with fixed seed `random_state = 42`.

### 1. Regularized Logistic Regression (Ridge / L2)
- **Preprocessing**: `StandardScaler` fitted strictly on training data (no scaling parameters fit on test). Missing inputs imputed with median of training fold.
- **Grid**:
  - `C`: `[0.01, 0.1, 1.0, 10.0]`
  - `class_weight`: `["balanced", None]`
  - `penalty`: `["l2"]`

### 2. Shallow Random Forest Classifier
- **Grid**:
  - `n_estimators`: `[25, 50]`
  - `max_depth`: `[2, 3]`
  - `min_samples_split`: `[3, 5]`
  - `max_features`: `["sqrt", 0.5]`

### 3. Shrinkage Extreme Gradient Boosting (XGBoost)
- **Grid**:
  - `n_estimators`: `[20, 40]`
  - `max_depth`: `[2, 3]`
  - `learning_rate`: `[0.05, 0.1]`
  - `subsample`: `[0.8, 1.0]`
  - `colsample_bytree`: `[0.8, 1.0]`

---

## 5. A4: Metrics and Uncertainty Estimation

### Metrics Portfolio
1. **Area Under the ROC Curve (ROC-AUC)**: Primary ranking and discrimination metric.
2. **Precision-Recall AUC (PR-AUC / Average Precision)**: Emphasizes precision over the minority stressed class.
3. **Brier Score**: Proper scoring rule measuring probability calibration mean squared error:
   $$\text{BS} = \frac{1}{N} \sum_{i=1}^{N} (\hat{p}_i - y_i)^2$$
4. **Reliability (Calibration) Table**: Evaluates predicted probabilities binned into 3 coarse risk buckets appropriate for small sample sizes:
   - Low Risk: $[0.00, 0.33)$
   - Medium Risk: $[0.33, 0.67)$
   - High Risk: $[0.67, 1.00]$

### Uncertainty Estimation: Plot-Level Cluster Bootstrap
Individual observations from the same farm plot over time are longitudinally correlated. Standard row-wise bootstrap invalidates independent error assumptions.

- **Bootstrap Protocol**:
  - Number of resamples: $B = 1,000$.
  - Resampling unit: Cluster-level resampling of unique `plot_code` identifiers with replacement.
  - Compute 95% empirical bootstrap confidence interval: $[CI_{2.5\%}, CI_{97.5\%}]$.
- **Probability Calibration**: Post-hoc isotonic or Platt calibration is explicitly prohibited; with 36 training rows, fitting calibration mapping introduces extreme variance.

### Subgroup Reporting by Plot Size
Plots are grouped into size categories based on acreage ($< 2.0\text{ acres}$ vs. $\ge 2.0\text{ acres}$). If any subgroup in the test partition has $< 5$ instances, subgroup metrics are flagged as statistically underpowered and reported qualitatively.

---

## 6. A5: Pre-Committed Success Criteria and Reporting Commitments

The blueprint specifies the following benchmark criteria:
> **Target**: Held-out test season ROC-AUC $\ge 0.70$ AND beats the heuristic rules baseline, with reported 95% confidence intervals.

We pre-register the exact scientific narrative for all potential outcomes:

### Outcome 1: Criteria Fully Met
- **Condition**: $\text{AUC}_{\text{held-out}} \ge 0.70$ AND $\text{AUC}_{\text{held-out}} > \text{AUC}_{\text{rules\_baseline}}$, with lower 95% CI bound $> 0.50$.
- **Paper Statement**: Machine learning extracts subtle multi-source interactions (vegetative momentum + price volatility + moisture anomaly) that improve early underwriting discrimination over transparent agronomic thresholds on smallholder wheat.

### Outcome 2: Criteria Partially Met (Rules Baseline Wins)
- **Condition**: $\text{AUC}_{\text{held-out}} \ge 0.70$, but does not statistically exceed the agronomic rules baseline.
- **Paper Statement**: While ML models achieve acceptable discrimination, they do not outperform a transparent, zero-parameter agronomic heuristic rule. In accordance with banking explainability requirements (ADR-2), the rules baseline is recommended for loan officer deployment.

### Outcome 3: Criteria Not Met / Wide Confidence Interval
- **Condition**: $\text{AUC}_{\text{held-out}} < 0.70$ OR the 95% bootstrap confidence interval spans 0.50 (e.g. $[0.42, 0.78]$).
- **Paper Statement**: Due to small sample scale (12 plots) and the proxy nature of satellite stress labels, machine learning models do not demonstrate statistically reliable predictive signal over no-skill guessing. The paper openly documents this limitation and identifies the necessity of statewide multi-district expansion and true bank default records.

---

## 7. A6: Sanity Checks for Stage B

During training execution, the pipeline must pass three mandatory sanity checks:

1. **Label-Shuffle Permutation Test**:
   - Randomly permute the training labels $y_{\text{train}}$ 50 times and re-evaluate on the held-out season.
   - Mean permuted AUC must fall in $[0.45, 0.55]$. If permuted AUC exceeds $0.60$, execution halts immediately due to structural feature leakage.
2. **Leakage Truncation Integrity**:
   - Re-execute the automated truncation test from T-04 to confirm that model training code imports zero features derived after January 31.
3. **Feature Importance Bounds**:
   - Confirm that no single feature captures $> 70\%$ of model attribution weight, preventing single-feature proxy collapse.

---

## 8. A7: Model Versioning String Standard

Every model artifact serialized to disk and stored with risk assessments must follow the standardized format:

$$\text{model\_version} = \text{satbhoomi-risk-v1.0-}\{\text{algorithm}\}\text{-feat1-opt1th15-}\{\text{data\_hash[:8]}\}\text{-}\{\text{YYYYMMDD}\}$$

*Example*: `satbhoomi-risk-v1.0-logreg-feat1-opt1th15-a7b3c2d1-20261105`

---

## 9. Dependencies Required (Python 3.13 Compatibility)

Implementation in Stage B requires:
- `scikit-learn>=1.4.0` (Supported on Python 3.13 wheels)
- `xgboost>=2.0.3` (Supported on Python 3.13 wheels)

*Request*: Permission to add `scikit-learn` and `xgboost` to `pyproject.toml` and install them into `.venv`.

