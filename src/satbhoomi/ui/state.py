"""Session state management for SatBhoomi Streamlit UI.

Strict Privacy & Security Constraints:
- Bearer token and user credentials exist strictly in ephemeral Streamlit session state.
- Never persisted to disk, URLs, cookies, or shared global caches.
- 401 response or logout triggers complete session teardown.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

TOKEN_KEY = "auth_token"
USER_KEY = "auth_user"
SESSION_ERROR_KEY = "session_flash_error"
PLOT_BANDS_KEY = "session_plot_bands"


def init_session_state() -> None:
    """Initialize default session state keys if not already present."""
    if TOKEN_KEY not in st.session_state:
        st.session_state[TOKEN_KEY] = None
    if USER_KEY not in st.session_state:
        st.session_state[USER_KEY] = None
    if SESSION_ERROR_KEY not in st.session_state:
        st.session_state[SESSION_ERROR_KEY] = None
    if PLOT_BANDS_KEY not in st.session_state:
        st.session_state[PLOT_BANDS_KEY] = {}


def set_user_session(token: str, user_data: dict[str, Any]) -> None:
    """Store authenticated token and officer details in session."""
    st.session_state[TOKEN_KEY] = token
    st.session_state[USER_KEY] = user_data
    st.session_state[SESSION_ERROR_KEY] = None


def clear_session(flash_message: str | None = None) -> None:
    """Completely wipe authentication credentials from session state."""
    st.session_state[TOKEN_KEY] = None
    st.session_state[USER_KEY] = None
    st.session_state[PLOT_BANDS_KEY] = {}
    if flash_message:
        st.session_state[SESSION_ERROR_KEY] = flash_message


def is_authenticated() -> bool:
    """Return True if an active session token exists."""
    return bool(st.session_state.get(TOKEN_KEY))


def get_token() -> str | None:
    """Retrieve active session token."""
    return st.session_state.get(TOKEN_KEY)


def get_current_user() -> dict[str, Any] | None:
    """Retrieve logged-in user profile dictionary."""
    return st.session_state.get(USER_KEY)


def record_plot_band(plot_id: int, band: str) -> None:
    """Record latest risk band for a plot in current user session."""
    bands = st.session_state.get(PLOT_BANDS_KEY, {})
    bands[plot_id] = band
    st.session_state[PLOT_BANDS_KEY] = bands


def get_plot_band(plot_id: int) -> str | None:
    """Retrieve latest risk band assessed in this session for a plot."""
    return st.session_state.get(PLOT_BANDS_KEY, {}).get(plot_id)


def pop_session_error() -> str | None:
    """Retrieve and clear any pending session flash message."""
    msg = st.session_state.get(SESSION_ERROR_KEY)
    st.session_state[SESSION_ERROR_KEY] = None
    return msg
