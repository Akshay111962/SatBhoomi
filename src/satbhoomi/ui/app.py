"""Streamlit user interface entry point for SatBhoomi Score + Raksha."""

import streamlit as st

st.set_page_config(
    page_title="SatBhoomi Score + Raksha",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom calm green and navy styling
st.markdown(
    """
    <style>
    .main-title {
        color: #1b4332;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #1a2a3a;
        font-size: 1.1rem;
        margin-bottom: 1.5rem;
    }
    .status-card {
        background-color: #f0f7f4;
        border-left: 5px solid #2d6a4f;
        padding: 1rem 1.2rem;
        border-radius: 4px;
        margin-bottom: 1.5rem;
    }
    .status-card h4 {
        color: #1b4332;
        margin: 0 0 0.5rem 0;
    }
    .status-card p {
        color: #264653;
        margin: 0;
    }
    .disclaimer-box {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        font-size: 0.85rem;
        color: #495057;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">SatBhoomi Score + Raksha</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">'
    "AI Farm Credit Scoring & Early-Warning Decision Support for Bank Officers"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="status-card">
        <h4>System Foundation Active (Blueprint Task T-01)</h4>
        <p>The system infrastructure, modular monolith service architecture, API contracts,
        and database engine are initialized and operational.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("🌾 SatBhoomi Score")
    st.caption("Farm Credit Assessment")
    st.write(
        "Combines multi-season satellite crop health (NDVI), rainfall deficit, and mandi prices "
        "to deliver a calibrated 0–100 risk score with top plain-language reasons and "
        "right-sized limits."
    )
    st.info("Pipeline connector setup in progress (Task T-02).")

with col2:
    st.subheader("🛡️ Raksha Early Warning")
    st.caption("In-Season Monitoring")
    st.write(
        "Detects in-season crop health drops, rainfall anomalies, and price crashes early. "
        "Provides actionable playbooks focused on repayment support and insurance assistance."
    )
    st.info("Alert engine scheduled for Task T-09.")

with col3:
    st.subheader("📋 Relief Evidence")
    st.caption("RBI 33% Calamity Support")
    st.write(
        "Generates objective before-vs-after crop loss evidence aligned with the RBI 33% crop loss "
        "rescheduling framework to support timely restructuring decisions."
    )
    st.info("Report generator scheduled for Task T-12.")

st.divider()

st.markdown(
    """
    <div class="disclaimer-box">
        <strong>Operating Notice:</strong> SatBhoomi Score + Raksha is an advisory
        decision-support tool. The system never automatically approves or rejects loans;
        credit decisions reside solely with the authorized bank officer.
    </div>
    """,
    unsafe_allow_html=True,
)
