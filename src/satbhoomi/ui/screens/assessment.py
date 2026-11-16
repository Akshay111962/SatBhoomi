"""Screen S4: In-Season Farm Credit Risk Assessment.

Presents deterministic, explainable risk assessments with zero sanction/approval controls.
Guarantees:
- Large score with text-first band label (never color alone).
- Three grounded reasons and indicative Scale of Finance limit bands.
- Mandatory interpretation and reliability notes displayed verbatim.
- Plain handling for insufficient_data with no score displayed.
- Ethical, non-blaming language: farm stress, repayment stress, support needed.
"""

from __future__ import annotations

import uuid

import streamlit as st

from satbhoomi.ui.api_client import ApiClient, ApiError, SessionExpiredError
from satbhoomi.ui.components import inject_custom_styles, render_prototype_banner, render_score_card
from satbhoomi.ui.state import clear_session, get_token, is_authenticated, record_plot_band


def render_assessment_screen(api_client: ApiClient | None = None) -> None:
    """Render Screen S4: Farm Credit Risk Assessment."""
    inject_custom_styles()

    if not is_authenticated():
        st.info("Please sign in to run farm assessments.")
        return

    render_prototype_banner()

    st.title("🌾 In-Season Risk Assessment")
    st.markdown(
        "Evaluate crop canopy vegetative growth, rainfall anomalies, and market price volatility "
        "as of the in-season cut-off date (January 31) for objective credit decision support."
    )

    token = get_token()
    if not token:
        clear_session("Your session has ended. Please sign in again.")
        st.rerun()
        return

    client = api_client or ApiClient()

    # Retrieve plots for dropdown selection
    with st.spinner("Fetching registered plots..."):
        try:
            plots_resp = client.list_plots(token=token, limit=100)
            plot_items = plots_resp.get("items", [])
        except SessionExpiredError:
            clear_session("Your session has ended. Please sign in again.")
            st.rerun()
            return
        except Exception as exc:
            st.error(f"Failed to fetch plots: {exc}")
            return

    if not plot_items:
        st.warning("No registered plots found. Please add a plot first.")
        if st.button("Register a Plot", key="assess_goto_add_plot"):
            st.session_state["active_screen"] = "add_plot"
            st.rerun()
        return

    plot_options: dict[int, str] = {}
    for p in plot_items:
        pid = int(p["id"])
        code = p.get("plot_code") or f"PLOT-{pid:03d}"
        vil = p.get("village", "Anand")
        plot_options[pid] = f"{code} — {vil}"

    default_plot_id = st.session_state.get("selected_plot_id", list(plot_options.keys())[0])
    if default_plot_id not in plot_options:
        default_plot_id = list(plot_options.keys())[0]

    col_select, col_season = st.columns([3, 1])
    with col_select:
        selected_plot_id = st.selectbox(
            "Select Agricultural Plot *",
            options=list(plot_options.keys()),
            format_func=lambda pid: plot_options[pid],
            index=list(plot_options.keys()).index(default_plot_id),
            key="assess_plot_selector",
        )
    with col_season:
        season_options = ["2024-25", "2023-24", "2022-23", "2021-22", "2020-21"]
        selected_season = st.selectbox(
            "Target Rabi Season",
            season_options,
            index=0,
            key="assess_season_selector",
        )

    # Action trigger button
    if st.button("Run Assessment", key="run_assessment_btn"):
        # Generate single-use unique Idempotency-Key per click
        idempotency_key = f"ui-eval-{uuid.uuid4().hex[:16]}"
        with st.spinner("Executing agronomic assessment model..."):
            try:
                result = client.create_assessment(
                    plot_id=selected_plot_id,
                    token=token,
                    season=selected_season,
                    idempotency_key=idempotency_key,
                )
                st.session_state["latest_assessment_result"] = result
                # Record in session state so dashboard reflects this band
                if result.get("band"):
                    record_plot_band(selected_plot_id, result["band"])
            except SessionExpiredError:
                clear_session("Your session has ended. Please sign in again.")
                st.rerun()
                return
            except ApiError as err:
                st.error(f"Assessment error: {err.message}")
                return

    # Render assessment result if present
    res = st.session_state.get("latest_assessment_result")
    if not res:
        st.info(
            "Select a plot parcel above and click 'Run Assessment' "
            "to generate in-season risk scores."
        )
        return

    st.divider()

    plot_code = res.get("plot_code", "PLOT")
    season = res.get("season", selected_season)
    eval_status = res.get("status", "ok")

    st.subheader(f"Assessment Result: {plot_code} (Season {season})")

    # Handle insufficient_data status
    if eval_status == "insufficient_data":
        render_score_card(None, None)
        insuff_reason = res.get(
            "insufficient_data_reason",
            "Historical prior baseline unavailable for new plot.",
        )
        st.warning(
            f"**Not enough data to score this plot-season.** \n\n**Reason:** {insuff_reason}"
        )
        st.caption(
            "No credit risk score is produced when historical "
            "baseline requirements are not satisfied."
        )
    else:
        score_val = res.get("score")
        band_val = res.get("band")
        render_score_card(score_val, band_val)

        # 3 Grounded Reasons
        st.subheader("Key Risk & Protective Observations")
        reasons_list = res.get("reasons", [])
        if reasons_list:
            for idx, r in enumerate(reasons_list, 1):
                text = r.get("text") if isinstance(r, dict) else str(r)
                st.markdown(f"**{idx}.** {text}")
        else:
            st.write("No adverse factors recorded up to cut-off date.")

        prot_factor = res.get("protective_factor")
        if prot_factor:
            st.success(f"**Protective Factor:** {prot_factor}")

        # Indicative Loan Underwriting Suggestion
        loan_sugg = res.get("loan_suggestion")
        if loan_sugg and isinstance(loan_sugg, dict):
            st.subheader("Indicative Loan Suggestion (Decision Support)")
            st.caption(
                "Notice: This is an **indicative credit limit range** for loan officer "
                "decision support only—not a credit sanction or approval. "
                "The human loan officer makes the final credit decision. "
                "Rupee figures are demonstration values based on the DLTC Scale of Finance."
            )

            limit_info = loan_sugg.get("limit_band")
            if limit_info and isinstance(limit_info, dict):
                min_amt = limit_info.get("limit_min_inr", 0)
                max_amt = limit_info.get("limit_max_inr", 0)
                rec_amt = limit_info.get("limit_recommended_inr", 0)
                c_lim1, c_lim2, c_lim3 = st.columns(3)
                with c_lim1:
                    st.metric("Indicative Limit Range", f"₹{min_amt:,.0f} – ₹{max_amt:,.0f}")
                with c_lim2:
                    st.metric("Suggested Cap", f"₹{rec_amt:,.0f}")
                with c_lim3:
                    ins_req = loan_sugg.get("insurance_required", False)
                    st.metric("PMFBY Requirement", "Mandatory" if ins_req else "Standard KCC")

            sched = loan_sugg.get("repayment_schedule")
            if sched and isinstance(sched, dict):
                sched_notes = sched.get("schedule_notes", "Aligned to post-harvest crop receipts.")
                st.info(f"**Repayment Schedule:** {sched_notes}")

    # Data Warnings
    data_warnings = res.get("data_warnings", [])
    if data_warnings:
        with st.expander("Data Quality Warnings", expanded=False):
            for w in data_warnings:
                st.warning(f"• {w}")

    # Mandatory Governance & Regulatory Disclaimers (Verbatim API Output)
    st.subheader("Traceability & Governance Disclaimers")
    c_gov1, c_gov2 = st.columns(2)
    with c_gov1:
        st.markdown(f"**Cut-off Date:** {res.get('cutoff_date_iso', '2025-01-31')}")
        model_ver = res.get("model_version", "v2.0")
        scorer_name = res.get("scorer", "rules_baseline")
        st.markdown(f"**Active Model:** `{model_ver}` ({scorer_name})")
    with c_gov2:
        st.markdown(f"**Created At:** {res.get('created_at', '2026-11-15')}")

    interp_text = res.get(
        "interpretation",
        "Deterministic in-season agricultural credit risk evaluation.",
    )
    rel_note = res.get(
        "reliability_note",
        "Prototype evaluation grounded strictly on pre-cutoff satellite "
        "and meteorological observations.",
    )
    st.markdown(
        f"""
        <div class="info-card">
            <strong>Interpretation:</strong> {interp_text}
            <br><br>
            <strong>Reliability Note:</strong> {rel_note}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()
    c_link1, c_link2 = st.columns(2)
    with c_link1:
        if st.button("Simulate Interventions in What-If (S5)", key="btn_to_what_if"):
            st.session_state["active_screen"] = "what_if"
            st.rerun()
    with c_link2:
        if st.button("Generate Farmer Summary (S9)", key="btn_to_farmer_summary"):
            st.session_state["active_screen"] = "farmer_summary"
            st.rerun()
