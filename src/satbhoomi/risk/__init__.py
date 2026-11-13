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
from satbhoomi.risk.explain import (
    ExplanationResult,
    explain_logistic_regression,
    explain_rules_baseline,
)
from satbhoomi.risk.loan_suggestions import (
    DISCLAIMER_LOAN_SUGGESTION,
    LIMIT_BAND_RATIOS,
    RBI_COLLATERAL_FREE_LIMIT_INR,
    REPAYMENT_MONTH_RABI_WHEAT,
    SCALE_OF_FINANCE_WHEAT_IRRIGATED,
    SCALE_OF_FINANCE_WHEAT_RAINFED,
    LimitBand,
    LoanSuggestionResult,
    RepaymentSchedule,
    generate_loan_suggestion,
)
from satbhoomi.risk.models import (
    SafeClassifierWrapper,
    build_logistic_regression,
    build_random_forest,
    build_xgboost,
    create_preprocessor,
)
from satbhoomi.risk.reason_templates import (
    OFFICER_RECORDED_PHRASE,
    TEMPLATE_FEATURES,
    render_feature_reason,
)
from satbhoomi.risk.scoring import (
    BAND_LOW_MAX,
    BAND_MEDIUM_MAX,
    DEFAULT_ACTIVE_SCORER,
    FIXED_INTERPRETATION,
    FIXED_RELIABILITY_NOTE,
    MAX_MISSING_FEATURES_ALLOWED,
    RULES_BASELINE_VERSION,
    RiskScoreResult,
    map_score_to_band,
    score_plot_season,
)
from satbhoomi.risk.train import (
    compute_dataset_hash,
    generate_model_version_string,
    train_and_evaluate_pipeline,
)

__all__ = [
    "BAND_LOW_MAX",
    "BAND_MEDIUM_MAX",
    "DEFAULT_ACTIVE_SCORER",
    "DISCLAIMER_LOAN_SUGGESTION",
    "FIXED_INTERPRETATION",
    "FIXED_RELIABILITY_NOTE",
    "LIMIT_BAND_RATIOS",
    "MAX_MISSING_FEATURES_ALLOWED",
    "OFFICER_RECORDED_PHRASE",
    "RBI_COLLATERAL_FREE_LIMIT_INR",
    "REPAYMENT_MONTH_RABI_WHEAT",
    "RULES_BASELINE_VERSION",
    "SCALE_OF_FINANCE_WHEAT_IRRIGATED",
    "SCALE_OF_FINANCE_WHEAT_RAINFED",
    "TEMPLATE_FEATURES",
    "AgronomicRulesBaseline",
    "ExplanationResult",
    "LimitBand",
    "LoanSuggestionResult",
    "MajorityClassBaseline",
    "PersistenceBaseline",
    "RepaymentSchedule",
    "RiskScoreResult",
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
    "explain_logistic_regression",
    "explain_rules_baseline",
    "generate_loan_suggestion",
    "generate_model_version_string",
    "map_score_to_band",
    "render_feature_reason",
    "run_permutation_sanity_test",
    "score_plot_season",
    "train_and_evaluate_pipeline",
]
