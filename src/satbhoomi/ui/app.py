"""Streamlit user interface entry point for SatBhoomi Score + Raksha (Screens S1 to S9)."""

from __future__ import annotations

import streamlit as st

from satbhoomi.ui.components import inject_custom_styles
from satbhoomi.ui.screens.add_plot import render_add_plot_screen
from satbhoomi.ui.screens.alert_detail import render_alert_detail_screen
from satbhoomi.ui.screens.assessment import render_assessment_screen
from satbhoomi.ui.screens.dashboard import render_dashboard_screen
from satbhoomi.ui.screens.farmer_summary import render_farmer_summary_screen
from satbhoomi.ui.screens.login import render_login_screen
from satbhoomi.ui.screens.monitoring import render_monitoring_screen
from satbhoomi.ui.screens.relief_report import render_relief_report_screen
from satbhoomi.ui.screens.what_if import render_what_if_screen
from satbhoomi.ui.state import (
    clear_session,
    get_current_user,
    init_session_state,
    is_authenticated,
)

st.set_page_config(
    page_title="SatBhoomi Score + Raksha",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize ephemeral session state
init_session_state()
inject_custom_styles()


def page_login() -> None:
    render_login_screen()


def page_dashboard() -> None:
    render_dashboard_screen()


def page_add_plot() -> None:
    render_add_plot_screen()


def page_assessment() -> None:
    render_assessment_screen()


def page_what_if() -> None:
    render_what_if_screen()


def page_monitoring() -> None:
    render_monitoring_screen()


def page_alert_detail() -> None:
    render_alert_detail_screen()


def page_relief_report() -> None:
    render_relief_report_screen()


def page_farmer_summary() -> None:
    render_farmer_summary_screen()


# Define pages using modern st.Page API
login_p = st.Page(page_login, title="Officer Login", icon="🔐")
dashboard_p = st.Page(page_dashboard, title="Plot Portfolio", icon="📊")
add_plot_p = st.Page(page_add_plot, title="Register Plot", icon="➕")
assessment_p = st.Page(page_assessment, title="Risk Assessment", icon="🌾")
what_if_p = st.Page(page_what_if, title="What-If Simulator", icon="🔄")
monitoring_p = st.Page(page_monitoring, title="In-Season Monitoring", icon="🛡️")
alert_detail_p = st.Page(page_alert_detail, title="Alert Action Playbook", icon="📋")
relief_report_p = st.Page(page_relief_report, title="Relief Evidence", icon="📜")
farmer_summary_p = st.Page(page_farmer_summary, title="Farmer Summary", icon="🗣️")

authenticated_pages = [
    dashboard_p,
    add_plot_p,
    assessment_p,
    what_if_p,
    monitoring_p,
    alert_detail_p,
    relief_report_p,
    farmer_summary_p,
]

if not is_authenticated():
    pg = st.navigation([login_p])
else:
    # Sidebar user profile badge and logout
    user = get_current_user() or {}
    username = user.get("username", "Officer")
    with st.sidebar:
        st.markdown(f"**Logged in as:** `{username}`")
        if st.button("Sign Out", key="sidebar_logout_btn", use_container_width=True):
            clear_session()
            st.rerun()
        st.divider()

    # Route programmatic transitions via session_state["active_screen"]
    active_target = st.session_state.pop("active_screen", None)
    screen_map = {
        "add_plot": add_plot_p,
        "assessment": assessment_p,
        "what_if": what_if_p,
        "monitoring": monitoring_p,
        "alert_detail": alert_detail_p,
        "relief_report": relief_report_p,
        "farmer_summary": farmer_summary_p,
    }

    if active_target in screen_map:
        pg = st.navigation(authenticated_pages, position="sidebar")
        screen_map[active_target].run()
        st.stop()
    else:
        pg = st.navigation(authenticated_pages, position="sidebar")

pg.run()
