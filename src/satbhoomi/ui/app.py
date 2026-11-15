"""Streamlit user interface entry point for SatBhoomi Score + Raksha (Screens S1 to S4)."""

from __future__ import annotations

import streamlit as st

from satbhoomi.ui.components import inject_custom_styles
from satbhoomi.ui.screens.add_plot import render_add_plot_screen
from satbhoomi.ui.screens.assessment import render_assessment_screen
from satbhoomi.ui.screens.dashboard import render_dashboard_screen
from satbhoomi.ui.screens.login import render_login_screen
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


# Define pages using modern st.Page API
login_p = st.Page(page_login, title="Officer Login", icon="🔐")
dashboard_p = st.Page(page_dashboard, title="Plot Portfolio", icon="📊")
add_plot_p = st.Page(page_add_plot, title="Register Plot", icon="➕")
assessment_p = st.Page(page_assessment, title="Risk Assessment", icon="🌾")

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
    if active_target == "add_plot":
        pg = st.navigation([dashboard_p, add_plot_p, assessment_p], position="sidebar")
        # Direct render if requested
        add_plot_p.run()
        st.stop()
    elif active_target == "assessment":
        pg = st.navigation([dashboard_p, add_plot_p, assessment_p], position="sidebar")
        assessment_p.run()
        st.stop()
    else:
        pg = st.navigation([dashboard_p, add_plot_p, assessment_p], position="sidebar")

pg.run()
