# SatBhoomi Ground-Truth Outcome Data Discovery Plan

**Document Type**: Field Inquiry Guide & Interview Protocol  
**Date**: November 2026  
**Status**: DRAFT / UNVERIFIED  
**Target Region**: Anand District, Gujarat, India  
**Target Crop**: Rabi Wheat (*Triticum aestivum*)  

---

## 1. Purpose and Non-Existence Disclaimer

> [!IMPORTANT]
> **Explicit Disclaimer**: No claim is made that these datasets currently exist in open, digitized, or accessible form for Anand district. All items in this plan represent exploratory research questions to be investigated through stakeholder interviews. SatBhoomi does NOT assume access to private banking records or proprietary insurance logs.

To unlock formal Machine Learning evaluation under `docs/EVAL_PROTOCOL.md` (Protocol v2), empirical ground truth must replace or complement satellite vegetative proxies. This document outlines targeted interview questions for local agricultural lenders, state agriculture officers, and crop insurers to determine what ground-truth datasets exist and under what regulatory terms they could be accessed.

---

## 2. Target Stakeholder Groups

1. **Lead District Bank (LDB) & Commercial / Cooperative Bank Officers**:
   - Rural branch managers handling Kisan Credit Card (KCC) portfolios for wheat farmers in Anand, Petlad, Khambhat, and Umreth talukas.
2. **District Agriculture Department & Krishi Vigyan Kendra (KVK) Officials**:
   - Agronomists and extension officers supervising Crop-Cutting Experiments (CCEs) and seasonal crop advisories.
3. **PMFBY Insurance Nodal Officers / Implementing Insurance Companies**:
   - Representatives managing the Pradhan Mantri Fasal Bima Yojana (PMFBY) cluster in Anand district.

---

## 3. Interview Question Inventory

### Category A: Crop Insurance Claims (PMFBY)
*Target: PMFBY Nodal Officers and District Agriculture Statistics Officers*

1. **Spatial Granularity**: At what administrative level are PMFBY threshold yields and indemnity payouts calculated for Rabi wheat in Anand district (Notified Area: Gram Panchayat, Village, or Taluka)?
2. **Historical Record Depth**: Are multi-year (e.g., 2020–2025) historical claim settlement ratios or shortfall percentages archived and accessible for research purposes?
3. **Settlement Lag**: What is the typical elapsed time between Rabi harvest (March–April) and final claim settlement/disbursement to farmers?
4. **Data Format & Access**: Is historical claim payout data maintained in digitized relational databases (e.g., NCIP portal exports) or offline paper registers?

### Category B: Crop-Cutting Experiment (CCE) Yield Records
*Target: District Statistical Officers, Taluka Revenue Inspectors, and KVK Agronomists*

1. **Sampling Density**: How many randomized CCE plots are harvested per village or Gram Panchayat for Rabi wheat each season?
2. **Measurement Variables**: Do CCE records capture green weight, dry weight, moisture percentage, and sowing/harvest dates, or only estimated yield (kg/ha)?
3. **Georeferencing**: Are CCE harvesting locations georeferenced with GPS coordinates (e.g., via the CCE Agri mobile application), and can plot boundaries be correlated with Sentinel-2 tiles?
4. **Data Availability**: Under what government data-sharing framework or institutional MoU can anonymized CCE yield distributions be accessed for academic/research benchmarking?

### Category C: KCC Loan Repayment and Delinquency
*Target: Bank Branch Managers, PACS Secretaries, and Agricultural Loan Officers*

1. **Repayment Cycles**: How strictly does the KCC repayment schedule align with the Rabi wheat harvest window in Anand? When is an overdue account officially categorized as SMA (Special Mention Account) or NPA (Non-Performing Asset)?
2. **Aggregation Options**: Can lenders provide village-level or branch-level anonymized delinquency rates (e.g., percentage of overdue KCC wheat loans per panchayat) to eliminate borrower privacy risks?
3. **Distress Drivers**: From bank branch experience, what percentage of seasonal defaults in Anand wheat are driven by biophysical crop failure versus market price crashes or strategic non-repayment?

### Category D: Regulatory Compliance, Privacy & Consent (DPDP Act 2023)
*Target: Bank Compliance Officers and Legal Counsel*

1. **Data Protection Constraints**: Under India's Digital Personal Data Protection (DPDP) Act 2023, what consent architecture is required if satellite monitoring data is coupled with farmer credit appraisal?
2. **Anonymization Thresholds**: What minimum cluster size (e.g., k-anonymity $\ge 50$ farmers per village) is required to prevent individual farmer de-anonymization?
3. **Regulatory Sandbox**: Is there an opportunity to evaluate satellite-assisted risk indicators under the Reserve Bank Innovation Hub (RBIH) or RBI Regulatory Sandbox for agricultural lending?

---

## 4. Next Steps & Tracking

- Conduct structured interviews with at least 2 bank credit officers and 1 district agriculture official.
- Record responses as purely qualitative field notes without modifying any codebase feature, threshold, or model logic.
- If an anonymized, audited ground-truth dataset with $\ge 5$ verified distress outcomes in the test partition is secured and validated, pre-register an updated protocol before unfreezing ML evaluation.
