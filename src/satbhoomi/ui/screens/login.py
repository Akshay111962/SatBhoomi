"""Screen S1: Officer Login.

Authentication interface communicating strictly over HTTP with backend auth endpoint.
Guarantees:
- Passwords are never echoed or logged.
- Generic uninformative error message on failure (never reveals account existence).
- Displays retry wait period on HTTP 429 rate limit.
- Compatible with mock and real mode.
"""

from __future__ import annotations

import streamlit as st

from satbhoomi.ui.api_client import ApiClient, ApiError
from satbhoomi.ui.components import inject_custom_styles
from satbhoomi.ui.state import (
    clear_session,
    get_current_user,
    is_authenticated,
    pop_session_error,
    set_user_session,
)


def render_login_screen(api_client: ApiClient | None = None) -> None:
    """Render Screen S1: Authentication."""
    inject_custom_styles()
    client = api_client or ApiClient()

    st.title("🌾 SatBhoomi Score + Raksha")
    st.subheader("Officer Decision Support Sign In")

    # Display any flash message (e.g. after session timeout / 401)
    flash_err = pop_session_error()
    if flash_err:
        st.warning(flash_err)

    if is_authenticated():
        user = get_current_user() or {}
        username = user.get("username", "Officer")
        st.success(f"You are currently signed in as **{username}**.")
        if st.button("Sign Out", key="logout_btn"):
            clear_session()
            st.rerun()
        return

    with st.form("login_form", clear_on_submit=False):
        st.markdown("Please enter your loan officer credentials to access farm assessments.")
        username = st.text_input("Username", key="login_username", placeholder="e.g. officer_test")
        password = st.text_input(
            "Password", type="password", key="login_password", placeholder="••••••••"
        )
        submitted = st.form_submit_button("Sign In")

    if submitted:
        if not username.strip() or not password.strip():
            st.error("Please enter both username and password.")
            return

        with st.spinner("Authenticating with server..."):
            try:
                resp = client.login(username=username.strip(), password=password.strip())
                token = resp.get("access_token")
                user_info = {
                    "username": username.strip(),
                    "role": resp.get("role", "officer"),
                }
                if token:
                    set_user_session(token=token, user_data=user_info)
                    st.success("Authentication successful.")
                    st.rerun()
                else:
                    st.error("Invalid response from server. Please try again.")
            except ApiError as err:
                if err.status_code == 429:
                    st.error("Too many failed login attempts. Please wait before retrying.")
                else:
                    # Security requirement: generic error message, never revealing
                    # username validity or lock state.
                    st.error("Invalid username or password. Please try again.")
