"""Pure in-season risk scoring, banding, and missing-data handling (T-06).

Produces a deterministic, traceable, zero-PII RiskScoreResult for a single
plot-season feature row as of the January 31 in-season cut-off date.

Per user decision for T-06:
- Active scorer is `rules_baseline` (AgronomicRulesBaseline).
- Saved Logistic Regression from T-05 is NOT used for live scoring because it
  was trained on single-class sample data (0 stressed outcomes).
- Every result includes `scorer`, `model_version`, `interpretation`, and
  `reliability_note`.
"""

from collections.abc import Mapping
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.features.config import (
    FEATURE_COLUMNS,
)
from satbhoomi.risk.baseline import AgronomicRulesBaseline
from satbhoomi.risk.config import (
    BAND_LOW_MAX,
    BAND_MEDIUM_MAX,
    CORE_INSEASON_FEATURES,
    CUTOFF_DATE_LABEL,
    DEFAULT_ACTIVE_SCORER,
    FIXED_INTERPRETATION,
    FIXED_RELIABILITY_NOTE,
    MAX_MISSING_FEATURES_ALLOWED,
    RULES_BASELINE_VERSION,
)
from satbhoomi.risk.explain import (
    explain_logistic_regression,
    explain_rules_baseline,
    is_value_missing,
)
from satbhoomi.risk.models import SafeClassifierWrapper

# Module-level cached baseline model fitted on features dataset if available
_CACHED_BASELINE_MODEL: AgronomicRulesBaseline | None = None


def get_default_rules_baseline() -> AgronomicRulesBaseline:
    """Return default singleton AgronomicRulesBaseline fitted on historical dataset if present."""
    global _CACHED_BASELINE_MODEL
    if _CACHED_BASELINE_MODEL is None:
        _CACHED_BASELINE_MODEL = AgronomicRulesBaseline()
        from pathlib import Path

        feat_csv = Path("data/processed/features.csv")
        if feat_csv.is_file():
            try:
                df = pd.read_csv(feat_csv)
                _CACHED_BASELINE_MODEL.fit(df)
            except Exception:
                pass
    return _CACHED_BASELINE_MODEL


class RiskScoreResult(BaseModel):
    """Typed, immutable scoring output with zero personal data."""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok", "insufficient_data"]
    plot_code: str
    season: str
    scorer: Literal["rules_baseline", "logreg"]
    model_version: str
    cutoff_date: str = CUTOFF_DATE_LABEL
    score: int | None = Field(default=None, ge=0, le=100)
    band: Literal["low", "medium", "high"] | None = None
    reasons: list[str] = Field(default_factory=list)
    protective_factor: str | None = None
    data_warnings: list[str] = Field(default_factory=list)
    insufficient_data_reason: str | None = None
    interpretation: str = FIXED_INTERPRETATION
    reliability_note: str = FIXED_RELIABILITY_NOTE


def map_score_to_band(score: int) -> Literal["low", "medium", "high"]:
    """Map integer score (0..100) to risk band using single-source thresholds."""
    if score < 0 or score > 100:
        raise ValueError(f"Score must be between 0 and 100, got {score}")
    if score <= BAND_LOW_MAX:
        return "low"
    if score <= BAND_MEDIUM_MAX:
        return "medium"
    return "high"


def score_plot_season(
    row: Mapping[str, Any] | pd.Series,
    scorer: Literal["rules_baseline", "logreg"] = DEFAULT_ACTIVE_SCORER,
    model: AgronomicRulesBaseline | SafeClassifierWrapper | None = None,
    model_version: str | None = None,
) -> RiskScoreResult:
    """Score a single plot-season feature row deterministically.

    Args:
        row: Feature row (dict/Mapping or pandas Series) containing plot_code,
            season, and pre-cutoff features from FEATURE_COLUMNS.
        scorer: Active scorer ("rules_baseline" default, or "logreg" for
            multi-class testing).
        model: Optional fitted model instance matching `scorer`.
        model_version: Optional version string (defaults to RULES_BASELINE_VERSION
            for rules_baseline).

    Returns:
        Immutable RiskScoreResult with score (0-100), band, 3 grounded reasons,
        model_version, cutoff_date, data_warnings, interpretation, and
        reliability_note—or status="insufficient_data" if missingness exceeds limit.
    """
    row_dict = dict(row.items()) if isinstance(row, pd.Series) else dict(row)
    plot_code = str(row_dict.get("plot_code", "UNKNOWN_PLOT"))
    season = str(row_dict.get("season", "UNKNOWN_SEASON"))

    if scorer == "rules_baseline":
        resolved_version = model_version or RULES_BASELINE_VERSION
    else:
        if model_version is None:
            raise ValueError("model_version must be provided when scorer='logreg'")
        resolved_version = model_version

    # Inspect missing features without inventing any values
    missing_features = [f for f in FEATURE_COLUMNS if is_value_missing(row_dict.get(f))]
    data_warnings = [
        f"Missing feature '{feat}': skipped from explanation; value not invented."
        for feat in missing_features
    ]

    core_missing_count = sum(1 for f in CORE_INSEASON_FEATURES if f in missing_features)
    all_core_missing = core_missing_count == len(CORE_INSEASON_FEATURES)

    if len(missing_features) > MAX_MISSING_FEATURES_ALLOWED or all_core_missing:
        reason_msg = (
            f"Insufficient data: {len(missing_features)} of {len(FEATURE_COLUMNS)} features "
            f"are missing (maximum allowed: {MAX_MISSING_FEATURES_ALLOWED}; core in-season "
            f"signals missing: {core_missing_count}/{len(CORE_INSEASON_FEATURES)})."
        )
        return RiskScoreResult(
            status="insufficient_data",
            plot_code=plot_code,
            season=season,
            scorer=scorer,
            model_version=resolved_version,
            score=None,
            band=None,
            reasons=[],
            protective_factor=None,
            data_warnings=data_warnings,
            insufficient_data_reason=reason_msg,
        )

    # Historical prior baseline check for relative rules baseline (docs/SCORER_REVIEW.md Section A4)
    if scorer == "rules_baseline":
        rules_model = (
            model if isinstance(model, AgronomicRulesBaseline) else get_default_rules_baseline()
        )
        key = (plot_code, season)

        has_explicit_baseline = (
            "ndvi_pre_cutoff_baseline" in row_dict
            and not is_value_missing(row_dict["ndvi_pre_cutoff_baseline"])
        ) or (
            "prior_ndvi_pre_cutoff_mean" in row_dict
            and not is_value_missing(row_dict["prior_ndvi_pre_cutoff_mean"])
        )
        prior_count = row_dict.get("prior_seasons_count")
        if prior_count is None and key in rules_model.prior_seasons_count_:
            prior_count = rules_model.prior_seasons_count_[key]

        # Season 1 (2020-21) or 0 prior seasons strictly returns insufficient_data
        if (
            season == "2020-21"
            or prior_count == 0
            or (not has_explicit_baseline and key not in rules_model.baseline_history_)
        ):
            return RiskScoreResult(
                status="insufficient_data",
                plot_code=plot_code,
                season=season,
                scorer=scorer,
                model_version=resolved_version,
                score=None,
                band=None,
                reasons=[],
                protective_factor=None,
                data_warnings=data_warnings,
                insufficient_data_reason=(
                    "No historical prior seasons available to establish plot baseline"
                ),
            )
        explanation = explain_rules_baseline(row_dict, model=rules_model)
    elif scorer == "logreg":
        if not isinstance(model, SafeClassifierWrapper):
            raise TypeError("scorer='logreg' requires a fitted SafeClassifierWrapper model")
        explanation = explain_logistic_regression(row_dict, model=model)
    else:
        raise ValueError(f"Unsupported scorer: {scorer}")

    raw_score = int(round(explanation.predicted_probability * 100.0))
    clamped_score = max(0, min(100, raw_score))
    band = map_score_to_band(clamped_score)

    return RiskScoreResult(
        status="ok",
        plot_code=plot_code,
        season=season,
        scorer=scorer,
        model_version=resolved_version,
        score=clamped_score,
        band=band,
        reasons=explanation.reasons,
        protective_factor=explanation.protective_factor,
        data_warnings=data_warnings,
        insufficient_data_reason=None,
    )
