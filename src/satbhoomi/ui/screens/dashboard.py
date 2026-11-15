"""Screen S2: Plot Portfolio Dashboard.

Displays active crop plots, district filtering, and session risk bands.
"""

from __future__ import annotations

import streamlit as st

from satbhoomi.ui.api_client import ApiClient, SessionExpiredError
from satbhoomi.ui.components import inject_custom_styles, render_prototype_banner
from satbhoomi.ui.state import clear_session, get_plot_band, get_token, is_authenticated


def render_dashboard_screen(api_client: ApiClient | None = None) -> None:
    """Render Screen S2: Portfolio Dashboard."""
    inject_custom_styles()

    if not is_authenticated():
        st.info("Please sign in to access the portfolio dashboard.")
        return

    render_prototype_banner()

    st.title("📊 Farm Plot Portfolio")
    st.markdown("Overview of registered agricultural parcels under monitoring in Anand District.")

    token = get_token()
    if not token:
        clear_session("Your session has ended. Please sign in again.")
        st.rerun()
        return

    client = api_client or ApiClient()

    # Controls: Filter and Pagination State
    if "dash_page" not in st.session_state:
        st.session_state["dash_page"] = 0
    if "dash_district" not in st.session_state:
        st.session_state["dash_district"] = "All Districts"

    col_filter, col_page = st.columns([2, 2])
    with col_filter:
        dist_options = ["All Districts", "Anand"]
        selected_dist = st.selectbox(
            "Filter by District",
            dist_options,
            index=dist_options.index(st.session_state["dash_district"])
            if st.session_state["dash_district"] in dist_options
            else 0,
            key="district_filter_select",
        )
        if selected_dist != st.session_state["dash_district"]:
            st.session_state["dash_district"] = selected_dist
            st.session_state["dash_page"] = 0
            st.rerun()

    page_size = 100
    offset = st.session_state["dash_page"] * page_size

    # Fetch plot records
    with st.spinner("Loading portfolio data from server..."):
        try:
            resp = client.list_plots(
                token=token,
                limit=page_size,
                offset=offset,
                district=st.session_state["dash_district"],
            )
        except SessionExpiredError:
            clear_session("Your session has ended. Please sign in again.")
            st.rerun()
            return
        except Exception as exc:
            st.error(f"Unable to load plots: {exc}")
            return

    items = resp.get("items", [])
    total_count = resp.get("total", len(items))

    # Metric Callout
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Total Active Plots", total_count)
    with col_m2:
        st.metric("Plots on Current Page", len(items))

    if not items:
        st.warning("No plots yet. Add one.")
        if st.button("Add New Plot", key="empty_add_plot_btn"):
            st.session_state["active_screen"] = "add_plot"
            st.rerun()
        return

    # Table Representation
    table_rows: list[dict[str, str]] = []
    for p in items:
        plot_id = int(p.get("id", 0))
        sess_band = get_plot_band(plot_id)
        band_display = sess_band.upper() if sess_band else "NOT ASSESSED"

        ins_val = p.get("insured", 0)
        ins_str = "Insured" if int(ins_val) == 1 else "Uninsured"

        table_rows.append(
            {
                "Plot Code": str(p.get("plot_code", f"PLOT-{plot_id:03d}")),
                "District": str(p.get("district", "Anand")),
                "Village / Area": str(p.get("village", "-")),
                "Area (Acres)": f"{float(p.get('area_acre', 0.0)):.2f}",
                "Irrigation": str(p.get("irrigation", "tube_well")).replace("_", " ").title(),
                "Crop Insurance": ins_str,
                "Session Risk Band": band_display,
            }
        )

    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    # Pagination navigation controls
    col_prev, col_info, col_next = st.columns([1, 2, 1])
    with col_prev:
        if st.session_state["dash_page"] > 0:
            if st.button("← Previous", key="prev_page_btn"):
                st.session_state["dash_page"] -= 1
                st.rerun()
    with col_info:
        current_page_num = st.session_state["dash_page"] + 1
        total_pages = max(1, (total_count + page_size - 1) // page_size)
        page_info = f"Page {current_page_num} of {total_pages}"
        st.markdown(
            f"<div style='text-align:center; padding-top:8px;'>{page_info}</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if (offset + len(items)) < total_count:
            if st.button("Next →", key="next_page_btn"):
                st.session_state["dash_page"] += 1
                st.rerun()
