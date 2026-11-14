"""Unit test for recompute_scores.py and generated summary artifacts (Stage B)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_recompute_scores_artifact_integrity() -> None:
    """Verify that reports/scores_summary.json exists and satisfies schema constraints."""
    summary_path = Path("reports/scores_summary.json")
    if not summary_path.is_file():
        pytest.skip("reports/scores_summary.json not present on clean runner.")

    with open(summary_path, encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    assert meta["model_version"] == "satbhoomi-rules-v2.0-relative-20261114"
    assert meta["total_active_plots"] == 21
    assert meta["total_plot_seasons"] == 105

    totals = data["overall_band_totals"]
    assert totals["insufficient_data"] == 21
    assert totals["low"] == 73
    assert totals["medium"] == 9
    assert totals["high"] == 2
    assert totals["total_evaluable_plot_seasons"] == 84

    # Flag persistence
    persistence = data["plot_flag_persistence"]
    assert persistence["flagged_4_seasons"] == 0
    assert persistence["flagged_3_seasons"] == 0
    assert persistence["flagged_0_seasons"] == 11

    # Loan suggestions
    loan_ex = data["sample_loan_suggestions"]
    assert loan_ex["low_risk_example"]["status"] == "ok"
    assert loan_ex["insufficient_data_season1_example"]["status"] == "manual_appraisal_required"


def test_replay_alerts_artifact_integrity() -> None:
    """Verify that reports/replay_alerts.json exists and TC-007 passed."""
    replay_path = Path("reports/replay_alerts.json")
    if not replay_path.is_file():
        pytest.skip("reports/replay_alerts.json not present on clean runner.")

    with open(replay_path, encoding="utf-8") as f:
        data = json.load(f)

    meta = data["metadata"]
    assert meta["total_plots"] == 21
    assert meta["tc007_passed"] is True

    synth = data["tc007_synthetic_stress_scenario"]
    assert synth["tc007_passed"] is True
    assert synth["lead_time_weeks"] >= 6.0
