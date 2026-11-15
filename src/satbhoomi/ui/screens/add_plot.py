"""Screen S3: Register Plot.

Form matching PlotCreateRequest schema with zero-PII guarantees and officer attribute disclaimers.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from satbhoomi.ui.api_client import ApiClient, ApiError, SessionExpiredError
from satbhoomi.ui.components import inject_custom_styles, render_prototype_banner
from satbhoomi.ui.state import clear_session, get_token, is_authenticated


def render_add_plot_screen(api_client: ApiClient | None = None) -> None:
    """Render Screen S3: Plot Registration Form."""
    inject_custom_styles()

    if not is_authenticated():
        st.info("Please sign in to register a plot.")
        return

    render_prototype_banner()

    st.title("➕ Register New Plot Parcel")
    st.markdown(
        "Enter agricultural plot parameters for in-season monitoring and credit scoring. "
        "Strict compliance rule: **Do not enter farmer names, phone numbers, or Aadhaar numbers**."
    )

    token = get_token()
    if not token:
        clear_session("Your session has ended. Please sign in again.")
        st.rerun()
        return

    client = api_client or ApiClient()

    # Placeholders for inline error messages mapped to field names
    field_errors: dict[str, str] = st.session_state.get("add_plot_field_errors", {})

    with st.form("add_plot_form", clear_on_submit=False):
        st.subheader("Parcel Identification & Location")

        c1, c2 = st.columns(2)
        with c1:
            st.text_input(
                "Farmer Display Code *",
                value="Farmer-001",
                help="Synthetic anonymized code only. Never enter real names or identity cards.",
                key="field_farmer_code",
            )
            if "farmer_id" in field_errors:
                st.error(field_errors["farmer_id"])

            district = st.text_input(
                "District *",
                value="Anand",
                help="District in Gujarat, India.",
                key="field_district",
            )
            if "district" in field_errors:
                st.error(field_errors["district"])

        with c2:
            farmer_id_val = st.number_input(
                "Internal Farmer Reference ID *",
                min_value=1,
                value=1,
                step=1,
                help="Numeric identifier from local cadastral records.",
                key="field_farmer_id",
            )

            village = st.text_input(
                "Village / Local Area *",
                value="Boriavi",
                help="Village jurisdiction within the district.",
                key="field_village",
            )
            if "village" in field_errors:
                st.error(field_errors["village"])

        st.subheader("Agronomic Attributes")

        c3, c4 = st.columns(2)
        with c3:
            area_acre = st.number_input(
                "Operational Area (Acres) *",
                min_value=0.1,
                max_value=100.0,
                value=2.5,
                step=0.1,
                help="Cultivated area (must be greater than 0.0 acres).",
                key="field_area_acre",
            )
            if "area_acre" in field_errors:
                st.error(field_errors["area_acre"])

            st.text_input(
                "Target Crop",
                value="wheat",
                disabled=True,
                help="SatBhoomi v1 models wheat (Triticum aestivum) in the Rabi winter season.",
            )

        with c4:
            irrigation_options = ["tube_well", "canal", "rainfed"]
            irrigation = st.selectbox(
                "Irrigation Infrastructure Source *",
                irrigation_options,
                format_func=lambda x: {
                    "tube_well": "Tubewell / Borewell (Groundwater)",
                    "canal": "Canal Irrigation",
                    "rainfed": "Rainfed (No Assured Irrigation)",
                }.get(x, x),
                key="field_irrigation",
            )

            insured_options = [1, 0]
            insured = st.selectbox(
                "Crop Insurance Enrollment (PMFBY) *",
                insured_options,
                format_func=lambda x: (
                    "Enrolled in Crop Insurance (1)" if x == 1 else "Not Insured (0)"
                ),
                key="field_insured",
            )

        st.caption(
            "Note: Irrigation source and crop insurance coverage are "
            "**officer-recorded attributes** based on farmer declaration and verification, "
            "not satellite-observed facts."
        )

        st.subheader("Geographical Coordinates")
        c5, c6 = st.columns(2)
        with c5:
            lat = st.number_input("Latitude", value=22.5645, format="%.5f", key="field_lat")
        with c6:
            lon = st.number_input("Longitude", value=72.9289, format="%.5f", key="field_lon")

        submitted = st.form_submit_button("Register Plot Parcel")

    if submitted:
        st.session_state["add_plot_field_errors"] = {}

        # Client-side validation mirroring API rules
        local_errors: dict[str, str] = {}
        if area_acre <= 0.0:
            local_errors["area_acre"] = "Operational area must be strictly greater than 0.0 acres."
        if not district.strip():
            local_errors["district"] = "District is required."
        if not village.strip():
            local_errors["village"] = "Village is required."

        if local_errors:
            st.session_state["add_plot_field_errors"] = local_errors
            st.rerun()
            return

        payload: dict[str, Any] = {
            "farmer_id": int(farmer_id_val),
            "crop": "wheat",
            "area_acre": float(area_acre),
            "district": district.strip(),
            "village": village.strip(),
            "lat": float(lat),
            "lon": float(lon),
            "irrigation": irrigation,
            "insured": int(insured),
        }

        with st.spinner("Submitting plot registration to server..."):
            try:
                resp = client.create_plot(payload, token=token)
                new_id = resp.get("id")
                new_code = resp.get("plot_code", f"PLOT-{new_id}")
                st.session_state["newly_added_plot"] = {
                    "id": new_id,
                    "code": new_code,
                }
                st.success(f"Plot **{new_code}** successfully registered!")
                if st.button("Run Assessment for this Plot →", key="goto_assess_btn"):
                    st.session_state["selected_plot_id"] = new_id
                    st.session_state["active_screen"] = "assessment"
                    st.rerun()
            except SessionExpiredError:
                clear_session("Your session has ended. Please sign in again.")
                st.rerun()
            except ApiError as err:
                if err.field:
                    st.session_state["add_plot_field_errors"] = {err.field: err.message}
                    st.error(f"Validation error on field '{err.field}': {err.message}")
                else:
                    st.error(f"Error registering plot: {err.message}")
