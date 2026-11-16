# SatBhoomi Streamlit Officer Dashboard Notes (Screens S1 to S9)

This document records the endpoint mappings, design choices, and known operating limitations for the bank officer decision-support interface.

---

## 1. Screen to API Endpoint Mapping

| Screen ID | Screen Name | FastAPI Endpoint Called | Description & Key Parameters |
| :--- | :--- | :--- | :--- |
| **S1** | Officer Login | `POST /api/v1/auth/login` | Authenticates officer credentials; returns JWT stored strictly in `st.session_state`. |
| **S2** | Dashboard | `GET /api/v1/plots` | Paginated plot portfolio envelope (`limit`, `offset`, optional `district` filter). |
| **S3** | Register Plot | `POST /api/v1/plots` | Registers parcel attributes with client-side and server-side validation error mapping. |
| **S4** | Risk Assessment | `POST /api/v1/plots/{id}/assessments`<br>`GET /api/v1/assessments/{id}` | Runs baseline scoring; returns score, band, 3 plain reasons, and indicative DLTC loan limits. |
| **S5** | What-If Simulator | `POST /api/v1/assessments/{id}/what-if` | Projects score & limit impacts given controllable interventions (`insured`, `irrigation`). |
| **S6** | In-Season Monitoring | `GET /api/v1/plots/{id}/monitoring` | Serves historical checkpoint replay timeline, NDVI trajectory chart, and active alerts. |
| **S7** | Alert Playbook | `POST /api/v1/alerts/{id}/actions` | Logs supportive officer intervention from fixed playbook (`field_visit`, `insurance_claim_help`, etc.). |
| **S8** | Relief Evidence Report | `GET /api/v1/plots/{id}/relief-report` | Calamity loss screening comparing in-season NDVI to baseline against RBI 33% threshold. |
| **S9** | Farmer Summary | `GET /api/v1/assessments/{id}/farmer-summary` | Plain-language vernacular summary in English (`en`), Gujarati (`gu`), or Hindi (`hi`). |

---

## 2. Design Guardrails & Ethical Compliance

1. **Human-in-the-Loop Authority**:
   - Zero automated loan approval, rejection, sanction, or disbursement buttons anywhere in the interface.
   - All screens clearly state that credit decisions and relief determinations reside exclusively with the authorized loan officer and relief committees.
2. **Supportive Language Framing**:
   - Strictly no recovery pressure, repossession, or automated collection notices.
   - S7 features prominent guidance: *"If a farmer is visibly distressed, involve a senior colleague and local support and do not handle it alone."*
3. **High-Contrast & Dual-Channel Signaling**:
   - Color is never the sole visual signal: numeric scores are always accompanied by large text band labels (`LOW RISK`, `MEDIUM RISK`, `HIGH RISK`).
   - Alert severities are rendered with text tags (`[HIGH SEVERITY]`, `[MEDIUM SEVERITY]`, `[LOW SEVERITY]`).
4. **Data Privacy & Zero PII**:
   - No farmer names, personal telephone numbers, or Aadhaar/ID numbers appear or are accepted by inputs.

---

## 3. Known Limitations & Technical Disclosures

1. **Replay Not Live Monitoring**:
   - In-season monitoring (Screen S6) serves pre-computed **historical seasonal replay** data from prior seasons. It is not live real-time monitoring and makes no claim of detecting real-world stress events.
2. **Translations Unreviewed (Preview Only)**:
   - Vernacular text (Screen S9) for Gujarati and Hindi is generated via deterministic templates.
   - Any translation where `source != 'reviewed'` is strictly isolated inside the yellow warning box: *"Unreviewed translation: officer preview only. Do not show to a farmer until a reader of this language has reviewed it."*
3. **Glyph Rendering**:
   - Gujarati and Hindi rendering depends entirely on system fonts and font fallbacks (`Noto Sans Gujarati`, `Noto Sans Devanagari`). Text glyph rendering was **not visually verified by the automated agent**.
4. **Accessibility Audit Status**:
   - While high-contrast palettes, text legends, and accessible data tables beneath charts are implemented, **no formal WCAG 2.1 AA accessibility audit** has been conducted.
5. **PDF File Export**:
   - Screen S8 provides a print-friendly CSS stylesheet for browser printing (`Ctrl+P` / `Cmd+P`); a standalone binary PDF file generator is not built in this phase.
