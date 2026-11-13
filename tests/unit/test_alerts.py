"""Unit tests for Raksha Alert Engine and Historical Season Replay (T-09, FR-008).

Validates:
1. Crop health drop compares against plot's own prior seasons on identical date.
2. Data gap handling (minimum 2 clear observations, minimum 1 prior season).
3. Rainfall deficit capping for irrigated plots (high allowed only for rainfed).
4. APMC mandi price crash against district-level prior monthly baselines.
5. In-season alert de-duplication and severity escalation (no duplicates).
6. Zero look-ahead leakage test (truncated dataset yields identical alerts).
7. TC-007 synthetic stress scenario validation (lead time >= 6 weeks).
8. Alert ORM schema compatibility (constraints match db/models/alert.py).
9. Rule 2 ethical compliance: supportive officer actions, no banned words, repayment stress framing.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from satbhoomi.alerts.config import (
    ALLOWED_ALERT_TYPES,
    ALLOWED_SEVERITIES,
    ALLOWED_STATUSES,
)
from satbhoomi.alerts.engine import (
    InSeasonAlertTracker,
    evaluate_crop_health_drop,
    evaluate_price_crash,
    evaluate_rainfall_deficit,
)
from satbhoomi.alerts.models import AlertItem
from satbhoomi.alerts.replay import (
    generate_synthetic_stress_scenario,
    replay_single_plot_season,
    run_full_replay,
)
from satbhoomi.db.models.alert import Alert

BANNED_MENTAL_OR_BLAME_WORDS: tuple[str, ...] = (
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


# ---------------------------------------------------------------------------
# 1. Crop Health Decline Rule Tests
# ---------------------------------------------------------------------------


def test_crop_health_drop_compares_to_own_prior_seasons_same_date() -> None:
    """NDVI drop must compare against plot's own prior seasons on the same date."""
    # Baseline: mean 0.50 across prior seasons on Dec 15
    prior_ndvis = [0.48, 0.52]  # mean = 0.50

    # Case A: Current NDVI is 0.40 -> (0.50 - 0.40) / 0.50 = 20% drop -> MEDIUM severity
    alert_med, gap = evaluate_crop_health_drop(
        plot_code="PLOT_TEST_01",
        season="2023-24",
        checkpoint_label="Dec 15",
        detected_on=date(2023, 12, 15),
        current_ndvi=0.40,
        prior_ndvis_same_checkpoint=prior_ndvis,
        clear_obs_count=3,
    )
    assert gap is None
    assert alert_med is not None
    assert alert_med.severity == "medium"
    assert alert_med.type == "crop_health_drop"
    assert "20.0% drop" in alert_med.headline

    # Case B: Current NDVI is 0.35 -> (0.50 - 0.35) / 0.50 = 30% drop -> HIGH severity
    alert_high, gap_high = evaluate_crop_health_drop(
        plot_code="PLOT_TEST_01",
        season="2023-24",
        checkpoint_label="Dec 15",
        detected_on=date(2023, 12, 15),
        current_ndvi=0.35,
        prior_ndvis_same_checkpoint=prior_ndvis,
        clear_obs_count=3,
    )
    assert gap_high is None
    assert alert_high is not None
    assert alert_high.severity == "high"

    # Case C: Current NDVI is 0.46 -> 8% drop (< 15%) -> No alert
    alert_none, gap_none = evaluate_crop_health_drop(
        plot_code="PLOT_TEST_01",
        season="2023-24",
        checkpoint_label="Dec 15",
        detected_on=date(2023, 12, 15),
        current_ndvi=0.46,
        prior_ndvis_same_checkpoint=prior_ndvis,
        clear_obs_count=3,
    )
    assert gap_none is None
    assert alert_none is None


def test_crop_health_data_gap_when_insufficient_clear_obs_or_prior_seasons() -> None:
    """Without enough data, record data_gap status; never raise an alert or guess."""
    # Case 1: Insufficient clear observations in current season (< 2)
    alert, gap_reason = evaluate_crop_health_drop(
        plot_code="PLOT_TEST_01",
        season="2023-24",
        checkpoint_label="Dec 15",
        detected_on=date(2023, 12, 15),
        current_ndvi=0.30,
        prior_ndvis_same_checkpoint=[0.50, 0.52],
        clear_obs_count=1,
    )
    assert alert is None
    assert gap_reason is not None
    assert "Insufficient clear observations" in gap_reason

    # Case 2: Insufficient prior seasons history (< 1)
    alert2, gap_reason2 = evaluate_crop_health_drop(
        plot_code="PLOT_TEST_01",
        season="2020-21",
        checkpoint_label="Dec 15",
        detected_on=date(2020, 12, 15),
        current_ndvi=0.30,
        prior_ndvis_same_checkpoint=[],
        clear_obs_count=3,
    )
    assert alert2 is None
    assert gap_reason2 is not None
    assert "Insufficient prior seasons history" in gap_reason2


# ---------------------------------------------------------------------------
# 2. Rainfall Deficit Rule Tests
# ---------------------------------------------------------------------------


def test_rainfall_deficit_irrigated_capped_at_medium() -> None:
    """Rabi wheat is irrigated; severe rainfall deficit is capped at medium for irrigated plots."""
    # Irrigated plot with -60% rainfall deficit
    alert_irrigated = evaluate_rainfall_deficit(
        plot_code="PLOT_TEST_01",
        season="2023-24",
        checkpoint_label="Jan 15",
        detected_on=date(2024, 1, 15),
        rain_deficit_pct=-60.0,
        irrigation="tube_well",
    )
    assert alert_irrigated is not None
    assert alert_irrigated.severity == "medium"
    assert "capped at medium severity because assured irrigation" in alert_irrigated.detail

    # Rainfed plot with -60% rainfall deficit can trigger high severity
    alert_rainfed = evaluate_rainfall_deficit(
        plot_code="PLOT_TEST_02",
        season="2023-24",
        checkpoint_label="Jan 15",
        detected_on=date(2024, 1, 15),
        rain_deficit_pct=-60.0,
        irrigation="rainfed",
    )
    assert alert_rainfed is not None
    assert alert_rainfed.severity == "high"


# ---------------------------------------------------------------------------
# 3. Mandi Price Crash Rule Tests
# ---------------------------------------------------------------------------


def test_price_crash_district_level_baseline() -> None:
    """Mandi price drop compares district modal price vs historical monthly baseline."""
    # Prior Decembers mean: ₹2400
    prior_dec_prices = [2350.0, 2450.0]

    # Current price: ₹1900 -> (2400 - 1900) / 2400 = 20.8% drop -> Alert
    alert = evaluate_price_crash(
        plot_code="PLOT_TEST_01",
        season="2023-24",
        checkpoint_label="Dec 15",
        detected_on=date(2023, 12, 15),
        current_district_price=1900.0,
        prior_seasons_district_prices=prior_dec_prices,
    )
    assert alert is not None
    assert alert.type == "price_crash"
    assert "District APMC mandi price decline" in alert.headline
    assert "20.8% decline" in alert.detail

    # Drop < 15%: ₹2200 -> (2400 - 2200) / 2400 = 8.3% drop -> No alert
    no_alert = evaluate_price_crash(
        plot_code="PLOT_TEST_01",
        season="2023-24",
        checkpoint_label="Dec 15",
        detected_on=date(2023, 12, 15),
        current_district_price=2200.0,
        prior_seasons_district_prices=prior_dec_prices,
    )
    assert no_alert is None


# ---------------------------------------------------------------------------
# 4. De-duplication and Severity Escalation Tests
# ---------------------------------------------------------------------------


def test_in_season_tracker_deduplication_and_escalation() -> None:
    """The same alert type is raised once; subsequent checkpoints escalate or resolve."""
    tracker = InSeasonAlertTracker(plot_code="PLOT_TEST_01", season="2023-24")

    # Checkpoint 1 (Dec 15): Medium severity crop health drop
    alert_cp1 = AlertItem(
        type="crop_health_drop",
        severity="medium",
        status="open",
        detected_on=date(2023, 12, 15),
        checkpoint_label="Dec 15",
        plot_code="PLOT_TEST_01",
        season="2023-24",
        headline="NDVI drop 18%",
        detail="Detail 1",
        supportive_action="Action 1",
    )
    active1 = tracker.update_with_checkpoint_alerts([alert_cp1])
    assert len(active1) == 1
    assert active1[0].severity == "medium"
    assert active1[0].detected_on == date(2023, 12, 15)

    # Checkpoint 2 (Jan 15): Condition worsens to High severity
    alert_cp2 = AlertItem(
        type="crop_health_drop",
        severity="high",
        status="open",
        detected_on=date(2024, 1, 15),
        checkpoint_label="Jan 15",
        plot_code="PLOT_TEST_01",
        season="2023-24",
        headline="NDVI drop 28%",
        detail="Detail 2",
        supportive_action="Action 2",
    )
    active2 = tracker.update_with_checkpoint_alerts([alert_cp2])
    # MUST NOT create a duplicate alert
    assert len(active2) == 1
    assert active2[0].severity == "high"
    # Preserves initial detection date
    assert active2[0].detected_on == date(2023, 12, 15)
    assert "Escalated" in active2[0].headline

    # Checkpoint 3 (Jan 31): Field conditions normalize (no alerts in new_alerts)
    active3 = tracker.update_with_checkpoint_alerts([])
    assert len(active3) == 0  # No longer active
    assert len(tracker._history) == 1
    assert tracker._history[0].status == "resolved"


# ---------------------------------------------------------------------------
# 5. Leakage / Truncation Invariance Test
# ---------------------------------------------------------------------------


def test_replay_leakage_truncation_invariance() -> None:
    """Replaying on a dataset truncated at the checkpoint produces identical alerts."""
    # Build a self-contained 2-season test dataset (independent of local disk cache)
    df = pd.DataFrame(
        [
            {
                "plot_code": "PLOT_LEAK_01",
                "season": "2022-23",
                "irrigation": "tube_well",
                "rain_nov_mm": 5.0,
                "rain_dec_mm": 10.0,
                "rain_jan_mm": 8.0,
                "price_dec": 2200.0,
                "price_jan": 2250.0,
            },
            {
                "plot_code": "PLOT_LEAK_01",
                "season": "2023-24",
                "irrigation": "tube_well",
                "rain_nov_mm": 0.0,
                "rain_dec_mm": 0.0,
                "rain_jan_mm": 50.0,  # post-Dec high rain
                "price_dec": 1600.0,  # price crash in Dec
                "price_jan": 2400.0,  # post-Dec high price
            },
        ]
    )

    # Full replay on untruncated dataset
    res_full = replay_single_plot_season(
        plot_code="PLOT_LEAK_01",
        season="2023-24",
        plot_df=df,
        full_df=df,
        raw_satellite_dir=None,
    )
    cp_dec15_full = [r for r in res_full if r.checkpoint_label == "Dec 15"][0]

    # Truncated dataset removing subsequent months' weather and price data
    df_truncated = df.copy()
    mask = (df_truncated["plot_code"] == "PLOT_LEAK_01") & (df_truncated["season"] == "2023-24")
    df_truncated.loc[mask, "rain_jan_mm"] = None
    df_truncated.loc[mask, "price_jan"] = None

    res_truncated = replay_single_plot_season(
        plot_code="PLOT_LEAK_01",
        season="2023-24",
        plot_df=df_truncated,
        full_df=df_truncated,
        raw_satellite_dir=None,
    )
    cp_dec15_truncated = [r for r in res_truncated if r.checkpoint_label == "Dec 15"][0]

    # Alerts emitted at Dec 15 must be identical regardless of post-Dec data
    assert len(cp_dec15_full.alerts) == len(cp_dec15_truncated.alerts)
    for a_full, a_trunc in zip(cp_dec15_full.alerts, cp_dec15_truncated.alerts, strict=True):
        assert a_full.type == a_trunc.type
        assert a_full.severity == a_trunc.severity
        assert a_full.headline == a_trunc.headline


# ---------------------------------------------------------------------------
# 6. TC-007 Synthetic Stress Scenario Test
# ---------------------------------------------------------------------------


def test_tc007_synthetic_stress_scenario() -> None:
    """TC-007 passes strictly on the labelled synthetic stress scenario."""
    synth_result = generate_synthetic_stress_scenario(
        plot_code="ANAND_WHEAT_01",
        base_season="2023-24",
        raw_satellite_dir=Path("data/raw/satellite")
        if Path("data/raw/satellite").is_dir()
        else None,
    )

    assert synth_result["scenario_type"] == "SYNTHETIC_STRESS_SCENARIO"
    assert synth_result["tc007_passed"] is True
    # Lead time must be >= 6 weeks prior to April 1 harvest
    assert synth_result["lead_time_weeks"] >= 6.0
    assert synth_result["alerts_count"] >= 1

    # Verify scenario is clearly marked in checkpoint results
    has_alert = False
    for r in synth_result["checkpoint_results"]:
        for a in r.alerts:
            has_alert = True
            assert a.type in ALLOWED_ALERT_TYPES
            assert a.severity in ALLOWED_SEVERITIES
    assert has_alert


# ---------------------------------------------------------------------------
# 7. Alert ORM Compatibility Test
# ---------------------------------------------------------------------------


def test_alert_orm_compatibility() -> None:
    """AlertItem fields and constraints match satbhoomi.db.models.alert.Alert."""
    item = AlertItem(
        type="crop_health_drop",
        severity="medium",
        status="open",
        detected_on=date(2023, 12, 15),
        checkpoint_label="Dec 15",
        plot_code="ANAND_WHEAT_01",
        season="2023-24",
        headline="Vegetative vigor decline",
        detail="Plot NDVI dropped 20% below historical baseline.",
        supportive_action="Schedule supportive visit to inspect soil moisture.",
    )

    # Instantiate SQLAlchemy Alert model to test compatibility
    detected_dt = datetime.combine(item.detected_on, datetime.min.time(), tzinfo=UTC)
    orm_alert = Alert(
        plot_id=1,
        type=item.type,
        severity=item.severity,
        status=item.status,
        detected_on=detected_dt,
    )

    assert orm_alert.type == "crop_health_drop"
    assert orm_alert.severity in ALLOWED_SEVERITIES
    assert orm_alert.status in ALLOWED_STATUSES


# ---------------------------------------------------------------------------
# 8. Rule 2 Compliance & Supportive Officer Action Tests
# ---------------------------------------------------------------------------


def test_rule_2_compliance_no_banned_wording_supportive_actions() -> None:
    """Alerts describe farm and repayment stress, never mental state or farmer blame."""
    dataset_path = Path("data/processed/season_dataset.csv")
    if dataset_path.is_file() and Path("data/raw/satellite").is_dir():
        df = pd.read_csv(dataset_path)
        report = run_full_replay(df, raw_satellite_dir=Path("data/raw/satellite"))
        assert report.total_plots > 0

    # Also check synthetic scenario alerts (always executes in all environments including CI)
    raw_dir = Path("data/raw/satellite") if Path("data/raw/satellite").is_dir() else None
    synth_res = generate_synthetic_stress_scenario(raw_satellite_dir=raw_dir)

    all_checkpoint_results = synth_res["checkpoint_results"]
    for res in all_checkpoint_results:
        for alert in res.alerts:
            # Check text fields
            full_text = f"{alert.headline} {alert.detail} {alert.supportive_action}".lower()

            # Rule 2: Zero banned words
            for banned in BANNED_MENTAL_OR_BLAME_WORDS:
                assert banned not in full_text, (
                    f"Violation: Banned word {banned!r} found in alert: {full_text}"
                )

            # Supportive framing checks
            assert "support" in full_text or "assistance" in full_text, (
                f"Alert must provide supportive framing: {full_text}"
            )
