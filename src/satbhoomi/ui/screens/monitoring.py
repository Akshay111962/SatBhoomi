"""Screen S6: In-Season Plot Monitoring and Replay Alerts.

Displays:
- Mandatory historical replay disclaimer banner.
- Multi-checkpoint NDVI timeline line chart with accessible data table beneath.
- Distinguishes optical data gaps from agronomic stress alerts.
- In-season alerts list with paired text and color severity badges.
- Empty state: 'No alerts'.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from satbhoomi.ui.api_client import ApiClient, ApiError, SessionExpiredError
from satbhoomi.ui.components import (
    inject_custom_styles,
    render_prototype_banner,
    render_replay_banner,
    render_severity_badge,
)
from satbhoomi.ui.state import clear_session, get_token


def render_monitoring_screen(api_client: ApiClient | None = None) -> None:
    """Render Screen S6: Monitoring and Alerts."""
    inject_custom_styles()
    render_prototype_banner()
    render_replay_banner()
    client = api_client or ApiClient()

    st.title("🛡️ Raksha In-Season Monitoring & Replay")
    st.caption(
        "Historical season replay tracking vegetative vigor, rainfall accumulation, "
        "and supportive stress alerts."
    )

    token = get_token()
    if not token:
        st.warning("Please sign in to access plot monitoring.")
        return

    # Fetch available plots
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

    plot_options: dict[int, str] = {}
    for p in plots:
        pid = int(p["id"])
        code = p.get("plot_code") or f"PLOT-{pid:03d}"
        vlg = p.get("village", "Village")
        plot_options[pid] = f"{code} ({vlg})"

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        selected_plot_id = st.selectbox(
            "Select Plot Parcel *",
            options=list(plot_options.keys()),
            format_func=lambda pid: plot_options.get(pid, f"Plot {pid}"),
            key="monitor_plot_select",
        )
    with c2:
        selected_season = st.selectbox(
            "Cropping Season *",
            options=["2024-25", "2023-24", "2022-23", "2021-22", "2020-21"],
            index=0,
            key="monitor_season_select",
        )
    with c3:
        st.write("")
        st.write("")
        fetch_btn = st.button("Load Monitoring Data", type="primary", key="load_monitor_btn")

    if fetch_btn or "current_monitoring_data" not in st.session_state:
        with st.spinner("Loading monitoring timeline and alerts..."):
            try:
                mon_data = client.get_monitoring(
                    plot_id=int(selected_plot_id),
                    token=token,
                    season=selected_season,
                )
                st.session_state["current_monitoring_data"] = mon_data
            except SessionExpiredError:
                clear_session("Your session has ended. Please sign in again.")
                st.rerun()
                return
            except ApiError as err:
                st.error(f"Unable to fetch monitoring data ({err.code}): {err.message}")
                return

    mon_data = st.session_state.get("current_monitoring_data")
    if not mon_data:
        st.info("Select a plot parcel and season, then click 'Load Monitoring Data'.")
        return

    # Metadata & Status summary
    st.divider()
    c_stat1, c_stat2, c_stat3 = st.columns(3)
    with c_stat1:
        st.markdown(f"**Plot Code:** `{mon_data.get('plot_code', 'PLOT')}`")
        st.markdown(f"**Cropping Season:** `{mon_data.get('season', selected_season)}`")
    with c_stat2:
        st.markdown(f"**Checkpoint Label:** `{mon_data.get('checkpoint_label', 'In-Season')}`")
        st.markdown(f"**Evaluation Mode:** `{mon_data.get('mode', 'replay').upper()}`")
    with c_stat3:
        status_val = mon_data.get("status", "ok")
        if status_val == "data_gap":
            gap_reason = mon_data.get("data_gap_reason", "Cloud cover gap")
            st.warning(f"**Status:** Data Gap Recorded\n\n*{gap_reason}*")
        else:
            st.success("**Status:** Clear Observation Timeline")

    # Timeline Visualization
    st.subheader("Vegetation Vigor & Rainfall Timeline")
    timeline_items = mon_data.get("timeline", [])

    if timeline_items:
        # Prepare tabular data
        table_records: list[dict[str, str]] = []
        chart_records: list[dict[str, float | str | None]] = []

        for pt in timeline_items:
            obs_date = pt.get("date", "-")
            ndvi_val = pt.get("ndvi")
            rain_val = pt.get("rainfall_mm")
            is_gap = pt.get("data_gap", False)

            ndvi_display = f"{float(ndvi_val):.3f}" if ndvi_val is not None else "data gap"
            rain_display = f"{float(rain_val):.1f} mm" if rain_val is not None else "0.0 mm"
            flag_display = "DATA GAP (optical obstruction)" if is_gap else "Observation OK"

            table_records.append(
                {
                    "Date": obs_date,
                    "NDVI Vigor Value": ndvi_display,
                    "Rainfall": rain_display,
                    "Observation Quality": flag_display,
                }
            )

            # For chart plotting
            chart_records.append(
                {
                    "Date": obs_date,
                    "Observed NDVI": float(ndvi_val) if ndvi_val is not None else None,
                }
            )

        # Plot chart using Streamlit native line_chart
        df_chart = pd.DataFrame(chart_records).set_index("Date")
        st.line_chart(df_chart, height=280)
        st.caption(
            "Figure: Multi-checkpoint clear-sky NDVI trajectory. "
            "Missing points represent optical data gaps."
        )

        # Accessible Data Table beneath chart
        st.markdown("#### Tabular Observation Record (Accessible Data View)")
        st.dataframe(table_records, use_container_width=True, hide_index=True)
    else:
        st.info("No timeline observation checkpoints recorded for this plot-season.")

    # Alerts List
    st.subheader("In-Season Stress Alerts & Playbook Warnings")
    active_alerts = mon_data.get("active_alerts", [])
    past_alerts = mon_data.get("past_alerts", [])
    all_alerts = active_alerts + past_alerts

    if not all_alerts:
        st.info("No alerts recorded for this plot parcel in the selected season.")
    else:
        for idx, alert in enumerate(all_alerts, 1):
            sev_badge = render_severity_badge(alert.get("severity", "low"))
            headline = alert.get("headline", "Stress Notice")
            det = alert.get("detail", "")
            action = alert.get("supportive_action", "")
            gap_warn = alert.get("data_gap_warning")
            alert_id = alert.get("id")
            status_text = alert.get("status", "open").upper()

            with st.container():
                st.markdown(
                    f"""
                    <div class="info-card">
                        <div style="display: flex; justify-content: space-between;
                                    align-items: center; margin-bottom: 8px;">
                            <span style="font-size: 1.1rem; font-weight: 700; color: #0A192F;">
                                {idx}. {headline}
                            </span>
                            <span>
                                {sev_badge}
                                <span style="font-weight: 600; color: #475569;
                                             font-size: 0.85rem; margin-left: 8px;">
                                    STATUS: {status_text}
                                </span>
                            </span>
                        </div>
                        <p style="color: #334155; margin-bottom: 8px;">
                            <strong>Detail:</strong> {det}
                        </p>
                        <p style="color: #1E5631; margin-bottom: 8px;">
                            <strong>Supportive Action Guidance:</strong> {action}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if gap_warn:
                    st.caption(f"ℹ️ Notice: {gap_warn}")

                c_act1, c_act2 = st.columns([1, 3])
                with c_act1:
                    if alert_id and st.button(
                        f"Action Playbook #{alert_id}",
                        key=f"btn_action_alert_{alert_id}_{idx}",
                    ):
                        st.session_state["selected_alert_obj"] = alert
                        st.session_state["active_screen"] = "alert_detail"
                        st.rerun()

    # Link to Relief Report
    st.divider()
    c_link1, c_link2 = st.columns([1, 2])
    with c_link1:
        if st.button("Inspect Relief Screening Evidence (S8)", key="nav_to_relief_btn"):
            st.session_state["relief_plot_id"] = selected_plot_id
            st.session_state["active_screen"] = "relief_report"
            st.rerun()
    with c_link2:
        st.caption(
            "Screen S8 compares vegetative vigor against multi-season baseline "
            "under the RBI 33% calamity relief criteria."
        )
