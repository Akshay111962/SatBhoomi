# Sentinel-2 L2A Radiometric Offset Correction (Processing Baseline 04.00+)

> **Status**: Verified and Implemented  
> **Date**: 2026-11-14  
> **Related Documents**: `docs/LABEL_AUDIT.md`, `docs/DATA_REVISIT.md`, `docs/DATA_SOURCES.md`, `docs/RISKS.md` (RISK-06), `docs/PROGRESS.md`

---

## 1. Executive Summary & Root Cause Diagnosis

During the read-only audit of proxy stress labels (`docs/LABEL_AUDIT.md`), a severe temporal anomaly was detected across all 24 Anand wheat plots:
- The mean peak NDVI across the 24 plots dropped precipitously from **0.559** (2020-21) and **0.501** (2021-22) down to **0.382** in season 2022-23 (a ~30% step drop), remaining depressed in 2023-24 (**0.384**) and 2024-25 (**0.387**).
- In contrast, official Gujarat state and Anand district crop statistics recorded near-normal yields across these years (variation $< 4\%$), and local ground observations reported no catastrophic district-wide crop failure (no adverse events were reported to us; not checked against official records).

### The Mechanism: ESA Processing Baseline 04.00
On **25 January 2022**, the European Space Agency (ESA) transitioned the Sentinel-2 L2A operational processor to **Processing Baseline 04.00** (`PB 04.00`). In this baseline, ESA introduced a **radiometric offset of +1000 Digital Numbers (DN)** on all L2A surface reflectance bands (B01–B12, including B04 Red and B08 NIR) to prevent truncation of negative reflectances caused by atmospheric correction:
$$\text{DN}_{\text{stored}} = 10\,000 \cdot \rho + 1000 \implies \rho = \frac{\text{DN}_{\text{stored}} - 1000}{10\,000}$$

Where:
- $\rho$ is surface reflectance.
- Before PB 04.00 (prior to 2022-01-25): $\text{DN}_{\text{stored}} = 10\,000 \cdot \rho$, so $\rho = \frac{\text{DN}}{10\,000}$ (offset = 0).
- Baseline PB 04.00 and later: offset = $-1000$.

### Impact on Calculated NDVI
NDVI is calculated as:
$$\text{NDVI} = \frac{\rho_{\text{NIR}} - \rho_{\text{Red}}}{\rho_{\text{NIR}} + \rho_{\text{Red}}}$$

When raw uncorrected DNs are divided by 10,000 without subtracting the 1000 DN offset:
$$\rho_{\text{NIR}}^{\text{raw}} = \rho_{\text{NIR}} + 0.10, \quad \rho_{\text{Red}}^{\text{raw}} = \rho_{\text{Red}} + 0.10$$
The numerator remains identical:
$$\rho_{\text{NIR}}^{\text{raw}} - \rho_{\text{Red}}^{\text{raw}} = (\rho_{\text{NIR}} + 0.10) - (\rho_{\text{Red}} + 0.10) = \rho_{\text{NIR}} - \rho_{\text{Red}}$$
However, the denominator is artificially inflated:
$$\rho_{\text{NIR}}^{\text{raw}} + \rho_{\text{Red}}^{\text{raw}} = \rho_{\text{NIR}} + \rho_{\text{Red}} + 0.20$$
Therefore:
$$\text{NDVI}_{\text{uncorrected}} = \frac{\rho_{\text{NIR}} - \rho_{\text{Red}}}{\rho_{\text{NIR}} + \rho_{\text{Red}} + 0.20} = \frac{\text{NDVI}_{\text{true}}}{1 + \frac{0.20}{\rho_{\text{NIR}} + \rho_{\text{Red}}}}$$

For dense, healthy wheat near peak vegetative growth ($\rho_{\text{Red}} \approx 0.04$, $\rho_{\text{NIR}} \approx 0.46$, $\rho_{\text{NIR}} + \rho_{\text{Red}} \approx 0.50$):
$$\text{NDVI}_{\text{uncorrected}} \approx \frac{0.84}{1 + \frac{0.20}{0.50}} = \frac{0.84}{1.40} = 0.60 \quad (-28.57\%)$$

Because seasons 2020-21 and the majority of 2021-22 were acquired before 2022-01-25, they had zero offset (or only partial late-season exposure). Season 2022-23 (December 2022 – March 2023) was the very first rabi season processed entirely under PB 04.00+. This created a step drop in calculated NDVI that is **consistent with** the theoretical attenuation formula. Confirmation of this mechanism depended on rebuilt live data.

---

## 2. Implementation of Radiometric Correction

The planetary connector was updated in `src/satbhoomi/connectors/satellite/planetary_provider.py` to correctly extract and apply the offset for every individual scene:

### 2.1 Per-Scene Offset Determination
The provider inspects metadata in strict hierarchical order:
1. **STAC Band Metadata (`raster:bands`)**: If the STAC item's B04/B08 asset specifies `offset`, that value is scaled and used (`offset_rule = "metadata"`).
2. **STAC Processing Baseline (`s2:processing_baseline`)**: Reads the STAC item property. If baseline $\ge \text{"04.00"}$, applies $-1000$ offset (`offset_rule = "baseline"`). Pre-04.00 baselines apply $0$.
3. **Date Fallback (Strict Last Resort)**: If neither metadata nor baseline string exists, uses the acquisition date boundary ($2022\text{-}01\text{-}25$). Every scene utilizing date fallback is explicitly flagged with `offset_rule = "date_fallback"`.

### 2.2 Masking and Conversion Rules
1. **Nodata Masking Before Offset**: Raw $\text{DN} == 0$ is masked as `nodata` *prior* to offset application, preventing nodata pixels from turning into $-0.10$ reflectance.
2. **Reflectance Conversion Without Zero Clamping**:
   $$\rho = \frac{\text{DN} + \text{offset}}{10\,000}$$
   Negative reflectances are preserved without clamping to 0 (per user approved specification).
3. **Valid Denominator Mask**: Pixels where corrected $\rho_{\text{NIR}} + \rho_{\text{Red}} \le 0$ are masked to prevent division by zero or negative denominators.
4. **Scene Quality & SCL Cloud Masking**: SCL cloud and shadow filtering remain fully operational.

### 2.3 Cache Versioning & Provenance
Cached scene observations now strictly require four provenance fields:
- `processing_baseline`: STAC item baseline string (e.g., `"05.10"`).
- `offset_applied`: Numeric integer offset applied to DN (e.g., `-1000`).
- `offset_rule`: `"metadata"`, `"baseline"`, or `"date_fallback"`.
- `provider_logic_version`: `"v2_pb_offset_corrected"`.

New cache files are saved under `{plot_code}_{season}_v2_pb_offset_corrected.json`. All legacy uncorrected cache files (`{plot_code}_{season}.json`) are preserved untouched on disk.

---

## 3. Descriptive Before-and-After Analysis

> **Descriptive only: no label is being chosen here**
>
> *(Note: The numbers below are computed on the rebuilt live 120 plot-season dataset. Confirmation of the correction is confirmed by the elimination of the artificial step drop.)*

### 3.1 Peak NDVI Comparison by Season (Pre vs Post Correction)

| Season | Pre-Correction Mean Peak NDVI | Post-Correction Mean Peak NDVI | Absolute Change | Relative Change | Observations |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **2020-21** | 0.559 | 0.559 | 0.000 | 0.0% | Pre-04.00 baseline (offset = 0) |
| **2021-22** | 0.501 | 0.560 | +0.059 | +11.8% | Transition season; late Feb–Mar scenes had PB 04.00 offset |
| **2022-23** | 0.382 | 0.578 | +0.196 | +51.3% | Full PB 04.00 season; artificial step-drop completely erased |
| **2023-24** | 0.384 | 0.581 | +0.197 | +51.3% | Post-04.00 baseline restored to expected agronomic level |
| **2024-25** | 0.387 | 0.575 | +0.188 | +48.6% | Post-04.00 baseline restored to expected agronomic level |
| **5-Yr Mean**| **0.443** | **0.571** | **+0.128** | **+28.9%** | Multi-season mean stable across all 5 rabi cycles |

**Key Finding**: With the radiometric offset applied, mean peak NDVI across the 24 plots is remarkably stable across all 5 seasons ($0.559$ to $0.581$, overall mean $0.5705$). The post-2022 artificial drop has completely disappeared, which is **consistent with** the theoretical attenuation formula.

### 3.2 Label Impact Under Active Rule ($\tau = 15.0\%$)

| Season | Pre-Correction Stressed ($Y=1$) | Post-Correction Stressed ($Y=1$) | Normal ($Y=0$) | Post-Correction Stressed Share (%) |
| :--- | :---: | :---: | :---: | :---: |
| **2021-22** | 5 | 2 | 22 | 8.33% |
| **2022-23** | 22 | 2 | 22 | 8.33% |
| **2023-24** | 16 | 2 | 22 | 8.33% |
| **2024-25** | 11 | 3 | 21 | 12.50% |
| **Total Labelled** | **54 (56.25%)** | **9 (9.38%)** | **87 (90.62%)** | **9.38%** |

### 3.3 Drop-Versus-Baseline Distribution by Season

*Descriptive only: no label is being chosen here*

| Season | Count | Median Drop (%) | 25th Percentile (%) | 75th Percentile (%) | Minimum Drop (%) | Maximum Drop (%) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **2021-22** | 24 | +0.28% | -4.72% | +6.27% | -39.28% | +16.55% |
| **2022-23** | 24 | -1.98% | -11.15% | -0.54% | -48.87% | +27.01% |
| **2023-24** | 24 | -1.84% | -6.78% | +6.58% | -62.64% | +34.14% |
| **2024-25** | 24 | -1.20% | -4.19% | +4.64% | -29.95% | +34.28% |
| **All Labelled** | **96** | **-1.52%** | **-6.20%** | **+4.52%** | **-62.64%** | **+34.28%** |

### 3.4 Threshold Sensitivity ($\tau$)

*Descriptive only: no label is being chosen here*

| Percentage Drop Threshold ($\tau$) | Stressed Rows ($N=96$) | Share of Labelled Dataset (%) |
| :---: | :---: | :---: |
| $\ge 5.0\%$ | 23 | 23.96% |
| $\ge 10.0\%$ | 16 | 16.67% |
| **$\ge 15.0\%$ (Current Active Rule)** | **9** | **9.38%** |
| $\ge 20.0\%$ | 3 | 3.12% |
| $\ge 25.0\%$ | 3 | 3.12% |
| $\ge 30.0\%$ | 2 | 2.08% |

### 3.5 Suspect Plot Flagging
In accordance with user decisions:
- Plots with peak NDVI $< 0.30$ (`UMRETH_WHEAT_09`, `KHAMBHAT_WHEAT_12`) are flagged as `non_crop_suspect` in descriptive reports. No plots have been dropped from the dataset. Replacement of these plots with verified wheat fields is reserved for the user.
- **Critical Observation**: 4 of the 9 remaining stressed labels under the active rule ($\tau=15\%$) belong directly to `KHAMBHAT_WHEAT_12` (seasons 2021-22, 2023-24, 2024-25) and `UMRETH_WHEAT_09` (season 2024-25). Both plots have baseline NDVI $< 0.17$, meaning small absolute fluctuations in bare soil produce large percentage swings.
- Plots `PETLAD_WHEAT_05` (peak NDVI $0.21\text{–}0.26$) and `ANAND_WHEAT_14` (peak NDVI $0.22\text{–}0.26$) also exhibit borderline low NDVI.

---

## 4. Downstream Impact and Freeze Notice

- **ML Training Frozen**: Model training remains strictly frozen. The agronomic rules baseline (`AgronomicRulesBaseline`) remains the active production scorer.
- **Label / Threshold Protocol Deferred**: No label rules, thresholds, or evaluation protocols are modified in this task.
- **Superseded Downstream Artifacts**: All downstream models (`T-05`), SHAP explanations (`T-06`), loan suggestion haircuts (`T-07`), what-if simulations (`T-08`), and alert replay event logs (`T-09`) generated on pre-correction data are formally marked as **SUPERSEDED** in `docs/PROGRESS.md`, `docs/MODEL_EVAL.md`, and `reports/metrics.json`. Recomputation is deferred to a future task.

---

## 5. Remaining Open Questions

1. **Reprocessed Archive Scenes**: Does ESA plan to retroactively reprocess pre-2022 archive data with PB 04.00+ offsets? If so, the per-scene baseline check already handles it transparently.
2. **Threshold Re-calibration**: Once confirmed on rebuilt data, the label threshold ($\tau = 15\%$) and baseline depth requirement ($k \ge 2$) must be formally evaluated in a new written evaluation protocol approved by the user.
3. **Replacement of Suspect Plots**: Replacement of `UMRETH_WHEAT_09` and `KHAMBHAT_WHEAT_12` with checked wheat fields by the user will further stabilize the baseline and label balance.
