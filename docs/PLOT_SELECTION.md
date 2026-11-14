# Sample Plot Selection and Exclusion Protocol

> **Date**: 2026-11-14  
> **Status**: Approved and Pre-Declared  
> **Authority**: Pre-declared rules fixed before application  
> **Source Output**: `reports/ndvi_summary.json` (SHA-256 verifiable)  
> **Related Documents**: `docs/PROJECT_CONTEXT.md`, `docs/ENGINEERING_RULES.md`, `docs/NDVI_CORRECTION.md`, `docs/LABEL_AUDIT.md`, `docs/DATA_SOURCES.md`

---

## 1. Context and Objective

During the multi-season radiometric reconciliation of Sentinel-2 surface reflectance (Processing Baseline PB 04.00+), three sample plots demonstrated persistent vegetative silence across all five observed rabi cycles (2020-21 through 2024-25), with maximum peak NDVI remaining well below 0.30 in every single season. 

In agrarian Anand district, irrigated wheat typically peaks between 0.55 and 0.85 NDVI. Peak values consistently below 0.30 reflect non-crop land cover (such as bare saline flats, permanent fallow, or non-vegetated surfaces) rather than agricultural stress.

This document formalizes the objective, uniform plot selection and exclusion rules applied across the sample plot dataset.

---

## 2. Pre-Declared Selection Rules

### Rule R1: Uniform Multi-Season Non-Crop Exclusion
- **Definition**: A plot is excluded if and only if its peak NDVI is below **0.30** in every one of the 5 observed rabi seasons ($\max_{s \in S}(\text{peak\_ndvi}_s) < 0.30$).
- **Strict Independence**: The exclusion rule is purely biophysical; it does **not** use any stress label, any season-to-season change, or any rainfall/yield proxy.
- **Application**: Applied uniformly across all 24 sample plots.
- **Data Source**: Derived directly from the deterministic PB 04.00 corrected satellite observations audited in `reports/ndvi_summary.json`.

### Rule R2: Borderline Plots Retention
- **Definition**: Plots with a 5-season mean peak NDVI below **0.40** that are **not** excluded by R1 (i.e., having at least one season with peak NDVI $\ge 0.30$) are retained as **ACTIVE**.
- **Action**: These plots are preserved in the active dataset and explicitly flagged as `borderline` for transparent sensitivity analysis in downstream evaluations.

### Rule R3: Scope & Replacement Policy
- **Active Set**: The active dataset comprises the original sample plots minus the plots excluded under R1 (24 total rows $- 3$ excluded $= 21$ active plots).
- **No Candidate Replacements in Current Scope**: Candidate replacement plots are not added in this task.
- **Written Procedure Required**: Any addition of replacement or expansion sample plots in the future must follow a written, approved protocol specifying geographic constraints, pre-screening criteria, and unbiased temporal selection before any live data ingestion.

---

## 3. Exclusion and Retention Results

Based on the verified metrics in `reports/ndvi_summary.json`:

### 3.1 Plots Meeting Rule R1 (Excluded)

| Plot Code | 5-Yr Min Peak | 5-Yr Mean Peak | 5-Yr Max Peak | Taluka / District | Exclusion Status | Reason |
| :--- | :---: | :---: | :---: | :--- | :---: | :--- |
| **`KHAMBHAT_WHEAT_12`** | 0.0677 | 0.0910 | 0.1316 | Khambhat, Anand | **EXCLUDED** | Non-crop signal: peak NDVI below 0.30 in all seasons |
| **`PETLAD_WHEAT_05`** | 0.2155 | 0.2393 | 0.2618 | Petlad, Anand | **EXCLUDED** | Non-crop signal: peak NDVI below 0.30 in all seasons |
| **`UMRETH_WHEAT_09`** | 0.1031 | 0.1517 | 0.2290 | Umreth, Anand | **EXCLUDED** | Non-crop signal: peak NDVI below 0.30 in all seasons |

*Total Excluded: 3 plots.*

### 3.2 Plots Meeting Rule R2 (Borderline — Retained as Active)

| Plot Code | 5-Yr Min Peak | 5-Yr Mean Peak | 5-Yr Max Peak | Taluka / District | Status | Flag |
| :--- | :---: | :---: | :---: | :--- | :---: | :--- |
| **`ANAND_WHEAT_13`** | 0.3132 | 0.3542 | 0.3838 | Anand, Anand | **ACTIVE** | `borderline` |
| **`ANAND_WHEAT_14`** | 0.2237 | 0.2654 | 0.3254 | Anand, Anand | **ACTIVE** | `borderline` |
| **`TARAPUR_WHEAT_11`** | 0.2100 | 0.2531 | 0.3657 | Tarapur, Anand | **ACTIVE** | `borderline` |

*Total Borderline (Retained): 3 plots.*

### 3.3 Clear Crop Plots (Retained as Active)
The remaining 18 plots demonstrate typical robust wheat vegetative dynamics, with 5-year maximum peak NDVI exceeding 0.40 (ranging up to 0.8820).

*Total Active Plots: 21 plots ($18 \text{ clear} + 3 \text{ borderline}$).*

---

## 4. Preservation & Non-Destructive Storage Policy

In accordance with engineering guidelines and user decisions:
1. **Zero Row Deletions**: No row is deleted from `data/synthetic/sample_plots.csv`. Excluded plots are retained on disk with `status = "excluded"`, `exclusion_reason`, and `exclusion_date = "2026-11-14"`.
2. **No Code Reuse**: Excluded plot codes are permanently retired and cannot be reused by future replacement plots.
3. **Downstream Enforcement**: The sample plot loader (`satbhoomi.connectors.satellite.loader.load_sample_plots`) filters for `status == "active"` by default, preventing any downstream fetch, feature building, model scoring, or alert replay from processing excluded plots.
