"""Feature contribution explainers for SatBhoomi risk scorers (T-06).

Implements exact, deterministic, additive explanations without external SHAP
dependencies:
- AgronomicRulesBaseline: Exact additive decomposition of rule terms in
  probability space (base_value=0.10 + rule_contributions == predicted_prob).
- LogisticRegression: Exact linear contributions (coef * scaled_value) in
  log-odds space (intercept + sum(contributions) == logit == log(p/(1-p))).
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from satbhoomi.features.config import FEATURE_COLUMNS
from satbhoomi.risk.baseline import AgronomicRulesBaseline
from satbhoomi.risk.config import RAINFED_TYPES
from satbhoomi.risk.models import SafeClassifierWrapper
from satbhoomi.risk.reason_templates import render_feature_reason

# Deterministic priority order for contextual fallback reasons when fewer than 3
# features have strictly positive risk-increasing contributions.
CONTEXT_PRIORITY_ORDER: tuple[str, ...] = (
    "ndvi_early",
    "ndvi_pre_cutoff_mean",
    "ndvi_trend_pre_cutoff",
    "rain_pre_cutoff_total_mm",
    "rain_pre_cutoff_deficit_pct",
    "mandi_pre_cutoff_volatility",
    "past_stressed_seasons_count",
    "prev_season_ndvi_peak",
    "ndvi_pre_cutoff_std",
    "irrigation",
    "insured",
    "area_acre",
)


@dataclass(frozen=True)
class ExplanationResult:
    """Structured explanation output for additivity and reason generation."""

    scorer: str
    space: str  # "probability" for rules_baseline, "log_odds" for logreg
    base_value: float
    predicted_probability: float
    model_output_value: float  # probability for rules_baseline, logit for logreg
    contributions: dict[str, float]
    reasons: list[str]
    protective_factor: str | None


def is_value_missing(val: Any) -> bool:
    """Return True if value is None or NaN."""
    if val is None:
        return True
    try:
        return bool(pd.isna(val))
    except (TypeError, ValueError):
        return False


def _select_reasons_and_protective(
    row: dict[str, Any],
    contributions: dict[str, float],
    missing_features: set[str],
    n_reasons: int = 3,
) -> tuple[list[str], str | None]:
    """Select top risk-increasing reasons (up to 3, padded deterministically) and
    top protective factor, skipping all missing features.
    """
    available = [f for f in FEATURE_COLUMNS if f not in missing_features]
    priority_rank = {f: idx for idx, f in enumerate(CONTEXT_PRIORITY_ORDER)}

    # Features pushing risk UP (contribution > 0)
    up_features = sorted(
        [f for f in available if contributions.get(f, 0.0) > 1e-12],
        key=lambda f: (-contributions[f], priority_rank.get(f, 999)),
    )

    selected_for_reasons: list[tuple[str, str]] = [(f, "up") for f in up_features[:n_reasons]]

    # If fewer than n_reasons push risk UP, fill with observed contextual features
    if len(selected_for_reasons) < n_reasons:
        already = {f for f, _ in selected_for_reasons}
        remaining = sorted(
            [f for f in available if f not in already],
            key=lambda f: (
                0 if contributions.get(f, 0.0) < -1e-12 else 1,
                -abs(contributions.get(f, 0.0)),
                priority_rank.get(f, 999),
            ),
        )
        for f in remaining:
            if len(selected_for_reasons) >= n_reasons:
                break
            direction = "down" if contributions.get(f, 0.0) < -1e-12 else "neutral"
            selected_for_reasons.append((f, direction))

    reasons = [
        render_feature_reason(f, row[f], direction=direction, row_context=row)
        for f, direction in selected_for_reasons
    ]

    # Top protective factor (most negative contribution among non-missing features)
    down_features = sorted(
        [f for f in available if contributions.get(f, 0.0) < -1e-12],
        key=lambda f: (contributions[f], priority_rank.get(f, 999)),
    )
    protective = (
        render_feature_reason(
            down_features[0], row[down_features[0]], direction="down", row_context=row
        )
        if down_features
        else None
    )

    return reasons, protective


def explain_rules_baseline(
    row: dict[str, Any],
    model: AgronomicRulesBaseline | None = None,
) -> ExplanationResult:
    """Compute exact additive probability contributions for AgronomicRulesBaseline (v2.0)."""
    scorer_model = model or AgronomicRulesBaseline()
    missing_features = {f for f in FEATURE_COLUMNS if is_value_missing(row.get(f))}

    plot_code = str(row.get("plot_code", ""))
    season = str(row.get("season", ""))
    key = (plot_code, season)

    # 1. Establish prior baseline and relative drop
    baseline = None
    n_prior = 0
    if "ndvi_pre_cutoff_baseline" in row and not is_value_missing(row["ndvi_pre_cutoff_baseline"]):
        baseline = float(row["ndvi_pre_cutoff_baseline"])
        n_prior = int(row.get("prior_seasons_count", 1))
    elif "prior_ndvi_pre_cutoff_mean" in row and not is_value_missing(
        row["prior_ndvi_pre_cutoff_mean"]
    ):
        baseline = float(row["prior_ndvi_pre_cutoff_mean"])
        n_prior = int(row.get("prior_seasons_count", 1))
    elif key in scorer_model.baseline_history_:
        baseline = scorer_model.baseline_history_[key]
        n_prior = scorer_model.prior_seasons_count_.get(key, 0)

    curr_ndvi = row.get("ndvi_pre_cutoff_mean")
    drop_pct = 0.0
    if (
        baseline is not None
        and baseline > 0.05
        and curr_ndvi is not None
        and not is_value_missing(curr_ndvi)
        and n_prior >= 1
    ):
        drop_pct = (baseline - float(curr_ndvi)) / baseline * 100.0

    is_acute_veg = (
        "ndvi_pre_cutoff_mean" not in missing_features
        and drop_pct >= scorer_model.ndvi_drop_acute_pct
    )
    is_mod_veg = (
        "ndvi_pre_cutoff_mean" not in missing_features
        and drop_pct >= scorer_model.ndvi_drop_moderate_pct
    )

    # 2. Differentiated rainfall deficit check (rainfed only)
    irr = str(row.get("irrigation", "tube_well")).strip().lower()
    is_rainfed = irr in RAINFED_TYPES
    rain_def = row.get("rain_pre_cutoff_deficit_pct")
    is_rain_stress = (
        is_rainfed
        and "rain_pre_cutoff_deficit_pct" not in missing_features
        and rain_def is not None
        and not is_value_missing(rain_def)
        and float(rain_def) <= scorer_model.rain_deficit_moderate_pct
    )

    # 3. Exact additive probability contributions
    base_value = scorer_model.prob_low
    contributions: dict[str, float] = {f: 0.0 for f in FEATURE_COLUMNS if f not in missing_features}

    if is_acute_veg and is_rain_stress:
        pred_prob = scorer_model.prob_high
        contributions["ndvi_pre_cutoff_mean"] = 0.375
        contributions["rain_pre_cutoff_deficit_pct"] = 0.375
    elif is_acute_veg:
        pred_prob = scorer_model.prob_high
        contributions["ndvi_pre_cutoff_mean"] = 0.75
    elif is_mod_veg and is_rain_stress:
        pred_prob = scorer_model.prob_high
        contributions["ndvi_pre_cutoff_mean"] = 0.375
        contributions["rain_pre_cutoff_deficit_pct"] = 0.375
    elif is_mod_veg:
        pred_prob = scorer_model.prob_medium
        contributions["ndvi_pre_cutoff_mean"] = 0.35
    elif is_rain_stress:
        pred_prob = scorer_model.prob_medium
        contributions["rain_pre_cutoff_deficit_pct"] = 0.35
    else:
        pred_prob = scorer_model.prob_low

    ctx = dict(row, rel_drop_pct=drop_pct, baseline_ndvi=baseline)
    reasons, protective = _select_reasons_and_protective(ctx, contributions, missing_features)

    return ExplanationResult(
        scorer="rules_baseline",
        space="probability",
        base_value=base_value,
        predicted_probability=pred_prob,
        model_output_value=pred_prob,
        contributions=contributions,
        reasons=reasons,
        protective_factor=protective,
    )


def explain_logistic_regression(
    row: dict[str, Any],
    model: SafeClassifierWrapper,
) -> ExplanationResult:
    """Compute exact coefficient * scaled_value contributions for Logistic Regression."""
    missing_features = {f for f in FEATURE_COLUMNS if is_value_missing(row.get(f))}
    df_row = pd.DataFrame([{f: row.get(f, np.nan) for f in FEATURE_COLUMNS}])
    pred_prob = float(model.predict_proba(df_row)[0, 1])

    if model.single_class_target_ is not None or model.pipeline_ is None:
        base_val = float(model.single_class_target_ or 0)
        contributions = {f: 0.0 for f in FEATURE_COLUMNS if f not in missing_features}
        reasons, protective = _select_reasons_and_protective(row, contributions, missing_features)
        return ExplanationResult(
            scorer="logreg",
            space="probability",
            base_value=base_val,
            predicted_probability=pred_prob,
            model_output_value=pred_prob,
            contributions=contributions,
            reasons=reasons,
            protective_factor=protective,
        )

    preprocessor = model.pipeline_.named_steps["preprocessor"]
    clf = model.pipeline_.named_steps["classifier"]

    x_trans = preprocessor.transform(df_row)
    x_vec = x_trans[0]
    coefs = clf.coef_[0]
    intercept = float(clf.intercept_[0])
    logit = float(clf.decision_function(x_trans)[0])

    trans_names = preprocessor.get_feature_names_out()
    raw_contribs: dict[str, float] = dict.fromkeys(FEATURE_COLUMNS, 0.0)

    for name, coef_val, x_val in zip(trans_names, coefs, x_vec, strict=True):
        contrib = float(coef_val * x_val)
        if name.startswith("num__"):
            feat = name[len("num__") :]
            if feat in raw_contribs:
                raw_contribs[feat] += contrib
        elif name.startswith("cat__irrigation_"):
            raw_contribs["irrigation"] += contrib

    reasons, protective = _select_reasons_and_protective(row, raw_contribs, missing_features)

    return ExplanationResult(
        scorer="logreg",
        space="log_odds",
        base_value=intercept,
        predicted_probability=pred_prob,
        model_output_value=logit,
        contributions=raw_contribs,
        reasons=reasons,
        protective_factor=protective,
    )
