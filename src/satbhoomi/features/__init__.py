"""Feature pipeline and proxy label engineering package (T-04).

Provides in-season pre-cutoff feature extraction, expanding-baseline
proxy ground-truth crop stress labels, and leakage prevention rules.
"""

from satbhoomi.features.build_features import (
    build_feature_dataset,
    compute_linear_trend,
    compute_mandi_cv,
    extract_pre_cutoff_satellite_features,
)
from satbhoomi.features.config import (
    ANAND_PRE_CUTOFF_NORMAL_RAIN_MM,
    DEFAULT_CUTOFF_DAY,
    DEFAULT_CUTOFF_MONTH,
    DEFAULT_LABEL_DROP_THRESHOLD_PCT,
    DEFAULT_MIN_PRIOR_SEASONS,
    EXCLUDED_LEAKAGE_COLUMNS,
    FEATURE_COLUMNS,
    LABEL_COLUMNS,
    METADATA_COLUMNS,
    RABI_SEASONS_ORDER,
    FeaturePipelineConfig,
)
from satbhoomi.features.label import compute_proxy_labels

__all__ = [
    "ANAND_PRE_CUTOFF_NORMAL_RAIN_MM",
    "DEFAULT_CUTOFF_DAY",
    "DEFAULT_CUTOFF_MONTH",
    "DEFAULT_LABEL_DROP_THRESHOLD_PCT",
    "DEFAULT_MIN_PRIOR_SEASONS",
    "EXCLUDED_LEAKAGE_COLUMNS",
    "FEATURE_COLUMNS",
    "LABEL_COLUMNS",
    "METADATA_COLUMNS",
    "RABI_SEASONS_ORDER",
    "FeaturePipelineConfig",
    "build_feature_dataset",
    "compute_linear_trend",
    "compute_mandi_cv",
    "compute_proxy_labels",
    "extract_pre_cutoff_satellite_features",
]
