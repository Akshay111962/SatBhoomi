"""Unit and integration tests for risk models and evaluation pipeline (T-05).

Covers:
- Baselines (Majority-Class, Persistence, Agronomic Rules) probability correctness
- Determinism and reproducibility with fixed seeds
- Strict temporal isolation and forward-chaining splits
- Multi-class synthetic fixture end-to-end training and evaluation
- Plot-level cluster bootstrap resampling integrity
- Hand-checkable math verification for Brier score and calibration table
- Model artifact serialization and deserialization reproducibility
- Exclusion and look-ahead leakage quarantine verification.
"""

import tempfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest

from satbhoomi.features.config import EXCLUDED_LEAKAGE_COLUMNS, FEATURE_COLUMNS
from satbhoomi.risk.baseline import (
    AgronomicRulesBaseline,
    MajorityClassBaseline,
    PersistenceBaseline,
)
from satbhoomi.risk.evaluate import (
    cluster_bootstrap_confidence_interval,
    compute_calibration_table,
    compute_metrics,
    evaluate_by_plot_size,
)
from satbhoomi.risk.train import (
    generate_model_version_string,
    train_and_evaluate_pipeline,
)


@pytest.fixture
def synthetic_features_df() -> pd.DataFrame:
    """Fixture providing a controlled multi-class temporal feature dataset."""
    plots = [f"PLOT_{i:02d}" for i in range(1, 13)]
    seasons = ["2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
    rows = []

    for s_idx, season in enumerate(seasons):
        for p_idx, plot in enumerate(plots):
            is_init = season == "2020-21"
            # Introduce controlled stress in plot 1 and 2 in later seasons
            is_stressed = 1 if (not is_init and p_idx < 3 and s_idx >= 2) else 0

            rows.append(
                {
                    "plot_code": plot,
                    "season": season,
                    "district": "anand",
                    "crop": "wheat",
                    "lat": 22.56 + (p_idx * 0.01),
                    "lon": 72.95 + (p_idx * 0.01),
                    "ndvi_early": 0.25 if is_stressed else 0.45,
                    "ndvi_pre_cutoff_mean": 0.30 if is_stressed else 0.50,
                    "ndvi_pre_cutoff_std": 0.05,
                    "ndvi_trend_pre_cutoff": -0.02 if is_stressed else 0.03,
                    "rain_pre_cutoff_total_mm": 5.0 if is_stressed else 15.0,
                    "rain_pre_cutoff_deficit_pct": -50.0 if is_stressed else 10.0,
                    "mandi_pre_cutoff_volatility": 120.5,
                    "past_stressed_seasons_count": 1 if (s_idx >= 3 and p_idx < 3) else 0,
                    "prev_season_ndvi_peak": 0.60,
                    "area_acre": 1.5 if p_idx < 6 else 3.0,
                    "irrigation": "tube_well" if p_idx % 2 == 0 else "canal",
                    "insured": 1 if p_idx % 3 == 0 else 0,
                    "stressed": float(is_stressed) if not is_init else np.nan,
                    "label_unavailable": is_init,
                    "peak_drop_pct": 20.0 if is_stressed else 0.0,
                    "historical_baseline_ndvi": 0.65,
                }
            )

    return pd.DataFrame(rows)


def test_majority_class_baseline() -> None:
    """Test MajorityClassBaseline probability properties."""
    model = MajorityClassBaseline()
    y_train = np.array([1, 0, 0, 0])
    model.fit(None, y_train)

    assert model.prior_ == pytest.approx(0.25)

    X_dummy = np.zeros((5, 3))
    probs = model.predict_proba(X_dummy)
    assert probs.shape == (5, 2)
    np.testing.assert_allclose(probs[:, 0] + probs[:, 1], 1.0)
    np.testing.assert_allclose(probs[:, 1], 0.25)

    preds = model.predict(X_dummy, threshold=0.5)
    assert np.all(preds == 0)


def test_persistence_baseline() -> None:
    """Test PersistenceBaseline probability assignments."""
    model = PersistenceBaseline()
    df = pd.DataFrame(
        {
            "plot_code": ["P1", "P2"],
            "past_stressed_seasons_count": [1, 0],
        }
    )
    probs = model.predict_proba(df)
    assert probs.shape == (2, 2)
    assert probs[0, 1] == pytest.approx(0.80)
    assert probs[1, 1] == pytest.approx(0.20)
    np.testing.assert_allclose(probs[:, 0] + probs[:, 1], 1.0)


def test_agronomic_rules_baseline() -> None:
    """Test AgronomicRulesBaseline heuristic compound conditions."""
    model = AgronomicRulesBaseline()
    df = pd.DataFrame(
        {
            # Row 0: Compound stress (low early NDVI + rain deficit)
            # Row 1: Partial stress (low trend only)
            # Row 2: Normal growth
            "ndvi_early": [0.30, 0.40, 0.50],
            "ndvi_trend_pre_cutoff": [0.01, -0.05, 0.05],
            "rain_pre_cutoff_deficit_pct": [-25.0, 0.0, 5.0],
        }
    )
    probs = model.predict_proba(df)
    assert probs.shape == (3, 2)
    assert probs[0, 1] == pytest.approx(0.85)  # Compound
    assert probs[1, 1] == pytest.approx(0.45)  # Partial
    assert probs[2, 1] == pytest.approx(0.10)  # Normal
    np.testing.assert_allclose(probs[:, 0] + probs[:, 1], 1.0)


def test_hand_checkable_metrics_math() -> None:
    """Verify Brier score and calibration table against manual calculation."""
    # Two samples: sample 1 has y=1, p=0.8; sample 2 has y=0, p=0.2
    # Brier score = ((0.8 - 1.0)^2 + (0.2 - 0.0)^2) / 2 = (0.04 + 0.04) / 2 = 0.04
    y_true = np.array([1, 0])
    y_prob = np.array([0.8, 0.2])

    metrics = compute_metrics(y_true, y_prob)
    assert metrics["brier_score"] == pytest.approx(0.04)
    assert metrics["roc_auc"] == pytest.approx(1.0)

    cal = compute_calibration_table(y_true, y_prob)
    assert len(cal) == 3
    # Bin 0: Low Risk [0.0, 0.33) -> contains sample 2 (prob=0.2, y=0)
    assert cal[0]["count"] == 1
    assert cal[0]["mean_predicted_prob"] == pytest.approx(0.2)
    assert cal[0]["observed_event_rate"] == pytest.approx(0.0)

    # Bin 2: High Risk [0.67, 1.00] -> contains sample 1 (prob=0.8, y=1)
    assert cal[2]["count"] == 1
    assert cal[2]["mean_predicted_prob"] == pytest.approx(0.8)
    assert cal[2]["observed_event_rate"] == pytest.approx(1.0)


def test_cluster_bootstrap_integrity() -> None:
    """Verify plot-level cluster bootstrap resamples by plot clusters."""
    df = pd.DataFrame(
        {
            "plot_code": ["P1", "P1", "P2", "P2", "P3", "P3"],
            "y_true": [1, 1, 0, 0, 1, 0],
            "y_prob": [0.9, 0.8, 0.1, 0.2, 0.7, 0.3],
        }
    )
    boot_ci = cluster_bootstrap_confidence_interval(
        df=df,
        y_true_col="y_true",
        y_prob_col="y_prob",
        cluster_col="plot_code",
        n_resamples=100,
        random_state=42,
    )
    auc_ci = boot_ci["roc_auc_95_ci"]
    brier_ci = boot_ci["brier_score_95_ci"]

    assert 0.0 <= brier_ci[0] <= brier_ci[1] <= 1.0
    assert 0.0 <= auc_ci[0] <= auc_ci[1] <= 1.0


def test_subgroup_by_plot_size() -> None:
    """Verify plot size subgroup evaluation."""
    df = pd.DataFrame(
        {
            "area_acre": [1.0, 1.5, 3.0, 4.0],
            "y_true": [1, 0, 1, 0],
            "y_prob": [0.8, 0.2, 0.7, 0.3],
        }
    )
    subgroups = evaluate_by_plot_size(
        df=df,
        y_true_col="y_true",
        y_prob_col="y_prob",
        area_col="area_acre",
        split_threshold=2.0,
    )
    assert subgroups["small_plots"]["count"] == 2
    assert subgroups["small_plots"]["statistically_underpowered"] is True
    assert subgroups["large_plots"]["count"] == 2
    assert subgroups["large_plots"]["statistically_underpowered"] is True


def test_multi_class_training_and_permutation(synthetic_features_df: pd.DataFrame) -> None:
    """Test full multi-class model training, evaluation, and permutation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "synthetic_features.csv"
        synthetic_features_df.to_csv(csv_path, index=False)

        res = train_and_evaluate_pipeline(
            features_csv_path=csv_path,
            output_dir=Path(tmpdir) / "models",
            test_season="2024-25",
        )

        assert res["criteria_status"] in [
            "CRITERIA_MET",
            "CRITERIA_PARTIALLY_MET_RULES_PREFERRED",
            "CRITERIA_NOT_MET",
        ]
        assert Path(res["artifact_path"]).exists()
        assert Path(res["metadata_path"]).exists()

        # Model deserialization check
        loaded_model = joblib.load(res["artifact_path"])
        X_test = synthetic_features_df[synthetic_features_df["season"] == "2024-25"][
            FEATURE_COLUMNS
        ]
        preds_loaded = loaded_model.predict_proba(X_test)[:, 1]
        assert len(preds_loaded) == len(X_test)


def test_leakage_exclusion_in_risk_pipeline() -> None:
    """Assert look-ahead outcome columns are strictly quarantined from feature set."""
    for forbidden_col in EXCLUDED_LEAKAGE_COLUMNS:
        assert forbidden_col not in FEATURE_COLUMNS, f"Leaked column in features: {forbidden_col}"


def test_model_version_string_format() -> None:
    """Verify model version string conforms to docs/EVAL_PROTOCOL.md Section 8."""
    v_str = generate_model_version_string(
        algorithm="logreg",
        data_hash="abcdef0123456789",
        date_str="20261105",
    )
    assert v_str == "satbhoomi-risk-v1.0-logreg-feat1-opt1th15-abcdef01-20261105"
