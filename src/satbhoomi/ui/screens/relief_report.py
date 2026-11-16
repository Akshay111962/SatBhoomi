"""Screen S8: RBI 33% Calamity Relief Screening Evidence Report.

Displays:
- Baseline vs. in-season NDVI vegetative comparison.
- Percentage drop and categorical loss band relative to RBI 33% calamity threshold.
- Handles 'insufficient data' gracefully without displaying misleading percentages.
- Mandatory statutory disclaimer and screening indicator notice.
- Clean printable view for browser print (PDF file export not built in this task).
"""

from __future__ import annotations

import streamlit as st

from satbhoomi.ui.api_client import ApiClient, ApiError, SessionExpiredError
from satbhoomi.ui.components import inject_custom_styles, render_prototype_banner
from satbhoomi.ui.state import clear_session, get_token

RELIEF_SCREENING_NOTICE = (
    "This is an NDVI-based screening indicator, not a crop loss assessment, "
    "and that the official assessment and any calamity declaration rest with the authorities."
)


def render_relief_report_screen(api_client: ApiClient | None = None) -> None:
    """Render Screen S8: Relief Evidence Report."""
    inject_custom_styles()
    render_prototype_banner()
    client = api_client or ApiClient()

    st.title("📋 Relief Evidence Report (RBI 33% Calamity Framework)")
    st.caption(
        "Objective satellite vegetative decline screening to facilitate timely "
        "debt restructuring review."
    )

    token = get_token()
    if not token:
        st.warning("Please sign in to access the Relief Evidence Report.")
        return

    # Fetch plot choices
    try:
        plot_resp = client.list_plots(token=token, limit=100)
        plots = plot_resp.get("items", [])
    except SessionExpiredError:
        clear_session("Your session has ended. Please sign in again.")
        st.rerun()
        return
    except ApiError as err:
        st.error(f"Unable to load plots list: {err.message}")
        return

    if not plots:
        st.warning("No plots available. Please register or import sample plots first.")
        return

    saved_plot_id = st.session_state.get("relief_plot_id")
    plot_options: dict[int, str] = {}
    for p in plots:
        pid = int(p["id"])
        code = p.get("plot_code") or f"PLOT-{pid:03d}"
        vlg = p.get("village", "Village")
        plot_options[pid] = f"{code} ({vlg})"
    default_idx = (
        list(plot_options.keys()).index(saved_plot_id) if saved_plot_id in plot_options else 0
    )

    c1, c2 = st.columns([2, 1])
    with c1:
        selected_plot_id = st.selectbox(
            "Select Plot Parcel *",
            options=list(plot_options.keys()),
            index=default_idx,
            format_func=lambda pid: plot_options.get(pid, f"Plot {pid}"),
            key="relief_plot_select",
        )
    with c2:
        st.write("")
        st.write("")
        generate_btn = st.button("Generate Relief Evidence", type="primary", key="btn_gen_relief")

    if generate_btn or "current_relief_report" not in st.session_state:
        with st.spinner("Generating satellite crop loss screening evidence..."):
            try:
                rep_data = client.get_relief_report(plot_id=int(selected_plot_id), token=token)
                st.session_state["current_relief_report"] = rep_data
            except SessionExpiredError:
                clear_session("Your session has ended. Please sign in again.")
                st.rerun()
                return
            except ApiError as err:
                if err.status_code == 501:
                    # In real DB mode before T-12, the endpoint returns 501
                    st.info(
                        "Relief evidence generator is active in mock mode "
                        "(501 in real database mode)."
                    )
                    st.session_state["current_relief_report"] = {
                        "status": "insufficient_data",
                        "plot_code": f"PLOT-{selected_plot_id:03d}",
                        "season": "2024-25",
                        "disclaimer": (
                            "Official crop loss assessment and calamity declaration remain strictly"
                            " with government and bank relief committees. This evidence report is "
                            "for decision support only."
                        ),
                    }
                else:
                    st.error(f"Unable to generate relief report ({err.code}): {err.message}")
                    return

    report = st.session_state.get("current_relief_report")
    if not report:
        st.info("Select a plot parcel above and click 'Generate Relief Evidence'.")
        return

    # Printable container
    st.divider()
    st.markdown('<div class="printable-section">', unsafe_allow_html=True)

    plot_code = report.get("plot_code", "PLOT")
    season = report.get("season", "2024-25")
    st.subheader(f"Evidence Report: {plot_code} (Season {season})")

    # Mandatory Screening Indicator Statement
    st.info(f"**Screening Notice:** {RELIEF_SCREENING_NOTICE}")

    is_insufficient = report.get("status") == "insufficient_data" or "ndvi_drop_pct" not in report

    if is_insufficient:
        st.warning(
            "**Insufficient data to generate crop calamity screening.**\n\n"
            "Historical satellite baseline required to compute vegetative departure is not "
            "available for this plot-season."
        )
        st.caption(
            "No loss percentage or RBI calamity threshold calculation is displayed "
            "for insufficient data cases."
        )
    else:
        base_ndvi = report.get("baseline_ndvi_mean", 0.0)
        curr_ndvi = report.get("current_ndvi_mean", 0.0)
        drop_pct = report.get("ndvi_drop_pct", 0.0)
        loss_band = report.get("estimated_loss_band", "normal")
        exceeds_rbi = report.get("exceeds_rbi_33_threshold", False)

        c_metric1, c_metric2, c_metric3 = st.columns(3)
        with c_metric1:
            st.metric("Historical Benchmark NDVI", f"{base_ndvi:.3f}")
            st.caption("Multi-season median in calendar window")
        with c_metric2:
            st.metric("Recorded Season NDVI", f"{curr_ndvi:.3f}")
            st.caption("In-season clear-sky vegetative vigor")
        with c_metric3:
            st.metric("Vegetative Drop Departure", f"{drop_pct:.1f}%")
            st.caption("Percentage drop below historical baseline")

        # RBI Calamity Threshold Callout
        st.subheader("RBI Calamity Restructuring Threshold Status")
        if exceeds_rbi:
            st.markdown(
                f"""
                <div style="background-color: #FEF2F2; border-left: 6px solid #EF4444;
                            padding: 14px 18px; border-radius: 4px; margin-bottom: 14px;">
                    <strong style="color: #991B1B; font-size: 1.1rem;">
                        ⚠️ EXCEEDS RBI 33% CALAMITY THRESHOLD
                    </strong>
                    <p style="color: #7F1D1D; margin: 6px 0 0 0;">
                        Estimated crop loss band: <strong>{loss_band}</strong>.
                        Satellite vegetative decline meets objective screening criteria for
                        rescheduling review under RBI calamity restructuring guidelines.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style="background-color: #ECFDF5; border-left: 6px solid #10B981;
                            padding: 14px 18px; border-radius: 4px; margin-bottom: 14px;">
                    <strong style="color: #065F46; font-size: 1.1rem;">
                        ✅ BELOW RBI 33% CALAMITY THRESHOLD
                    </strong>
                    <p style="color: #047857; margin: 6px 0 0 0;">
                        Estimated crop loss band: <strong>{loss_band}</strong>.
                        Observed vegetative vigor shows normal crop progression.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        summary_text = report.get("supporting_evidence_summary")
        if summary_text:
            st.markdown(f"**Supporting Evidence:** {summary_text}")

    # Mandatory Statutory Disclaimer
    disclaimer_text = report.get(
        "disclaimer",
        "Official crop loss assessment and calamity declaration remain strictly with "
        "government and bank relief committees. This evidence report is for decision support only.",
    )
    st.markdown(
        f"""
        <div class="info-card">
            <strong>Statutory Disclaimer:</strong> {disclaimer_text}
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # Print action hint
    st.caption(
        "💡 **Print Friendly View:** Use your browser's Print command (`Ctrl+P` or `Cmd+P`) "
        "to print or save this evidence report. Navigation elements and buttons are "
        "automatically excluded from printed output."
    )
