"""Risk scoring and baseline validation package (T-05).

Provides baseline heuristics, machine learning classifiers, time-aware cross-validation,
cluster bootstrap confidence intervals, and standardized model versioning.
"""

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
    run_permutation_sanity_test,
)
from satbhoomi.risk.models import (
    SafeClassifierWrapper,
    build_logistic_regression,
    build_random_forest,
    build_xgboost,
    create_preprocessor,
)
from satbhoomi.risk.train import (
    compute_dataset_hash,
    generate_model_version_string,
    train_and_evaluate_pipeline,
)

__all__ = [
    "AgronomicRulesBaseline",
    "MajorityClassBaseline",
    "PersistenceBaseline",
    "SafeClassifierWrapper",
    "build_logistic_regression",
    "build_random_forest",
    "build_xgboost",
    "cluster_bootstrap_confidence_interval",
    "compute_calibration_table",
    "compute_dataset_hash",
    "compute_metrics",
    "create_preprocessor",
    "evaluate_by_plot_size",
    "generate_model_version_string",
    "run_permutation_sanity_test",
    "train_and_evaluate_pipeline",
]
