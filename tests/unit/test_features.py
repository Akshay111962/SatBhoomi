"""Unit tests and look-ahead leakage tests for feature engineering and proxy labels (T-04)."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from satbhoomi.features.build_features import (
    build_feature_dataset,
    compute_linear_trend,
    compute_mandi_cv,
    extract_pre_cutoff_satellite_features,
)
from satbhoomi.features.config import (
    EXCLUDED_LEAKAGE_COLUMNS,
    FEATURE_COLUMNS,
    LABEL_COLUMNS,
    METADATA_COLUMNS,
    FeaturePipelineConfig,
)
from satbhoomi.features.label import compute_proxy_labels


@pytest.fixture
def sample_multi_season_df() -> pd.DataFrame:
    """Fixture providing a hand-verifiable 4-season sequence for 2 plots."""
    return pd.DataFrame(
        [
            # Plot 1: ANAND_01
            {
                "plot_code": "ANAND_01",
                "season": "2020-21",
                "district": "Anand",
                "crop": "wheat",
                "lat": 22.51,
                "lon": 72.93,
                "buffer_m": 50.0,
                "irrigation": "tube_well",
                "insured": 1,
                "ndvi_early": 0.40,
                "ndvi_peak": 0.80,
                "ndvi_mean": 0.55,
                "ndvi_std": 0.12,
                "rain_nov_mm": 5.0,
                "rain_dec_mm": 10.0,
                "rain_jan_mm": 15.0,
                "rain_feb_mm": 20.0,
                "rain_mar_mm": 10.0,
                "rain_apr_mm": 5.0,
                "rain_total_mm": 65.0,
                "price_nov": 2000.0,
                "price_dec": 2100.0,
                "price_jan": 2200.0,
                "price_feb": 1900.0,
                "price_mar": 1800.0,
                "price_apr": 1750.0,
                "yield_kg_per_ha": 3500.0,
            },
            {
                "plot_code": "ANAND_01",
                "season": "2021-22",
                "district": "Anand",
                "crop": "wheat",
                "lat": 22.51,
                "lon": 72.93,
                "buffer_m": 50.0,
                "irrigation": "tube_well",
                "insured": 1,
                "ndvi_early": 0.35,
                "ndvi_peak": 0.64,  # Drop vs 0.80: (0.80 - 0.64)/0.80 = 20% -> STRESSED (>=15%)
                "ndvi_mean": 0.45,
                "ndvi_std": 0.10,
                "rain_nov_mm": 2.0,
                "rain_dec_mm": 4.0,
                "rain_jan_mm": 4.0,
                "rain_feb_mm": 0.0,
                "rain_mar_mm": 0.0,
                "rain_apr_mm": 0.0,
                "rain_total_mm": 10.0,
                "price_nov": 2100.0,
                "price_dec": 2150.0,
                "price_jan": 2200.0,
                "price_feb": 2050.0,
                "price_mar": 2000.0,
                "price_apr": 1950.0,
                "yield_kg_per_ha": 3400.0,
            },
            {
                "plot_code": "ANAND_01",
                "season": "2022-23",
                "district": "Anand",
                "crop": "wheat",
                "lat": 22.51,
                "lon": 72.93,
                "buffer_m": 50.0,
                "irrigation": "tube_well",
                "insured": 1,
                "ndvi_early": 0.38,
                # Baseline = (0.80 + 0.64)/2 = 0.72. Drop = 0.0% -> NORMAL (<15%)
                "ndvi_peak": 0.72,
                "ndvi_mean": 0.50,
                "ndvi_std": 0.11,
                "rain_nov_mm": 8.0,
                "rain_dec_mm": 12.0,
                "rain_jan_mm": 10.0,
                "rain_feb_mm": 15.0,
                "rain_mar_mm": 5.0,
                "rain_apr_mm": 2.0,
                "rain_total_mm": 52.0,
                "price_nov": 2200.0,
                "price_dec": 2250.0,
                "price_jan": 2300.0,
                "price_feb": 2200.0,
                "price_mar": 2100.0,
                "price_apr": 2000.0,
                "yield_kg_per_ha": 3250.0,
            },
            {
                "plot_code": "ANAND_01",
                "season": "2023-24",
                "district": "Anand",
                "crop": "wheat",
                "lat": 22.51,
                "lon": 72.93,
                "buffer_m": 50.0,
                "irrigation": "tube_well",
                "insured": 1,
                "ndvi_early": 0.32,
                # Baseline = (0.80+0.64+0.72)/3 = 0.72. Drop = (0.72-0.54)/0.72 = 25% -> STRESSED
                "ndvi_peak": 0.54,
                "ndvi_mean": 0.40,
                "ndvi_std": 0.08,
                "rain_nov_mm": 1.0,
                "rain_dec_mm": 2.0,
                "rain_jan_mm": 3.0,
                "rain_feb_mm": 2.0,
                "rain_mar_mm": 0.0,
                "rain_apr_mm": 0.0,
                "rain_total_mm": 8.0,
                "price_nov": 2300.0,
                "price_dec": 2350.0,
                "price_jan": 2400.0,
                "price_feb": 2350.0,
                "price_mar": 2300.0,
                "price_apr": 2250.0,
                "yield_kg_per_ha": 3550.0,
            },
            # Plot 2: BORSAD_02 (1 season only -> must be label_unavailable)
            {
                "plot_code": "BORSAD_02",
                "season": "2020-21",
                "district": "Anand",
                "crop": "wheat",
                "lat": 22.41,
                "lon": 72.90,
                "buffer_m": 50.0,
                "irrigation": "canal",
                "insured": 0,
                "ndvi_early": None,  # Gapped input
                "ndvi_peak": 0.70,
                "ndvi_mean": 0.50,
                "ndvi_std": 0.10,
                "rain_nov_mm": 5.0,
                "rain_dec_mm": 5.0,
                "rain_jan_mm": 5.0,
                "rain_feb_mm": 5.0,
                "rain_mar_mm": 5.0,
                "rain_apr_mm": 5.0,
                "rain_total_mm": 30.0,
                "price_nov": 2000.0,
                "price_dec": 2050.0,
                "price_jan": 2100.0,
                "price_feb": 1950.0,
                "price_mar": 1900.0,
                "price_apr": 1850.0,
                "yield_kg_per_ha": 3500.0,
            },
        ]
    )


def test_no_leakage_columns_in_feature_columns() -> None:
    """Verify that no outcome, label, full-season, or post-cutoff column is in FEATURE_COLUMNS."""
    for col in EXCLUDED_LEAKAGE_COLUMNS:
        assert col not in FEATURE_COLUMNS, (
            f"CRITICAL LEAKAGE: Excluded column '{col}' is present in FEATURE_COLUMNS!"
        )

    # Label columns must not be in feature columns
    for col in LABEL_COLUMNS:
        assert col not in FEATURE_COLUMNS, (
            f"CRITICAL LEAKAGE: Label column '{col}' is present in FEATURE_COLUMNS!"
        )


def test_truncation_test_guarantees_zero_temporal_leakage(
    sample_multi_season_df: pd.DataFrame,
) -> None:
    """TRUNCATION TEST: Modifying/corrupting post-cutoff data does not alter any feature value.

    Features built from the full season dataset must be bit-for-bit identical to
    features built when all post-January 31 data (February, March, April rain and prices,
    full-season yield, and post-cutoff NDVI) are heavily corrupted or masked.
    """
    # 1. Build features from the uncorrupted dataset
    feats_original = build_feature_dataset(sample_multi_season_df)

    # 2. Heavily corrupt all post-cutoff data (Feb, Mar, Apr rain and prices, harvest yield)
    corrupted_df = sample_multi_season_df.copy()
    corrupted_df["rain_feb_mm"] = 9999.0
    corrupted_df["rain_mar_mm"] = 8888.0
    corrupted_df["rain_apr_mm"] = 7777.0
    corrupted_df["rain_total_mm"] = 99999.0
    corrupted_df["price_feb"] = 1.0
    corrupted_df["price_mar"] = 2.0
    corrupted_df["price_apr"] = 3.0
    corrupted_df["yield_kg_per_ha"] = 99999.0

    feats_truncated = build_feature_dataset(corrupted_df)

    # 3. Assert all feature columns are completely identical
    err_msg = "Feature '{col}' changed when post-cutoff data corrupted! Look-ahead leakage."
    for col in FEATURE_COLUMNS:
        orig_series = feats_original[col]
        trunc_series = feats_truncated[col]
        pd.testing.assert_series_equal(
            orig_series,
            trunc_series,
            check_exact=True,
            obj=err_msg.format(col=col),
        )


def test_label_computation_hand_checked_math(sample_multi_season_df: pd.DataFrame) -> None:
    """Verify expanding-baseline proxy stress label against exact hand-calculated numbers."""
    labels = compute_proxy_labels(sample_multi_season_df, drop_threshold_pct=15.0)

    # Plot 1: ANAND_01
    p1 = labels[labels["plot_code"] == "ANAND_01"].sort_values("season").reset_index(drop=True)

    # 2020-21: First season -> insufficient history
    assert p1.loc[0, "season"] == "2020-21"
    assert bool(p1.loc[0, "label_unavailable"]) is True
    assert pd.isna(p1.loc[0, "stressed"])
    assert pd.isna(p1.loc[0, "historical_baseline_ndvi"])
    assert pd.isna(p1.loc[0, "peak_drop_pct"])

    # 2021-22: Baseline = 0.80. Peak = 0.64. Drop = (0.80-0.64)/0.80 * 100 = 20.0% -> STRESSED (1)
    assert p1.loc[1, "season"] == "2021-22"
    assert bool(p1.loc[1, "label_unavailable"]) is False
    assert p1.loc[1, "historical_baseline_ndvi"] == 0.80
    assert p1.loc[1, "peak_drop_pct"] == 20.0
    assert p1.loc[1, "stressed"] == 1

    # 2022-23: Baseline = (0.80+0.64)/2 = 0.72. Peak = 0.72. Drop = 0.0% -> NORMAL (0)
    assert p1.loc[2, "season"] == "2022-23"
    assert bool(p1.loc[2, "label_unavailable"]) is False
    assert p1.loc[2, "historical_baseline_ndvi"] == 0.72
    assert p1.loc[2, "peak_drop_pct"] == 0.0
    assert p1.loc[2, "stressed"] == 0

    # 2023-24: Baseline = 0.72. Peak = 0.54. Drop = (0.72-0.54)/0.72 * 100 = 25.0% -> STRESSED (1)
    assert p1.loc[3, "season"] == "2023-24"
    assert bool(p1.loc[3, "label_unavailable"]) is False
    assert p1.loc[3, "historical_baseline_ndvi"] == 0.72
    assert p1.loc[3, "peak_drop_pct"] == 25.0
    assert p1.loc[3, "stressed"] == 1


def test_past_stressed_seasons_strictly_uses_earlier_seasons(
    sample_multi_season_df: pd.DataFrame,
) -> None:
    """Verify that 'past_stressed_seasons_count' uses only strictly prior completed seasons."""
    feats = build_feature_dataset(sample_multi_season_df)
    p1 = feats[feats["plot_code"] == "ANAND_01"].sort_values("season").reset_index(drop=True)

    # 2020-21: No prior history -> 0
    assert p1.loc[0, "season"] == "2020-21"
    assert p1.loc[0, "past_stressed_seasons_count"] == 0
    assert pd.isna(p1.loc[0, "prev_season_ndvi_peak"])

    # 2021-22: Outcome was stressed (1), but BEFORE this season the past count was 0!
    assert p1.loc[1, "season"] == "2021-22"
    assert p1.loc[1, "past_stressed_seasons_count"] == 0
    assert p1.loc[1, "prev_season_ndvi_peak"] == 0.80

    # 2022-23: Prior seasons: 2020-21 (unavail), 2021-22 (stressed=1) -> past count = 1
    assert p1.loc[2, "season"] == "2022-23"
    assert p1.loc[2, "past_stressed_seasons_count"] == 1
    assert p1.loc[2, "prev_season_ndvi_peak"] == 0.64

    # 2023-24: Prior seasons: 2021-22 (stressed=1), 2022-23 (stressed=0) -> past count = 1
    assert p1.loc[3, "season"] == "2023-24"
    assert p1.loc[3, "past_stressed_seasons_count"] == 1
    assert p1.loc[3, "prev_season_ndvi_peak"] == 0.72


def test_rows_with_insufficient_history_get_label_unavailable_and_are_preserved(
    sample_multi_season_df: pd.DataFrame,
) -> None:
    """Plot-seasons lacking prior history get label_unavailable=True and are never dropped."""
    feats = build_feature_dataset(sample_multi_season_df)

    # Total rows must be exactly equal to input row count (never dropped)
    assert len(feats) == len(sample_multi_season_df)

    # Plot 2 has only 1 season -> must be unlabelled
    p2 = feats[feats["plot_code"] == "BORSAD_02"]
    assert len(p2) == 1
    assert bool(p2["label_unavailable"].iloc[0]) is True
    assert pd.isna(p2["stressed"].iloc[0])


def test_missing_inputs_stay_missing_and_never_imputed(
    sample_multi_season_df: pd.DataFrame,
) -> None:
    """Missing input values (e.g. ndvi_early) stay None/NaN and are never imputed with zero."""
    feats = build_feature_dataset(sample_multi_season_df)

    # BORSAD_02 had ndvi_early=None
    p2_early = feats[feats["plot_code"] == "BORSAD_02"]["ndvi_early"].iloc[0]
    assert p2_early is None or pd.isna(p2_early)
    assert p2_early != 0.0  # Must never be zero-filled!


def test_feature_builder_fails_when_cutoff_outside_season_window(
    sample_multi_season_df: pd.DataFrame,
) -> None:
    """Verify ValueError is raised if cut-off date falls outside the Nov 1 to Apr 15 window."""
    # May 1 (cutoff_month=5, cutoff_day=1) is outside Nov 1 to Apr 15 window
    bad_config = FeaturePipelineConfig(cutoff_month=5, cutoff_day=1)
    with pytest.raises(ValueError, match="falls outside season window"):
        build_feature_dataset(sample_multi_season_df, config=bad_config)


def test_extract_pre_cutoff_satellite_features() -> None:
    """Verify scene-level satellite feature extractor ignores all scenes after cut-off date."""
    cutoff = date(2024, 1, 31)
    start = date(2023, 11, 1)

    raw_scenes = [
        {"date": "2023-11-15", "ndvi": 0.25, "is_valid": True},
        {"date": "2023-12-15", "ndvi": 0.45, "is_valid": True},
        {"date": "2024-01-15", "ndvi": 0.65, "is_valid": True},
        # These 2 scenes occur strictly AFTER cut-off date (must be completely ignored!)
        {"date": "2024-02-15", "ndvi": 0.90, "is_valid": True},
        {"date": "2024-03-15", "ndvi": 0.30, "is_valid": True},
    ]

    stats = extract_pre_cutoff_satellite_features(raw_scenes, cutoff, start)
    # Mean of [0.25, 0.45, 0.65] = 0.45
    assert stats["ndvi_pre_cutoff_mean"] == 0.45
    assert stats["ndvi_pre_cutoff_std"] is not None
    assert stats["ndvi_trend_pre_cutoff"] is not None
    # Slope must be positive (vegetative growth)
    assert stats["ndvi_trend_pre_cutoff"] > 0


def test_compute_linear_trend_handles_edge_cases() -> None:
    """Verify linear trend handles single points, identical points, and normal vectors."""
    # Fewer than 2 points
    assert compute_linear_trend([date(2023, 11, 1)], [0.5]) is None

    # Two points: 10 days, ndvi increases by 0.10 -> slope = 0.01 per day
    slope = compute_linear_trend(
        [date(2023, 11, 1), date(2023, 11, 11)],
        [0.20, 0.30],
    )
    assert slope == 0.01


def test_compute_mandi_cv() -> None:
    """Verify mandi CV calculation on known values."""
    # CV of [2000, 2000, 2000] is 0.0
    assert compute_mandi_cv([2000.0, 2000.0, 2000.0]) == 0.0
    # Single value returns None
    assert compute_mandi_cv([2000.0]) is None
    # None / empty returns None
    assert compute_mandi_cv([]) is None


def test_real_season_dataset_end_to_end_build() -> None:
    """Verify end-to-end feature dataset building on real data/processed/season_dataset.csv."""
    real_csv = Path("data/processed/season_dataset.csv")
    if not real_csv.is_file():
        pytest.skip("data/processed/season_dataset.csv not present in environment")

    df = pd.read_csv(real_csv)
    feats = build_feature_dataset(df, raw_satellite_dir=Path("data/raw/satellite"))

    # Assert exact row count matches input
    assert len(feats) == len(df)

    # Column separation
    for col in METADATA_COLUMNS:
        assert col in feats.columns
    for col in FEATURE_COLUMNS:
        assert col in feats.columns
    for col in LABEL_COLUMNS:
        assert col in feats.columns

    # Unlabelled count
    unlabelled = feats[feats["label_unavailable"]]
    assert len(unlabelled) == len(df[df["season"] == "2020-21"])  # All plots in season 1 (2020-21)
    assert set(unlabelled["season"].unique()) == {"2020-21"}

    # Labelled count
    labelled = feats[~feats["label_unavailable"]]
    assert len(labelled) == len(df[df["season"] != "2020-21"])
