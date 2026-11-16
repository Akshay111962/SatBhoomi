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
REPLAY_BANNER_TEXT = (
    "Replay of past seasons. Not live monitoring. No claim of detecting real stress events."
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


def render_replay_banner() -> None:
    """Render mandatory disclaimer banner for historical in-season replay monitoring."""
    st.markdown(
        f"""
        <div style="
            background-color: #EFF6FF;
            border-left: 6px solid #2563EB;
            color: #1E3A8A;
            padding: 12px 16px;
            border-radius: 4px;
            font-size: 0.95rem;
            font-weight: 500;
            margin-bottom: 16px;
        ">
            <strong>MONITORING MODE:</strong> {REPLAY_BANNER_TEXT}
        </div>
        """,
        unsafe_allow_html=True,
    )


def inject_custom_styles() -> None:
    """Inject CSS for responsive layout, high contrast, typography, and print styles."""
    st.markdown(
        """
        <style>
        /* Base typography and palette with Gujarati and Devanagari font fallbacks */
        body, p, div, span, table, td, th {
            font-family: 'Noto Sans Gujarati', 'Noto Sans Devanagari',
                -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        }
        h1, h2, h3, h4 {
            color: #0A192F !important;
            font-family: 'Noto Sans Gujarati', 'Noto Sans Devanagari',
                -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
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
        .unreviewed-box {
            background-color: #FFFBEB;
            border: 2px dashed #D97706;
            border-radius: 6px;
            padding: 18px;
            margin-top: 12px;
            margin-bottom: 16px;
        }
        .unreviewed-box-warning {
            color: #92400E;
            font-weight: 700;
            font-size: 0.95rem;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .selectable-text {
            user-select: text !important;
            -webkit-user-select: text !important;
            line-height: 1.6;
            font-size: 1.05rem;
            color: #1E293B;
        }
        /* Print-friendly view */
        @media print {
            header, .stSidebar, [data-testid="stSidebar"],
            .stButton, footer, [data-testid="stToolbar"] {
                display: none !important;
            }
            .main, .block-container {
                padding: 0 !important;
                max-width: 100% !important;
            }
            .info-card, .score-box {
                border: 1px solid #333 !important;
                page-break-inside: avoid;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_severity_badge(severity: str) -> str:
    """Return HTML string for alert severity badge where color is paired with text."""
    sev = str(severity).strip().lower()
    base_style = "padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.85rem;"
    if sev == "high":
        return (
            f'<span style="background-color: #FEE2E2; color: #991B1B; '
            f'border: 1px solid #EF4444; {base_style}">[HIGH SEVERITY]</span>'
        )
    elif sev == "medium":
        return (
            f'<span style="background-color: #FEF3C7; color: #92400E; '
            f'border: 1px solid #F59E0B; {base_style}">[MEDIUM SEVERITY]</span>'
        )
    return (
        f'<span style="background-color: #E2E8F0; color: #334155; '
        f'border: 1px solid #94A3B8; {base_style}">[LOW SEVERITY]</span>'
    )


def render_unreviewed_translation_box(
    text: str,
    key_points: list[str] | None = None,
    fallback_note: str | None = None,
) -> None:
    """Render vernacular text inside mandatory unreviewed preview container.

    Enforces:
    - Clear warning banner.
    - Selectable and copyable text.
    - Fallback notification when appropriate.
    """
    warning_html = (
        "⚠️ Unreviewed translation: officer preview only. "
        "Do not show to a farmer until a reader of this language has reviewed it."
    )
    fallback_html = ""
    if fallback_note:
        fallback_html = (
            '<div style="color: #475569; font-size: 0.85rem; font-style: italic; '
            f'margin-bottom: 10px;">ℹ️ {fallback_note}</div>'
        )

    points_html = ""
    if key_points:
        points_html = "<ul>" + "".join(f"<li>{pt}</li>" for pt in key_points) + "</ul>"

    st.markdown(
        f"""
        <div class="unreviewed-box">
            <div class="unreviewed-box-warning">{warning_html}</div>
            {fallback_html}
            <div class="selectable-text">
                <p><strong>Summary:</strong> {text}</p>
                {points_html}
            </div>
        </div>
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
