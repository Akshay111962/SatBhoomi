"""Reusable UI components and styles for SatBhoomi Streamlit application.

Enforces:
- Mandatory prototype disclaimer banner on every authenticated screen.
- High-contrast calm green (#1E5631) and navy (#0A192F) palette.
- Accessible score visualization where color is never the only signal.
"""

from __future__ import annotations

import streamlit as st

PROTOTYPE_BANNER_TEXT = (
    "Prototype on sample data. Not a bank decision. Plots are sample points, not real farmers."
)


def render_prototype_banner() -> None:
    """Render mandatory persistent prototype notice at the top of every authenticated page."""
    st.markdown(
        f"""
        <div style="
            background-color: #FEF3C7;
            border-left: 6px solid #D97706;
            color: #78350F;
            padding: 12px 16px;
            border-radius: 4px;
            font-size: 0.95rem;
            font-weight: 500;
            margin-bottom: 20px;
        ">
            <strong>NOTICE:</strong> {PROTOTYPE_BANNER_TEXT}
        </div>
        """,
        unsafe_allow_html=True,
    )


def inject_custom_styles() -> None:
    """Inject CSS for responsive layout, high contrast, and accessible typography."""
    st.markdown(
        """
        <style>
        /* Base typography and palette */
        h1, h2, h3 {
            color: #0A192F !important;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        .stButton>button {
            background-color: #1E5631;
            color: #FFFFFF !important;
            font-weight: 600;
            border-radius: 4px;
            border: none;
            padding: 0.5rem 1.25rem;
        }
        .stButton>button:hover {
            background-color: #143D22;
        }
        /* Accessible Score Card */
        .score-box {
            padding: 24px;
            border-radius: 8px;
            text-align: center;
            margin: 16px 0;
        }
        .score-number {
            font-size: 4rem;
            font-weight: 800;
            line-height: 1;
            margin: 0;
        }
        .score-band-label {
            font-size: 1.4rem;
            font-weight: 700;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-top: 8px;
        }
        /* Callout cards */
        .info-card {
            background-color: #F8FAFC;
            border: 1px solid #CBD5E1;
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 16px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_score_card(score: int | None, band: str | None) -> None:
    """Render accessible large score display with paired text label and color.

    Color is NEVER the sole signal: a large uppercase text label is always displayed.
    """
    if score is None or band is None:
        st.markdown(
            """
            <div class="score-box" style="background-color: #F1F5F9; border: 2px dashed #94A3B8;">
                <p class="score-number" style="color: #64748B;">N/A</p>
                <p class="score-band-label" style="color: #475569;">INSUFFICIENT DATA</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    band_clean = str(band).strip().lower()
    if band_clean == "low":
        bg_color = "#ECFDF5"
        border_color = "#10B981"
        text_color = "#065F46"
        label = "LOW RISK"
    elif band_clean == "medium":
        bg_color = "#FFFBEB"
        border_color = "#F59E0B"
        text_color = "#92400E"
        label = "MEDIUM RISK"
    else:
        bg_color = "#FEF2F2"
        border_color = "#EF4444"
        text_color = "#991B1B"
        label = "HIGH RISK"

    st.markdown(
        f"""
        <div class="score-box"
             style="background-color: {bg_color}; border: 3px solid {border_color};">
            <p class="score-number" style="color: {text_color};">{score}</p>
            <p class="score-band-label" style="color: {text_color};">RISK TIER: {label}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
