"""Screen S7: Alert Detail & Supportive Action Playbook.

Displays:
- Officer-facing stress alert details and status.
- Fixed supportive action playbook (strictly no recovery pressure, no automated contact).
- Officer note entry (<= 500 characters, PII warning).
- Enforces status transitions and renders API errors on illegal transitions.
- Mandatory distressed farmer support notice: involve senior colleague and local support.
"""

from __future__ import annotations

import streamlit as st

from satbhoomi.ui.api_client import ApiClient, ApiError, SessionExpiredError
from satbhoomi.ui.components import (
    inject_custom_styles,
    render_prototype_banner,
    render_severity_badge,
)
from satbhoomi.ui.state import clear_session, get_token

# Fixed supportive actions from the canon playbook
SUPPORTIVE_ACTIONS_MAP = {
    "field_visit": "Supportive Field Visit (Inspect water and crop vigor)",
    "insurance_claim_help": "Insurance Claim Help (PMFBY claim submission guidance)",
    "extension_support": "Extension Support (Connect with agronomic advisor)",
    "repayment_timing_discussion": "Repayment Timing Discussion (Linked to post-harvest sale)",
    "rescheduling_request": "Rescheduling Request (Where RBI calamity rules allow)",
    "senior_or_local_support": "Involve Senior Colleague or Local Support",
}

DISTRESSED_FARMER_NOTICE = (
    "If a farmer is visibly distressed, involve a senior colleague and local support "
    "and do not handle it alone."
)


def render_alert_detail_screen(api_client: ApiClient | None = None) -> None:
    """Render Screen S7: Alert Playbook and Officer Action Logging."""
    inject_custom_styles()
    render_prototype_banner()
    client = api_client or ApiClient()

    st.title("🛡️ Alert Detail & Supportive Playbook")
    st.caption("Coordinate supportive bank interventions for active in-season stress alerts.")

    token = get_token()
    if not token:
        st.warning("Please sign in to access the Alert Action Playbook.")
        return

    # Retrieve selected alert from session state or allow entering ID
    selected_alert = st.session_state.get("selected_alert_obj")
    alert_id_default = (
        int(selected_alert.get("id", 1)) if selected_alert and selected_alert.get("id") else 1
    )

    c_top1, c_top2 = st.columns([1, 2])
    with c_top1:
        target_alert_id = st.number_input(
            "Alert Identifier *",
            min_value=1,
            value=alert_id_default,
            step=1,
            help="Reference ID of the in-season alert to document.",
            key="input_alert_id",
        )
    with c_top2:
        if selected_alert and selected_alert.get("id") == target_alert_id:
            st.info(
                f"Active Alert: **{selected_alert.get('plot_code', 'PLOT')}** | "
                f"Season: **{selected_alert.get('season', '2024-25')}** | "
                f"Status: **{str(selected_alert.get('status', 'open')).upper()}**"
            )
        else:
            st.caption("Enter the target alert ID to review playbook actions.")

    # Show alert overview
    st.subheader("Alert Information")
    if selected_alert and selected_alert.get("id") == target_alert_id:
        headline = selected_alert.get("headline", "Stress Notice")
        detail = selected_alert.get("detail", "Agronomic stress condition detected.")
        sev = selected_alert.get("severity", "medium")
        current_status = selected_alert.get("status", "open").lower()
        checkpoint = selected_alert.get("checkpoint_label", "In-Season Checkpoint")
        detected_on = selected_alert.get("detected_on", "2025-01-15")
    else:
        headline = "Vegetative drag detected against baseline"
        detail = "Plot recorded vegetative drag indicating support needed."
        sev = "medium"
        current_status = "open"
        checkpoint = "January 15"
        detected_on = "2025-01-15"

    sev_badge = render_severity_badge(sev)
    st.markdown(
        f"""
        <div class="info-card">
            <div style="display: flex; justify-content: space-between;
                        align-items: center; margin-bottom: 8px;">
                <span style="font-size: 1.15rem; font-weight: 700; color: #0A192F;">
                    {headline}
                </span>
                <span>{sev_badge}</span>
            </div>
            <p><strong>Evaluation Checkpoint:</strong> {checkpoint} (Observed {detected_on})</p>
            <p><strong>Current Status:</strong> <code>{current_status.upper()}</code></p>
            <p style="color: #334155;"><strong>Detail:</strong> {detail}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Mandatory Ethical Guidance Box
    st.warning(f"🤝 **Officer Guidance:** {DISTRESSED_FARMER_NOTICE}")

    # Action Logging Form
    st.subheader("Record Supportive Officer Intervention")
    st.caption(
        "Interventions are strictly supportive. "
        "There are no debt recovery pressure actions and no automatic contact to the farmer."
    )

    with st.form("alert_action_form", clear_on_submit=False):
        action_choice = st.selectbox(
            "Supportive Action Category *",
            options=list(SUPPORTIVE_ACTIONS_MAP.keys()),
            format_func=lambda k: SUPPORTIVE_ACTIONS_MAP.get(k, k),
            key="select_action_type",
        )

        officer_note = st.text_area(
            "Officer Verification Note (5 to 500 characters) *",
            placeholder="e.g. Conducted supportive field visit; verified pump repair status.",
            help=(
                "Document factual support provided. "
                "Do not enter phone numbers, national IDs, or bank accounts."
            ),
            key="input_officer_note",
            max_chars=500,
        )

        st.caption("Hint: Do not enter phone numbers, national IDs, or bank account numbers.")
        submit_action = st.form_submit_button("Record Supportive Action")

    if submit_action:
        if not officer_note.strip() or len(officer_note.strip()) < 5:
            st.error("Please provide a meaningful verification note (at least 5 characters).")
            return

        with st.spinner("Submitting audited action log to backend..."):
            try:
                res = client.record_alert_action(
                    alert_id=int(target_alert_id),
                    action_type=action_choice,
                    note=officer_note.strip(),
                    token=token,
                )
                st.success(
                    f"Action recorded successfully (ID #{res.get('action_id', 1)}). "
                    f"Status transition: {res.get('status_before', 'open')} → "
                    f"{res.get('status_after', 'in_progress')}."
                )
                if selected_alert and selected_alert.get("id") == target_alert_id:
                    selected_alert["status"] = res.get("status_after", "in_progress")
                    st.session_state["selected_alert_obj"] = selected_alert
            except SessionExpiredError:
                clear_session("Your session has ended. Please sign in again.")
                st.rerun()
                return
            except ApiError as err:
                # Surface specific validation or disallowed transition errors from the API
                if err.field:
                    st.error(f"Validation Error on field '{err.field}': {err.message}")
                elif err.code == "DISALLOWED_STATUS_TRANSITION":
                    st.error(
                        f"Illegal status transition ({err.code}): {err.message}. "
                        "Resolved or dismissed alerts cannot be transitioned."
                    )
                else:
                    st.error(f"Action recording failed ({err.code}): {err.message}")
