"""Unit tests for What-If simulator engine (T-08, FR-007)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from satbhoomi.db.models.what_if import WhatIf
from satbhoomi.risk.what_if import (
    DISCLAIMER_WHAT_IF,
    simulate_what_if,
)
from scripts.score_plot import main as score_cli_main


@pytest.fixture
def sample_feature_row() -> dict:
    """Standard sample feature row for a Gujarat wheat plot."""
    return {
        "plot_code": "ANAND_TEST_01",
        "season": "2024-25",
        "crop": "wheat",
        "district": "Anand",
        "irrigation": "rainfed",
        "insured": 0,
        "ndvi_early": 0.40,
        "ndvi_pre_cutoff_mean": 0.48,
        "ndvi_pre_cutoff_std": 0.05,
        "ndvi_trend_pre_cutoff": 0.008,
        "rain_pre_cutoff_total_mm": 4.0,
        "rain_pre_cutoff_deficit_pct": -45.0,  # Below -20% threshold triggers rule
        "mandi_pre_cutoff_volatility": 0.045,
        "past_stressed_seasons_count": 0,
        "prev_season_ndvi_peak": 0.60,
        "area_acre": 3.0,
    }


def test_what_if_enrolling_insurance(sample_feature_row: dict) -> None:
    """Enrolling in PMFBY insurance reduces credit risk score and updates limit."""
    res = simulate_what_if(
        sample_feature_row,
        changed_input="insured",
        new_value=1,
        area_acre=3.0,
        crop="wheat",
    )

    assert res.status == "ok"
    assert res.changed_input == "insured"
    assert res.old_value == "0"
    assert res.new_value == "1"

    # Rule 6 mandatory estimate label
    assert res.estimate_label == "estimate"
    assert res.disclaimer == DISCLAIMER_WHAT_IF

    # Old score: rain deficit (-45%) triggered partial stress (p=0.45 -> score=45)
    assert res.old_score == 45
    assert res.old_band == "medium"

    # New score: 10-point protective reduction for insurance -> score=35
    assert res.new_score == 35
    assert res.score_delta == -10

    # Old vs new limits
    assert res.old_limit_band is not None
    assert res.new_limit_band is not None
    assert "PMFBY crop insurance" in res.rationale


def test_what_if_upgrading_irrigation(sample_feature_row: dict) -> None:
    """Upgrading from rainfed to tube_well buffers deficit and increases SoF."""
    res = simulate_what_if(
        sample_feature_row,
        changed_input="irrigation",
        new_value="tube_well",
        area_acre=2.0,
    )

    assert res.status == "ok"
    assert res.changed_input == "irrigation"
    assert res.old_value == "rainfed"
    assert res.new_value == "tube_well"

    # Rainfed SoF: ₹22,000 -> Irrigated SoF: ₹32,000
    assert res.old_limit_band is not None
    assert res.new_limit_band is not None
    assert res.old_limit_band.scale_of_finance_per_acre_inr == 22_000
    assert res.new_limit_band.scale_of_finance_per_acre_inr == 32_000

    # Moisture deficit is buffered, resolving rule stress
    assert res.new_score <= res.old_score
    assert "assured tube_well irrigation" in res.rationale


def test_what_if_supplementary_irrigation(sample_feature_row: dict) -> None:
    """Applying protective irrigation eliminates winter moisture deficit."""
    res = simulate_what_if(
        sample_feature_row,
        changed_input="supplementary_irrigation",
        new_value="applied",
    )

    assert res.status == "ok"
    assert res.changed_input == "supplementary_irrigation"
    assert "45.0% deficit" in res.old_value
    assert res.new_value == "applied"
    assert res.score_delta < 0  # Risk decreased
    assert "buffers moisture deficit" in res.rationale


def test_what_if_disallowed_input_rejected(sample_feature_row: dict) -> None:
    """Attempting to change non-controllable historical data is strictly rejected."""
    with pytest.raises(ValueError, match="Invalid controllable input 'ndvi_early'"):
        simulate_what_if(sample_feature_row, changed_input="ndvi_early", new_value=0.65)

    with pytest.raises(ValueError, match="Invalid controllable input 'rain_pre_cutoff_total_mm'"):
        simulate_what_if(
            sample_feature_row, changed_input="rain_pre_cutoff_total_mm", new_value=100.0
        )


def test_what_if_invalid_irrigation_value_rejected(sample_feature_row: dict) -> None:
    """Passing an ungrounded irrigation type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid irrigation value 'hydroponic_experimental'"):
        simulate_what_if(
            sample_feature_row,
            changed_input="irrigation",
            new_value="hydroponic_experimental",
        )


def test_what_if_insufficient_data_baseline_raises() -> None:
    """Plots with insufficient core data cannot run simulations."""
    row = {
        "plot_code": "BAD_PLOT",
        "season": "2024-25",
        "area_acre": 2.0,
    }
    with pytest.raises(
        ValueError,
        match="Cannot run what-if simulation: baseline plot-season has insufficient data",
    ):
        simulate_what_if(row, changed_input="insured", new_value=1)


def test_what_if_orm_model_compatibility(sample_feature_row: dict) -> None:
    """Verify WhatIfResult fields map directly to the SQLAlchemy WhatIf ORM model."""
    res = simulate_what_if(
        sample_feature_row,
        changed_input="insured",
        new_value=1,
        assessment_id=42,
    )

    # Instantiate ORM model from result fields
    orm_record = WhatIf(
        assessment_id=res.assessment_id,
        changed_input=res.changed_input,
        old_value=res.old_value,
        new_value=res.new_value,
        new_score=float(res.new_score),
    )

    assert orm_record.assessment_id == 42
    assert orm_record.changed_input == "insured"
    assert orm_record.old_value == "0"
    assert orm_record.new_value == "1"
    assert 0 <= orm_record.new_score <= 100


def test_score_plot_cli_what_if_options(
    tmp_path: Path, sample_feature_row: dict, monkeypatch
) -> None:
    """CLI prints valid WhatIfResult JSON when --what-if-input and --what-if-val are given."""
    csv_path = tmp_path / "features.csv"
    pd.DataFrame([sample_feature_row]).to_csv(csv_path, index=False)

    import io

    stdout_capture = io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout_capture)

    exit_code = score_cli_main(
        [
            "--plot",
            sample_feature_row["plot_code"],
            "--season",
            sample_feature_row["season"],
            "--features-csv",
            str(csv_path),
            "--what-if-input",
            "insured",
            "--what-if-val",
            "1",
        ]
    )

    assert exit_code == 0
    parsed = json.loads(stdout_capture.getvalue())
    assert parsed["status"] == "ok"
    assert parsed["changed_input"] == "insured"
    assert parsed["estimate_label"] == "estimate"
    assert parsed["disclaimer"] == DISCLAIMER_WHAT_IF
