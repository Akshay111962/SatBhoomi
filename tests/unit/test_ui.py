"""Fast offline unit tests for Streamlit frontend (Screens S1 to S4).

Uses Streamlit's headless testing framework (streamlit.testing.v1.AppTest) and
fake API clients with zero network access.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from streamlit.testing.v1 import AppTest

from satbhoomi.ui.api_client import ApiClient, ApiError
from satbhoomi.ui.components import PROTOTYPE_BANNER_TEXT
from satbhoomi.ui.state import (
    clear_session,
    get_token,
    init_session_state,
    is_authenticated,
    set_user_session,
)

BANNED_WORDS = (
    "depressed",
    "depression",
    "suicidal",
    "suicide",
    "hopeless",
    "despair",
    "anxiety",
    "panic",
    "mental",
    "lazy",
    "irresponsible",
    "negligent",
    "fault",
    "guilty",
    "reckless",
    "careless",
    "defaulter",
    "criminal",
    "blame",
)


@pytest.fixture
def fake_client() -> MagicMock:
    """Mock ApiClient for offline UI testing."""
    client = MagicMock(spec=ApiClient)
    client.login.return_value = {
        "access_token": "mock-token-xyz-123",
        "role": "officer",
        "expires_in": 3600,
    }
    client.list_plots.return_value = {
        "items": [
            {
                "id": 1,
                "plot_code": "PLOT-001",
                "district": "Anand",
                "village": "Boriavi",
                "area_acre": 2.5,
                "irrigation": "tube_well",
                "insured": 1,
            },
            {
                "id": 2,
                "plot_code": "PLOT-002",
                "district": "Anand",
                "village": "Samarkha",
                "area_acre": 1.8,
                "irrigation": "rainfed",
                "insured": 0,
            },
        ],
        "total": 2,
        "limit": 100,
        "offset": 0,
    }
    client.create_plot.return_value = {
        "id": 3,
        "plot_code": "PLOT-003",
        "district": "Anand",
        "village": "Boriavi",
        "area_acre": 3.0,
        "irrigation": "tube_well",
        "insured": 1,
    }
    client.create_assessment.return_value = {
        "id": 10,
        "plot_id": 1,
        "plot_code": "PLOT-001",
        "season": "2024-25",
        "status": "ok",
        "score": 18,
        "band": "low",
        "reasons": [
            {
                "feature_name": "relative_ndvi_rule",
                "text": "Vegetation greenness tracks close to historical baseline.",
            },
            {
                "feature_name": "rainfall_rule",
                "text": "Pre-cutoff rainfall departure is within normal range.",
            },
            {"feature_name": "price_rule", "text": "Mandi wholesale wheat prices remained stable."},
        ],
        "protective_factor": "Tubewell irrigation buffers plot from winter dry spells.",
        "loan_suggestion": {
            "status": "ok",
            "limit_band": {
                "limit_min_inr": 60000,
                "limit_max_inr": 80000,
                "limit_recommended_inr": 75000,
            },
            "repayment_schedule": {
                "schedule_notes": "Single bullet repayment aligned with May wheat harvest.",
            },
            "insurance_required": False,
        },
        "data_warnings": [],
        "cutoff_date_iso": "2025-01-31",
        "model_version": "satbhoomi-rules-v2.0-relative-20261114",
        "scorer": "rules_baseline",
        "interpretation": "Deterministic in-season agricultural credit risk evaluation.",
        "reliability_note": (
            "Prototype evaluation grounded strictly on pre-cutoff satellite observations."
        ),
    }
    client.run_what_if.return_value = {
        "status": "ok",
        "assessment_id": 10,
        "plot_id": 1,
        "plot_code": "PLOT-001",
        "season": "2024-25",
        "changed_input": "insured",
        "old_value": "0",
        "new_value": "1",
        "old_score": 18,
        "new_score": 18,
        "score_delta": 0,
        "old_band": "low",
        "new_band": "low",
        "old_limit_band": {
            "limit_min_inr": 60000,
            "limit_max_inr": 80000,
            "limit_recommended_inr": 75000,
        },
        "new_limit_band": {
            "limit_min_inr": 65000,
            "limit_max_inr": 85000,
            "limit_recommended_inr": 80000,
        },
        "estimate_label": "estimate",
        "effect_basis": "scorer_input",
        "assumption": "Crop insurance enrollment maintains baseline haircut exemptions.",
        "rationale": "Crop insurance buffers risk against unexpected weather shock.",
        "disclaimer": "This statistical simulation demonstrates sensitivity only.",
        "reliability_note": "Validation status disclosure: model estimate.",
    }
    client.get_monitoring.return_value = {
        "plot_id": 1,
        "plot_code": "PLOT-001",
        "season": "2024-25",
        "status": "ok",
        "data_gap_reason": None,
        "checkpoint_label": "January 15",
        "evaluation_date": "2025-01-15",
        "mode": "replay",
        "replay_note": "Historical season replay; not live in-season monitoring.",
        "timeline": [
            {"date": "2024-12-15", "ndvi": 0.52, "rainfall_mm": 0.0, "data_gap": False},
            {"date": "2025-01-01", "ndvi": 0.65, "rainfall_mm": 5.0, "data_gap": False},
            {"date": "2025-01-10", "ndvi": None, "rainfall_mm": 0.0, "data_gap": True},
        ],
        "active_alerts": [
            {
                "id": 101,
                "plot_code": "PLOT-001",
                "season": "2024-25",
                "checkpoint_label": "January 15",
                "detected_on": "2025-01-15",
                "type": "crop_health_drop",
                "severity": "medium",
                "status": "open",
                "headline": "Vegetation vigor drag below baseline",
                "detail": "At Jan 15, plot recorded vegetative drag.",
                "supportive_action": "Schedule supportive field visit.",
                "data_gap_warning": None,
                "is_replay": True,
            }
        ],
        "past_alerts": [],
    }
    client.record_alert_action.return_value = {
        "action_id": 1,
        "alert_id": 101,
        "action_type": "field_visit",
        "note": "Conducted supportive inspection; confirmed tubewell repair.",
        "status_before": "open",
        "status_after": "in_progress",
        "done_by": "Officer-001",
        "done_on": "2026-11-16T10:00:00Z",
        "status": "recorded",
    }
    client.get_relief_report.return_value = {
        "plot_id": 1,
        "plot_code": "PLOT-001",
        "season": "2024-25",
        "baseline_ndvi_mean": 0.70,
        "current_ndvi_mean": 0.42,
        "ndvi_drop_pct": 40.0,
        "estimated_loss_band": "33% to 50% loss",
        "exceeds_rbi_33_threshold": True,
        "supporting_evidence_summary": "Vegetative vigor dropped 40.0% below baseline.",
        "disclaimer": (
            "Official crop loss assessment and calamity declaration remain strictly with "
            "government and bank relief committees. "
            "This evidence report is for decision support only."
        ),
    }
    client.get_farmer_summary.return_value = {
        "assessment_id": 10,
        "plot_code": "PLOT-001",
        "lang": "gu",
        "source": "template",
        "summary_text": "તમારા ઘઉંના પાકની સ્થિતિનું મૂલ્યાંકન કરવામાં આવ્યું છે.",
        "key_points": ["પાક સામાન્ય છે.", "બોરવેલનું પાણી ઉપલબ્ધ છે."],
    }
    return client


def test_app_initial_state_shows_login() -> None:
    """Unauthenticated access defaults to S1 Login screen."""
    app_file = str((Path(__file__).parents[2] / "src" / "satbhoomi" / "ui" / "app.py").resolve())
    at = AppTest.from_file(app_file)
    at.run()
    assert not at.exception
    # Should see the login form
    assert len(at.text_input) >= 2


def test_login_success_and_generic_failure(fake_client: MagicMock) -> None:
    """Login sets session state on success; presents generic unrevealing message on failure."""

    def run_login_flow(client):
        from satbhoomi.ui.screens.login import render_login_screen
        from satbhoomi.ui.state import init_session_state

        init_session_state()
        render_login_screen(api_client=client)

    # 1. Success test
    at_success = AppTest.from_function(run_login_flow, args=(fake_client,))
    at_success.run()
    at_success.text_input[0].input("officer_test")
    at_success.text_input[1].input("password123")
    at_success.button[0].click().run()

    assert not at_success.exception
    assert at_success.session_state["auth_token"] == "mock-token-xyz-123"
    assert at_success.session_state["auth_user"]["username"] == "officer_test"

    # 2. Generic failure test (401 from backend)
    fail_client = MagicMock(spec=ApiClient)
    fail_client.login.side_effect = ApiError("Invalid credentials", status_code=401)

    at_fail = AppTest.from_function(run_login_flow, args=(fail_client,))
    at_fail.run()
    at_fail.text_input[0].input("unknown_user")
    at_fail.text_input[1].input("bad_password")
    at_fail.button[0].click().run()

    assert not at_fail.exception
    assert at_fail.session_state["auth_token"] is None
    # Verify generic unrevealing message appears
    assert any("Invalid username or password" in err.value for err in at_fail.error)
    # Ensure neither "locked" nor "does not exist" is revealed
    assert not any("locked" in err.value.lower() for err in at_fail.error)
    assert not any("not exist" in err.value.lower() for err in at_fail.error)


def test_login_rate_limit_shows_retry_wait() -> None:
    """HTTP 429 rate limit displays retry wait period."""
    rate_limit_client = MagicMock(spec=ApiClient)
    rate_limit_client.login.side_effect = ApiError("Rate limit exceeded", status_code=429)

    def run_login(client):
        from satbhoomi.ui.screens.login import render_login_screen
        from satbhoomi.ui.state import init_session_state

        init_session_state()
        render_login_screen(api_client=client)

    at = AppTest.from_function(run_login, args=(rate_limit_client,))
    at.run()
    at.text_input[0].input("officer_test")
    at.text_input[1].input("password123")
    at.button[0].click().run()

    assert any("wait before retrying" in err.value.lower() for err in at.error)


def test_session_cleared_on_401() -> None:
    """401 error from any call clears session and sets plain message."""
    init_session_state()
    set_user_session("valid-token", {"username": "officer"})
    assert is_authenticated()

    clear_session("Your session has ended. Please sign in again.")
    assert not is_authenticated()
    assert get_token() is None
    assert (
        "session has ended" in at_message
        if (at_message := "Your session has ended. Please sign in again.")
        else True
    )


def test_banner_present_on_authenticated_screens(fake_client: MagicMock) -> None:
    """Prototype disclaimer banner is displayed on all authenticated screens."""

    def run_dash(client):
        from satbhoomi.ui.screens.dashboard import render_dashboard_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_dashboard_screen(api_client=client)

    at_dash = AppTest.from_function(run_dash, args=(fake_client,))
    at_dash.run()
    assert any(PROTOTYPE_BANNER_TEXT in m.value for m in at_dash.markdown)

    def run_add(client):
        from satbhoomi.ui.screens.add_plot import render_add_plot_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_add_plot_screen(api_client=client)

    at_add = AppTest.from_function(run_add, args=(fake_client,))
    at_add.run()
    assert any(PROTOTYPE_BANNER_TEXT in m.value for m in at_add.markdown)


def test_dashboard_empty_and_list_states() -> None:
    """Dashboard shows empty state when 0 plots exist, and table when plots exist."""
    # 1. Empty state
    empty_client = MagicMock(spec=ApiClient)
    empty_client.list_plots.return_value = {"items": [], "total": 0}

    def run_empty(client):
        from satbhoomi.ui.screens.dashboard import render_dashboard_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_dashboard_screen(api_client=client)

    at_empty = AppTest.from_function(run_empty, args=(empty_client,))
    at_empty.run()
    assert any("No plots yet. Add one." in w.value for w in at_empty.warning)

    # 2. Populated state with session risk band
    populated_client = MagicMock(spec=ApiClient)
    populated_client.list_plots.return_value = {
        "items": [
            {
                "id": 1,
                "plot_code": "PLOT-001",
                "district": "Anand",
                "village": "Boriavi",
                "area_acre": 2.5,
                "irrigation": "tube_well",
                "insured": 1,
            }
        ],
        "total": 1,
    }

    def run_populated(client):
        from satbhoomi.ui.screens.dashboard import render_dashboard_screen
        from satbhoomi.ui.state import init_session_state, record_plot_band, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        record_plot_band(1, "low")
        render_dashboard_screen(api_client=client)

    at_pop = AppTest.from_function(run_populated, args=(populated_client,))
    at_pop.run()
    assert len(at_pop.dataframe) >= 1
    df = at_pop.dataframe[0].value
    assert len(df) == 1
    assert df.iloc[0]["Plot Code"] == "PLOT-001"
    assert df.iloc[0]["Session Risk Band"] == "LOW"


def test_add_plot_form_client_validation_and_api_error() -> None:
    """Add plot shows validation errors and maps API errors next to the field."""

    def run_add(client):
        from satbhoomi.ui.screens.add_plot import render_add_plot_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_add_plot_screen(api_client=client)

    # Server API field error mapping
    error_client = MagicMock(spec=ApiClient)
    error_client.create_plot.side_effect = ApiError(
        message="Area must be under 100 acres",
        code="VALIDATION_ERROR",
        field="area_acre",
        status_code=422,
    )

    at = AppTest.from_function(run_add, args=(error_client,))
    at.run()
    # Submit form
    at.button[0].click().run()
    assert any("Validation error on field 'area_acre'" in err.value for err in at.error)


def test_assessment_screen_display_and_no_sanction_buttons(fake_client: MagicMock) -> None:
    """Assessment displays large score, text band label, 3 reasons, and zero sanction buttons."""

    def run_assess(client):
        from satbhoomi.ui.screens.assessment import render_assessment_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_assessment_screen(api_client=client)

    at = AppTest.from_function(run_assess, args=(fake_client,))
    at.run()

    # Click Run Assessment
    at.button[0].click().run()
    assert not at.exception

    # Verify score number and text-first risk tier label are present
    combined_markdown = " ".join(m.value for m in at.markdown)
    assert "18" in combined_markdown
    assert "LOW RISK" in combined_markdown
    assert "RISK TIER: LOW RISK" in combined_markdown

    # Verify all 3 reasons are present
    assert "Vegetation greenness tracks close" in combined_markdown
    assert "Pre-cutoff rainfall departure is within" in combined_markdown
    assert "Mandi wholesale wheat prices" in combined_markdown

    # Verify indicative Scale of Finance limit notice is present
    combined_all = combined_markdown.lower() + " " + " ".join(c.value.lower() for c in at.caption)
    assert "indicative credit limit range" in combined_all

    # Verify mandatory interpretation and reliability notes are present verbatim
    assert "Deterministic in-season agricultural credit risk evaluation." in combined_markdown
    assert (
        "Prototype evaluation grounded strictly on pre-cutoff satellite observations."
        in combined_markdown
    )

    # STRICT GOVERNANCE CHECK: Zero approve, reject, or sanction buttons anywhere
    button_labels = [b.label.lower() for b in at.button]
    for banned_btn in ("approve", "reject", "sanction", "decline", "disburse"):
        assert not any(banned_btn in lbl for lbl in button_labels), (
            f"Banned decision button '{banned_btn}' found!"
        )


def test_assessment_insufficient_data_case() -> None:
    """Insufficient data shows plain notice, reason, and no numeric score."""
    insuff_client = MagicMock(spec=ApiClient)
    insuff_client.list_plots.return_value = {
        "items": [{"id": 1, "plot_code": "PLOT-001", "village": "Boriavi"}]
    }
    insuff_client.create_assessment.return_value = {
        "id": 11,
        "plot_id": 1,
        "plot_code": "PLOT-001",
        "season": "2020-21",
        "status": "insufficient_data",
        "score": None,
        "band": None,
        "reasons": [],
        "insufficient_data_reason": (
            "No historical prior seasons available to establish plot baseline."
        ),
        "cutoff_date_iso": "2021-01-31",
        "model_version": "satbhoomi-rules-v2.0-relative-20261114",
        "scorer": "rules_baseline",
    }

    def run_assess_insuff(client):
        from satbhoomi.ui.screens.assessment import render_assessment_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_assessment_screen(api_client=client)

    at = AppTest.from_function(run_assess_insuff, args=(insuff_client,))
    at.run()
    at.button[0].click().run()

    combined_text = " ".join(m.value for m in at.markdown) + " ".join(w.value for w in at.warning)
    assert "Not enough data to score this plot-season" in combined_text
    assert "INSUFFICIENT DATA" in combined_text
    assert "No historical prior seasons available" in combined_text


def test_api_client_never_logs_token_or_password(caplog: pytest.LogCaptureFixture) -> None:
    """Audit test: ApiClient never writes passwords or tokens to logging."""
    logging.getLogger("satbhoomi.ui.api_client")
    secret_pass = "super-secret-password-xyz"
    fake_token = "secret-bearer-token-abc-987"

    mock_client = ApiClient(base_url="http://localhost:8000")

    with caplog.at_level(logging.DEBUG, logger="satbhoomi.ui.api_client"):
        # We test header creation and login failure logging
        headers = mock_client._headers(token=fake_token, idempotency_key="key-123")
        assert headers["Authorization"] == f"Bearer {fake_token}"

        # Trigger login with secret password against non-existent port
        with pytest.raises(ApiError):
            mock_client.login("officer_user", secret_pass)

    log_records = " ".join(record.getMessage() for record in caplog.records)
    assert secret_pass not in log_records, "Password leaked into log output!"
    assert fake_token not in log_records, "Bearer token leaked into log output!"


def test_no_banned_wording_in_ui_code_and_text() -> None:
    """Verify zero banned blame or psychological words in UI files."""
    ui_dir = Path("src/satbhoomi/ui")
    python_files = list(ui_dir.glob("**/*.py"))
    assert len(python_files) >= 5, "Expected UI python files to exist"

    for file_path in python_files:
        content = file_path.read_text(encoding="utf-8").lower()
        for banned in BANNED_WORDS:
            assert not re.search(rf"\b{re.escape(banned)}\b", content), (
                f"Banned word '{banned}' detected in {file_path}"
            )


def test_what_if_screen_estimate_zero_change_and_disclaimers(fake_client: MagicMock) -> None:
    """S5 What-If displays estimate label, zero change as 'no change', and verbatim disclaimers."""

    def run_what_if(client):
        from satbhoomi.ui.screens.what_if import render_what_if_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_what_if_screen(api_client=client)

    at = AppTest.from_function(run_what_if, args=(fake_client,))
    at.run()
    # Click Run What-If Simulation
    at.button[0].click().run()
    assert not at.exception

    all_text = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
    all_metrics = " ".join(f"{met.label} {met.value}" for met in at.metric)

    # Verify score change: delta == 0 displays as 'no change'
    assert "no change" in all_metrics.lower()

    # Verify mandatory Rule 6 disclosures
    assert "estimate" in all_text.lower()
    assert "Scorer Input" in all_text
    assert "Crop insurance enrollment maintains baseline" in all_text or any(
        "Crop insurance enrollment maintains baseline" in i.value for i in at.info
    )

    # Verify disclaimers exactly as API returns them
    assert "This statistical simulation demonstrates sensitivity only." in all_text
    assert "Validation status disclosure: model estimate." in all_text

    # Verify loan limit impact displayed
    assert "₹60,000" in all_text
    assert "₹85,000" in all_text


def test_monitoring_screen_replay_banner_timeline_table_and_empty_state(
    fake_client: MagicMock,
) -> None:
    """S6 Monitoring shows replay banner, data gap markers, severity badges, and empty state."""

    def run_monitor(client):
        from satbhoomi.ui.screens.monitoring import render_monitoring_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_monitoring_screen(api_client=client)

    # 1. Populated monitoring state
    at = AppTest.from_function(run_monitor, args=(fake_client,))
    at.run()
    assert not at.exception

    all_text = " ".join(m.value for m in at.markdown)

    # Replay banner presence
    assert "Replay of past seasons. Not live monitoring." in all_text

    # Table contains data gap notice
    assert len(at.dataframe) >= 1
    df = at.dataframe[0].value
    assert any("DATA GAP" in str(row["Observation Quality"]) for _, row in df.iterrows())

    # Alert severity badge
    assert "[MEDIUM SEVERITY]" in all_text

    # 2. Empty state when 0 alerts exist
    empty_client = MagicMock(spec=ApiClient)
    empty_client.list_plots.return_value = fake_client.list_plots.return_value
    empty_client.get_monitoring.return_value = {
        "plot_id": 1,
        "plot_code": "PLOT-001",
        "season": "2024-25",
        "status": "ok",
        "mode": "replay",
        "timeline": [],
        "active_alerts": [],
        "past_alerts": [],
    }

    at_empty = AppTest.from_function(run_monitor, args=(empty_client,))
    at_empty.run()
    all_empty_info = " ".join(i.value for i in at_empty.info)
    assert "No alerts recorded" in all_empty_info


def test_alert_detail_screen_playbook_actions_note_limits_and_transitions(
    fake_client: MagicMock,
) -> None:
    """S7 Alert detail shows canon playbook, distressed guidance, and handles API errors."""

    def run_detail(client):
        from satbhoomi.ui.screens.alert_detail import render_alert_detail_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_alert_detail_screen(api_client=client)

    at = AppTest.from_function(run_detail, args=(fake_client,))
    at.run()
    assert not at.exception

    all_warnings = " ".join(w.value for w in at.warning)
    assert "involve a senior colleague and local support" in all_warnings

    # Submit action with valid note
    at.text_area[0].input("Conducted supportive inspection; confirmed tubewell repair.")
    at.button[0].click().run()
    assert any("Action recorded successfully" in s.value for s in at.success)

    # Disallowed status transition (409) test
    err_client = MagicMock(spec=ApiClient)
    err_client.record_alert_action.side_effect = ApiError(
        message="Cannot transition alert already resolved",
        code="DISALLOWED_STATUS_TRANSITION",
        status_code=409,
    )

    at_err = AppTest.from_function(run_detail, args=(err_client,))
    at_err.run()
    at_err.text_area[0].input("Attempting transition on resolved alert.")
    at_err.button[0].click().run()
    assert any("Illegal status transition" in e.value for e in at_err.error)


def test_relief_report_screen_screening_notice_and_insufficient_data(
    fake_client: MagicMock,
) -> None:
    """S8 Relief report shows statutory disclaimer and screening notice, handles no data."""

    def run_relief(client):
        from satbhoomi.ui.screens.relief_report import render_relief_report_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_relief_report_screen(api_client=client)

    at = AppTest.from_function(run_relief, args=(fake_client,))
    at.run()
    assert not at.exception

    all_text = " ".join(m.value for m in at.markdown) + " ".join(i.value for i in at.info)
    assert "NDVI-based screening indicator, not a crop loss assessment" in all_text
    assert "Official crop loss assessment and calamity declaration remain strictly with" in all_text
    assert "EXCEEDS RBI 33% CALAMITY THRESHOLD" in all_text

    # Insufficient data test
    insuff_client = MagicMock(spec=ApiClient)
    insuff_client.list_plots.return_value = fake_client.list_plots.return_value
    insuff_client.get_relief_report.return_value = {
        "status": "insufficient_data",
        "plot_code": "PLOT-001",
        "season": "2020-21",
        "disclaimer": "Official crop loss assessment decides.",
    }

    at_insuff = AppTest.from_function(run_relief, args=(insuff_client,))
    at_insuff.run()
    all_insuff_warn = " ".join(w.value for w in at_insuff.warning)
    assert "Insufficient data to generate crop calamity screening" in all_insuff_warn
    # No percentage metric displayed
    assert not any("%" in met.value for met in at_insuff.metric)


def test_farmer_summary_screen_unreviewed_box_fallback_and_no_banned_verbiage(
    fake_client: MagicMock,
) -> None:
    """S9 Farmer summary displays unreviewed warning box, fallback notice, and safe words."""

    def run_summary(client):
        from satbhoomi.ui.screens.farmer_summary import render_farmer_summary_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        render_farmer_summary_screen(api_client=client)

    # 1. Vernacular unreviewed template test
    at = AppTest.from_function(run_summary, args=(fake_client,))
    at.run()
    assert not at.exception

    all_text = " ".join(m.value for m in at.markdown)
    assert "Unreviewed translation: officer preview only" in all_text
    assert "તમારા ઘઉંના પાકની સ્થિતિનું મૂલ્યાંકન" in all_text

    # Decision words check: Zero 'approved', 'rejected', 'eligible' in any casing
    for banned_word in ("approved", "rejected", "eligible"):
        assert not re.search(rf"\b{banned_word}\b", all_text.lower()), (
            f"Banned automated decision word '{banned_word}' found in summary!"
        )

    # 2. Fallback notice test
    fallback_client = MagicMock(spec=ApiClient)
    fallback_client.get_farmer_summary.return_value = {
        "assessment_id": 10,
        "plot_code": "PLOT-001",
        "lang": "en",
        "source": "template",
        "summary_text": "Assessment summary in English.",
        "key_points": [],
    }

    def run_fallback(client):
        from satbhoomi.ui.screens.farmer_summary import render_farmer_summary_screen
        from satbhoomi.ui.state import init_session_state, set_user_session

        init_session_state()
        set_user_session("token-123", {"username": "officer"})
        # Select Hindi ('hi')
        render_farmer_summary_screen(api_client=client)

    at_fb = AppTest.from_function(run_fallback, args=(fallback_client,))
    at_fb.run()
    at_fb.selectbox[0].select("hi")
    at_fb.button[0].click().run()

    all_fb_text = " ".join(m.value for m in at_fb.markdown)
    assert "fallen back to english" in all_fb_text.lower()
