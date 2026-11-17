# SatBhoomi Score + Raksha — Demo Run Sheet (6–7 Minutes)

## Pre-Demo Checklist
- [ ] Database fresh: Run `powershell -File scripts/demo_setup.ps1 -Reset`.
- [ ] Pre-flight verified: Run `powershell -File scripts/demo_check.ps1` (all PASS).
- [ ] Git tag verified (`v1.0-demo`), demo DB and model files backed up.
- [ ] Laptop charged, offline mode verified (turn off Wi-Fi to prove zero live network calls).

---

## Flow 1: Pre-Disbursal Credit Risk Assessment (3.5 min)
1. **Login (S1)**: Log in with username `demo_officer` and prompted password.
   - *Say*: "SatBhoomi is an AI farm credit scoring and early-warning decision-support tool for bank loan officers."
2. **Plot Portfolio (S2)**: Open dashboard; view 21 synthetic wheat plots in Anand, Gujarat.
   - *Say*: "We evaluate multi-season satellite vegetation (Sentinel-2 NDVI), rainfall anomalies, and mandi prices."
   - *DO NOT CLAIM*: "These are real farmers." *(Say: Sample coordinates and centroids, not individual surveyed farmers).*
3. **Risk Assessment (S4)**: Select plot `ANAND_WHEAT_01` (Season 2024-25).
   - *Show*: Calibrated score (35), risk band (`low`), top 3 plain-language reasons, and indicative credit limit.
   - *Say*: "SHAP-style attribution explains why the score was assigned. Scale of finance bounds the credit limit."
   - *DO NOT CLAIM*: "The AI approves or denies loans." *(Say: Human loan officer makes all final lending decisions).*
4. **What-If Simulator (S5)**: Toggle crop insurance to 'Yes' (`insured=1`).
   - *Show*: Real-time score projection (35 $\to$ 25), delta (-10), and mandatory "estimate" disclaimer.
   - *Say*: "Shows model sensitivity under prospective interventions to assist agronomic advisory."
   - *DO NOT CLAIM*: "This proves insurance causes higher yields." *(Say: Prospective sensitivity estimate, not proof of causation).*

---

## Flow 2: In-Season Stress & Relief Evidence (3 min)
1. **In-Season Monitoring (S6)**: Open monitoring timeline for `ANAND_WHEAT_01`.
   - *Show*: Checkpoint NDVI curve, cumulative rainfall deficit, and detected stress alert.
   - *DO NOT CLAIM*: "This is real-time satellite telemetry." *(Say: Historical seasonal replay with temporal truncation).*
2. **Supportive Action Playbook (S7)**: Click alert $\to$ log a supportive field visit.
   - *Say*: "The Raksha module prescribes supportive playbooks—field visits and restructuring—never coercive recovery."
3. **Disaster Relief Report (S8)**: Open printable relief evidence report.
   - *Show*: Benchmark comparison against the statutory **RBI 33% calamity threshold**.
   - *Say*: "Provides objective satellite damage evidence to accelerate official debt rescheduling."
4. **Farmer Summary (S9)**: Preview vernacular summary in Gujarati/Hindi.
   - *DO NOT CLAIM*: "Legally certified translation." *(Say: Unreviewed AI draft preview; officer must verify).*

---

## Backup Plan
- **Primary Failure**: If Streamlit halts, restart backend and UI in separate PowerShell windows.
- **Secondary Failure**: If local port hangs, present offline screenshots of screens S1–S9 or playback backup video walkthrough.
