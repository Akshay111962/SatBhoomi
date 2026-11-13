# Raksha In-Season Farm Stress Alerts & Historical Replay (FR-008, Task T-09)

## 1. Overview & Agronomic Purpose
The **Raksha Alert Engine** provides automated, deterministic in-season monitoring for active crop loans during the winter (*Rabi*) wheat cropping cycle in Anand district, Gujarat. 

Its goal is early detection of emerging agronomic and economic drag—such as vegetative stunting, rainfall deficits, or market price collapses—to empower bank loan officers to deliver supportive interventions (e.g. crop insurance claim assistance, supportive field visits, and harvest-aligned repayment restructuring) long before harvest distress culminates.

---

## 2. In-Season Temporal Checkpoints
Rabi wheat in Gujarat is typically sown in November to early December and harvested in April. Alert monitoring occurs at three key vegetative checkpoints:

| Checkpoint Date | Crop Growth Stage | Agronomic Focus |
|:---|:---|:---|
| **Dec 15** | Early Tillering / Establishment | Early germination vigor, basal precipitation, early mandi price trend |
| **Jan 15** | Late Tillering / Jointing | Vegetative canopy expansion, winter moisture balance |
| **Jan 31** | Pre-Heading Cut-off Barrier | Terminal vegetative vigor prior to ear emergence; alignment with underwriting score cutoff |

---

## 3. Agronomic Detection Rules & Fixed Thresholds

All thresholds are derived from agronomic reasoning and are fixed in [`src/satbhoomi/alerts/config.py`](file:///d:/SatBhoomi/src/satbhoomi/alerts/config.py) prior to replay. No thresholds were adjusted post-hoc after inspecting replay outputs.

### 3.1 Crop Health Decline Rule
* **Comparison**: Compares the plot's NDVI on the checkpoint date against that plot's **own** NDVI on the identical calendar date in strictly prior completed seasons ($< \text{season}$).
* **Anti-Pattern Prohibited**: Early vegetative NDVI is **never** compared to the plot's reproductive peak or cross-plot averages.
* **Data Sufficiency Guard**: Requires a minimum of **2 clear observations** in the current season up to the checkpoint date and a minimum of **1 prior season** of historical observations for that plot.
* **Data Gap Handling**: If observations are insufficient, the engine emits status `data_gap`, raises **no alert**, and makes **no guesses or imputations**.
* **Thresholds**:
  * Drop $\ge 25.0\%$: **High Severity**
  * Drop $\ge 15.0\%$: **Medium Severity**
  * Drop $< 15.0\%$: **No Alert**

### 3.2 Winter Rainfall Deficit Rule
* **Rabi Irrigation Weighting**: Rabi wheat in Anand district is heavily irrigated (~87.5% tubewell and canal irrigation). Meteorological winter rainfall deficits are largely buffered by irrigation infrastructure.
* **Irrigation Capping**: 
  * For **irrigated plots** (`tube_well`, `canal`), severity is strictly **capped at Medium**, even under extreme deficits ($\le -50\%$). The alert explicitly notes that assured irrigation mitigates meteorological drag.
  * For **rainfed plots**, deficits $\le -50\%$ trigger **High Severity**, as unmitigated soil moisture deficits threaten crop survival.
  * Deficits between $-25\%$ and $-50\%$ trigger **Medium Severity** across all plots.

### 3.3 Mandi Price Crash Rule
* **Spatial Resolution**: Mandi prices are **district-level**, not plot-level (sourced from APMC Anand modal wheat auction prices).
* **Baseline Definition**: Modal price for the checkpoint month is compared against the historical mean modal price for the same calendar month in strictly prior seasons ($< \text{season}$).
* **Threshold**: A drop $\ge 15.0\%$ below the historical monthly baseline triggers a price alert. (Documented as an agronomic/economic assumption).
* **Ungrounded Triggers Removed**: An arbitrary coefficient-of-variation ($CV \ge 0.12$) trigger was removed because it lacks empirical justification in seasonal price dynamics.

---

## 4. In-Season Alert De-Duplication & Escalation
Managed by `InSeasonAlertTracker`:
1. **Single Alert Per Type**: For any plot and season, at most one active alert per alert type (`crop_health_drop`, `rainfall_deficit`, `price_crash`) is maintained.
2. **Severity Escalation**: If subsequent checkpoints indicate deteriorating conditions (e.g., from `medium` at Dec 15 to `high` at Jan 15), the severity is escalated to `high`, while preserving the original `detected_on` timestamp.
3. **Condition Normalization**: If conditions recover at subsequent checkpoints, the alert transitions to `resolved` and is archived in history, preventing duplicate spam.

---

## 5. Replay Results & Historical Evidence Disclosure

### 5.1 Historical Calamity Status
* **Zero Confirmed Calamity Events**: As documented in [`docs/DATA_REVISIT.md`](file:///d:/SatBhoomi/docs/DATA_REVISIT.md), zero official disaster, flood, or drought declarations were recorded for Anand district rabi wheat between 2020 and 2025.
* **Descriptive Reporting Only**: Historical replay is strictly descriptive. We do **not** claim that the alert engine "detects real stressed seasons" or "proves early warning" on historical data.

### 5.2 Full Historical Replay Metrics (2020–2025, 24 Plots)
Run via `python scripts/replay_alerts.py`:
* **Total Plots**: 24
* **Total Seasons**: 5 (2020-21 through 2024-25, 120 plot-seasons)
* **Alerts by Season**:
  * `2020-21`: 0 alerts (Baseline season; 0 prior seasons available $\to$ recorded as `data_gap`)
  * `2021-22`: 26 alerts
  * `2022-23`: 31 alerts
  * `2023-24`: 20 alerts
  * `2024-25`: 39 alerts
* **Alerts by Rule Type**:
  * `crop_health_drop`: 104 alerts
  * `rainfall_deficit`: 12 alerts
  * `price_crash`: 0 alerts (mandi prices remained stable/increasing from ₹2004/qtl to ₹2450/qtl)
* **Alerts by Severity**:
  * `high`: 81 alerts
  * `medium`: 35 alerts
  * `low`: 0 alerts

---

## 6. TC-007 Early Warning Detection (Synthetic Stress Scenario)

Because no external ground-truth disaster occurred in the historical window, **TC-007 is validated exclusively on a labelled synthetic stress scenario**:
* **Scenario Setup (`SYNTHETIC_STRESS_SCENARIO`)**: On plot `ANAND_WHEAT_01` in season `2023-24`, real Sentinel-2 observations are injected with a simulated 30% NDVI reduction on and after Dec 10.
* **Detection Date**: First alert triggered on **January 15, 2024**.
* **Harvest Date**: April 1, 2024.
* **Lead Time**: **11.0 weeks** ($\ge 6$ weeks required).
* **TC-007 Verdict**: **PASS** (passed on synthetic stress; clearly disclosed).

---

## 7. Zero Look-Ahead Leakage Invariance

The replay harness enforces strict temporal separation:
* At checkpoint $t$, only observations with date $\le t$ are evaluated.
* Baselines are strictly computed from prior seasons ($< \text{season}$).
* **Leakage Test**: Replaying on the complete historical dataset vs. a dataset where all post-checkpoint observations are truncated yields identical alerts (verified in `tests/unit/test_alerts.py::test_replay_leakage_truncation_invariance`).

---

## 8. Rule 2 Ethical Compliance & Supportive Action Playbooks

All alerts are framed strictly around **farm stress, repayment stress, and support needed**.
* **Target Audience**: Loan officer playbooks only. Alerts are never delivered directly to farmers.
* **Zero Recovery Pressure**: Alerts recommend supportive visits, verifying tubewell power/canal water, assisting with PMFBY crop insurance claims, and preparing harvest-aligned repayment schedules.
* **Banned Language Check**: 100% of alert headlines, details, and supportive actions pass the T-06 banned-words check (zero psychiatric terms, zero blame, zero coercion).

