"""Screen S5: What-If Sensitivity Simulator.

Decision-support tool projecting risk score changes under hypothetical farm interventions.
Guarantees:
- Output is explicitly marked as an 'estimate'.
- Explains effect_basis in plain words and surfaces assumption text when present.
- Displays score delta with 0 explicitly rendered as 'no change'.
- Displays old and new loan limit ranges.
- Renders causation disclaimer and reliability note verbatim.
- Original assessment is immutable and never overwritten.
- Supportive framing: an illustration for discussion, not causal proof.
"""

from __future__ import annotations

import streamlit as st

from satbhoomi.ui.api_client import ApiClient, ApiError, SessionExpiredError
from satbhoomi.ui.components import inject_custom_styles, render_prototype_banner
from satbhoomi.ui.state import clear_session, get_token


def render_what_if_screen(api_client: ApiClient | None = None) -> None:
    """Render Screen S5: What-If Simulator."""
    inject_custom_styles()
    render_prototype_banner()
    client = api_client or ApiClient()

    st.title("🌾 What-If Sensitivity Simulator")
    st.caption(
        "Simulate the projected credit score and limit impact of controllable farm interventions. "
        "This simulation is an **illustration for discussion, not evidence that the action "
        "causes the change**."
    )

    token = get_token()
    if not token:
        st.warning("Please sign in to access the What-If Simulator.")
        return

    # Check for active assessment in session
    latest_asm = st.session_state.get("latest_assessment_result")
    default_asm_id = int(latest_asm.get("id", 1)) if latest_asm else 1

    c_top1, c_top2 = st.columns([1, 2])
    with c_top1:
        assessment_id = st.number_input(
            "Assessment Reference ID *",
            min_value=1,
            value=default_asm_id,
            step=1,
            help="Reference ID of the existing pre-disbursal assessment to simulate against.",
            key="what_if_asm_id",
        )
    with c_top2:
        if latest_asm and latest_asm.get("id") == assessment_id:
            p_code = latest_asm.get("plot_code", "PLOT")
            p_season = latest_asm.get("season", "2024-25")
            p_score = latest_asm.get("score", "N/A")
            p_band = str(latest_asm.get("band", "")).upper()
            st.info(
                f"Active Assessment: **{p_code}** "
                f"(Season {p_season}, Baseline Score: **{p_score}**, Band: **{p_band}**)"
            )
        else:
            st.caption(
                "Enter an assessment ID. The baseline evaluation remains strictly immutable."
            )

    st.subheader("Select Hypothetical Intervention")
    c_in1, c_in2 = st.columns(2)
    with c_in1:
        intervention_choice = st.selectbox(
            "Controllable Farm Attribute *",
            options=["insured", "irrigation"],
            format_func=lambda x: {
                "insured": "Crop Insurance Enrollment (PMFBY)",
                "irrigation": "Irrigation Infrastructure Source",
            }.get(x, x),
            key="what_if_attribute_select",
        )

    with c_in2:
        if intervention_choice == "insured":
            new_val = st.selectbox(
                "Hypothetical Insurance Status *",
                options=["1", "0"],
                format_func=lambda x: (
                    "Enrolled in Crop Insurance (1)" if x == "1" else "Not Insured (0)"
                ),
                key="what_if_val_insured",
            )
        else:
            new_val = st.selectbox(
                "Hypothetical Irrigation Source *",
                options=["tube_well", "canal", "rainfed"],
                format_func=lambda x: {
                    "tube_well": "Tubewell / Borewell (Groundwater)",
                    "canal": "Canal Irrigation",
                    "rainfed": "Rainfed (No Assured Irrigation)",
                }.get(x, x),
                key="what_if_val_irrigation",
            )

    run_sim = st.button("Run What-If Simulation", type="primary", key="run_what_if_btn")

    if run_sim:
        with st.spinner("Evaluating sensitivity projection..."):
            try:
                result = client.run_what_if(
                    assessment_id=int(assessment_id),
                    changed_input=intervention_choice,
                    new_value=str(new_val),
                    token=token,
                )
                st.session_state["latest_what_if_result"] = result
            except SessionExpiredError:
                clear_session("Your session has ended. Please sign in again.")
                st.rerun()
                return
            except ApiError as err:
                st.error(f"Simulation failed ({err.code}): {err.message}")
                return

    sim_res = st.session_state.get("latest_what_if_result")
    if not sim_res:
        st.info(
            "Select an intervention attribute and hypothetical value above, "
            "then click 'Run What-If Simulation'."
        )
        return

    st.divider()
    res_code = sim_res.get("plot_code", "PLOT")
    res_season = sim_res.get("season", "2024-25")
    st.subheader(f"Projection Results: {res_code} ({res_season})")

    # Score and Band Comparison
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        old_sc = sim_res.get("old_score", "N/A")
        old_b = str(sim_res.get("old_band", "")).upper()
        st.metric("Baseline Score", f"{old_sc} ({old_b})")
        st.caption(f"Baseline Risk Band: **{old_b}**")

    with col_s2:
        new_sc = sim_res.get("new_score", "N/A")
        new_b = str(sim_res.get("new_band", "")).upper()
        st.metric("Projected Score", f"{new_sc} ({new_b})")
        st.caption(f"Projected Risk Band: **{new_b}**")

    with col_s3:
        delta = sim_res.get("score_delta", 0)
        if delta == 0:
            delta_str = "no change"
        elif delta > 0:
            delta_str = f"+{delta} points (higher risk)"
        else:
            delta_str = f"{delta} points (lower risk)"
        st.metric("Projected Score Delta", delta_str)
        st.caption("Model sensitivity delta")

    # Limit Band Comparison
    st.subheader("Indicative Credit Limit Impact")
    old_lim = sim_res.get("old_limit_band")
    new_lim = sim_res.get("new_limit_band")
    c_lim1, c_lim2 = st.columns(2)
    with c_lim1:
        if old_lim and isinstance(old_lim, dict):
            min_o = old_lim.get("limit_min_inr", 0)
            max_o = old_lim.get("limit_max_inr", 0)
            rec_o = old_lim.get("limit_recommended_inr", 0)
            st.markdown(f"**Baseline Limit Range:** ₹{min_o:,.0f} – ₹{max_o:,.0f}")
            st.markdown(f"**Baseline Recommended Cap:** ₹{rec_o:,.0f}")
        else:
            st.markdown("*Baseline loan limit not evaluated.*")

    with c_lim2:
        if new_lim and isinstance(new_lim, dict):
            min_n = new_lim.get("limit_min_inr", 0)
            max_n = new_lim.get("limit_max_inr", 0)
            rec_n = new_lim.get("limit_recommended_inr", 0)
            st.markdown(f"**Projected Limit Range:** ₹{min_n:,.0f} – ₹{max_n:,.0f}")
            st.markdown(f"**Projected Recommended Cap:** ₹{rec_n:,.0f}")
        else:
            st.markdown("*Projected loan limit not evaluated.*")

    # Mandatory Rule 6 Disclosures
    st.subheader("Model Basis & Assumptions")
    basis_map = {
        "scorer_input": "Scorer Input (Direct feature variation applied to model rules)",
        "scenario_assumption": "Scenario Assumption (Structural agronomic simulation heuristic)",
        "not_modelled": "Not Modelled (Input has zero direct effect on model rules)",
    }
    raw_basis = sim_res.get("effect_basis", "scorer_input")
    plain_basis = basis_map.get(raw_basis, raw_basis)

    st.markdown(f"**Evaluation Basis:** {plain_basis}")
    st.markdown(f"**Estimate Classification:** `{sim_res.get('estimate_label', 'estimate')}`")

    assumption_text = sim_res.get("assumption")
    if assumption_text:
        st.info(f"**Scenario Assumption:** {assumption_text}")

    rationale_text = sim_res.get("rationale")
    if rationale_text:
        st.markdown(f"**Economic & Agronomic Rationale:** {rationale_text}")

    # Disclaimers verbatim from API
    st.markdown(
        f"""
        <div class="info-card">
            <strong>Mandatory Sensitivity Disclaimer:</strong> {sim_res.get("disclaimer", "")}
            <br><br>
            <strong>Reliability Note:</strong> {sim_res.get("reliability_note", "")}
        </div>
        """,
        unsafe_allow_html=True,
    )
