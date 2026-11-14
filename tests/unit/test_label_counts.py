"""Unit test for label_counts analysis script and feasibility gate logic."""

from pathlib import Path

from scripts.analysis.label_counts import generate_label_counts


def test_generate_label_counts_determinism(tmp_path: Path) -> None:
    """Verify that generate_label_counts produces consistent and valid structure."""
    features_csv = Path("data/processed/features.csv")
    plots_csv = Path("data/synthetic/sample_plots.csv")
    season_csv = Path("data/processed/season_dataset.csv")

    out1 = tmp_path / "counts1.json"
    out2 = tmp_path / "counts2.json"

    res1 = generate_label_counts(features_csv, plots_csv, season_csv, out1)
    res2 = generate_label_counts(features_csv, plots_csv, season_csv, out2)

    # Exclude dynamic timestamp before comparison
    del res1["metadata"]["generated_at_utc"]
    del res2["metadata"]["generated_at_utc"]

    assert res1 == res2

    # Structural assertions
    assert "label_counts" in res1
    assert "feasibility_gate" in res1
    assert "rules_baseline_descriptive_on_stressed" in res1
    assert "robustness" in res1

    # Exact data assertions
    counts = res1["label_counts"]
    assert counts["active_plots_count"] == 21
    assert counts["total_labelled_rows"] == 84
    assert counts["total_stressed_count"] == 4
    assert counts["total_normal_count"] == 80
    assert counts["overall_stressed_rate_pct"] == 4.76

    # Feasibility gate assertions
    gate = res1["feasibility_gate"]
    assert gate["status"] == "NOT EVALUABLE"
    assert gate["gate_passed"] is False
    assert gate["ml_action"] == "FREEZE_ML_TRAINING"
    assert gate["active_scorer"] == "AgronomicRulesBaseline"

    # Rules baseline assertions
    rules = res1["rules_baseline_descriptive_on_stressed"]
    assert rules["disclaimer"] == "n = 4, descriptive only, no inference"
    assert len(rules["rows"]) == 4
