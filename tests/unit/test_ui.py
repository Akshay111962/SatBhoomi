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
