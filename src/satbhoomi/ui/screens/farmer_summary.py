"""Screen S9: Farmer Vernacular Credit Assessment Summary.

Displays:
- Plain-language credit assessment summary in English (en), Gujarati (gu), or Hindi (hi).
- Text provenance (deterministic template vs. human-reviewed translation).
- Mandatory unreviewed translation preview warning box when source != 'reviewed'.
- Fallback notice when translation falls back to English.
- Selectable and copyable text with Gujarati and Devanagari font stack.
- Strict compliance: zero 'approved', 'rejected', or 'eligible' wording.
  States that the bank officer decides.
"""

from __future__ import annotations

import streamlit as st

from satbhoomi.ui.api_client import ApiClient, ApiError, SessionExpiredError
from satbhoomi.ui.components import (
    inject_custom_styles,
    render_prototype_banner,
    render_unreviewed_translation_box,
)
from satbhoomi.ui.state import clear_session, get_token

LANG_NAMES = {
    "en": "English",
    "gu": "ગુજરાતી (Gujarati)",
    "hi": "हिन्दी (Hindi)",
}


def render_farmer_summary_screen(api_client: ApiClient | None = None) -> None:
    """Render Screen S9: Farmer Vernacular Summary."""
    inject_custom_styles()
    render_prototype_banner()
    client = api_client or ApiClient()

    st.title("🗣️ Farmer Vernacular Summary")
    st.caption(
        "Plain-language explanation of credit assessment parameters for discussion with the "
        "farmer. The loan officer makes all final credit determinations."
    )

    token = get_token()
    if not token:
        st.warning("Please sign in to access the Farmer Summary.")
        return

    # Check active assessment in session
    latest_asm = st.session_state.get("latest_assessment_result")
    default_asm_id = int(latest_asm.get("id", 1)) if latest_asm and latest_asm.get("id") else 1

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        assessment_id = st.number_input(
            "Assessment Reference ID *",
            min_value=1,
            value=default_asm_id,
            step=1,
            help="Reference ID of the completed assessment.",
            key="farmer_summary_asm_id",
        )
    with c2:
        target_lang = st.selectbox(
            "Select Communication Language *",
            options=["en", "gu", "hi"],
            format_func=lambda code: LANG_NAMES.get(code, code),
            index=0,
            key="farmer_summary_lang_select",
        )
    with c3:
        st.write("")
        st.write("")
        fetch_btn = st.button("Generate Summary", type="primary", key="btn_get_farmer_summary")

    if fetch_btn or "current_farmer_summary" not in st.session_state:
        with st.spinner("Generating plain-language summary..."):
            try:
                summary_data = client.get_farmer_summary(
                    assessment_id=int(assessment_id),
                    lang=target_lang,
                    token=token,
                )
                summary_data["requested_lang"] = target_lang
                st.session_state["current_farmer_summary"] = summary_data
            except SessionExpiredError:
                clear_session("Your session has ended. Please sign in again.")
                st.rerun()
                return
            except ApiError as err:
                if err.status_code == 501:
                    st.info(
                        "Vernacular summary generator active in mock mode "
                        "(501 in real database mode)."
                    )
                    st.session_state["current_farmer_summary"] = {
                        "assessment_id": int(assessment_id),
                        "plot_code": f"PLOT-{assessment_id:03d}",
                        "lang": "en",
                        "requested_lang": target_lang,
                        "source": "template",
                        "summary_text": (
                            "Your crop vigor and water availability have been recorded for "
                            "loan officer review. The authorized bank officer will discuss "
                            "loan sizing and harvest-aligned repayment."
                        ),
                        "key_points": [
                            "Crop vigor is recorded.",
                            "Repayment schedule aligns with harvest.",
                            "Credit determination resides solely with the human loan officer.",
                        ],
                    }
                else:
                    st.error(f"Unable to fetch farmer summary ({err.code}): {err.message}")
                    return

    data = st.session_state.get("current_farmer_summary")
    if not data:
        st.info("Select an assessment reference ID and language, then click 'Generate Summary'.")
        return

    st.divider()

    # Metadata row
    c_meta1, c_meta2, c_meta3 = st.columns(3)
    with c_meta1:
        st.markdown(f"**Plot Parcel:** `{data.get('plot_code', 'PLOT')}`")
        st.markdown(f"**Assessment ID:** `#{data.get('assessment_id', assessment_id)}`")
    with c_meta2:
        resp_lang = data.get("lang", "en")
        st.markdown(f"**Language:** `{resp_lang}` ({LANG_NAMES.get(resp_lang, resp_lang)})")
        st.markdown(f"**Source Provenance:** `{data.get('source', 'template')}`")
    with c_meta3:
        is_reviewed = data.get("source") == "reviewed"
        if is_reviewed:
            st.success("Human Reviewed Translation")
        else:
            st.warning("Automated Template Translation")

    req_lang = data.get("requested_lang", target_lang)
    fell_back_to_en = req_lang != "en" and resp_lang == "en"
    fallback_note = (
        f"Language '{LANG_NAMES.get(req_lang, req_lang)}' is currently unavailable; "
        "fallen back to English."
        if fell_back_to_en
        else None
    )

    summary_text = data.get("summary_text", "")
    key_points = data.get("key_points", [])

    st.subheader("Assessment Explanation")

    # If language is English and reviewed or English template:
    # If not reviewed (or vernacular template), must appear inside the mandatory warning box
    if resp_lang == "en" and is_reviewed:
        pts_list = (
            "<ul>" + "".join(f"<li>{pt}</li>" for pt in key_points) + "</ul>" if key_points else ""
        )
        st.markdown(
            f"""
            <div class="info-card selectable-text">
                <p><strong>Summary:</strong> {summary_text}</p>
                {pts_list}
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        # Non-reviewed or non-English: must show inside the warning container
        render_unreviewed_translation_box(
            text=summary_text,
            key_points=key_points,
            fallback_note=fallback_note,
        )

    # Decision-Support Notice
    st.info(
        "ℹ️ **Decision Authority:** All credit determinations, limit sizing, and repayment "
        "terms reside solely with the authorized bank loan officer. This summary provides "
        "transparent explanation for farmer dialogue."
    )
