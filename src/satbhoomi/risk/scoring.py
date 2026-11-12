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
from datetime import date
from typing import Any, Final, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from satbhoomi.features.config import (
    DEFAULT_CUTOFF_DAY,
    DEFAULT_CUTOFF_MONTH,
    FEATURE_COLUMNS,
)
from satbhoomi.risk.baseline import AgronomicRulesBaseline
from satbhoomi.risk.explain import (
    explain_logistic_regression,
    explain_rules_baseline,
    is_value_missing,
)
from satbhoomi.risk.models import SafeClassifierWrapper

# ---------------------------------------------------------------------------
# Single-Source Scoring & Band Configuration
# ---------------------------------------------------------------------------

DEFAULT_ACTIVE_SCORER: Final[Literal["rules_baseline", "logreg"]] = "rules_baseline"
RULES_BASELINE_VERSION: Final[str] = "satbhoomi-rules-v1.0-agronomic-jan31"

# Band thresholds derived strictly from agronomic reasoning and the
# pre-registered AgronomicRulesBaseline probability tiers (0.10, 0.45, 0.85)
# and EVAL_PROTOCOL.md 3-tier buckets:
#   - Low    [0, 34]  : Normal growth (baseline p=0.10 -> score=10)
#   - Medium [35, 69] : Partial stress (one rule condition p=0.45 -> score=45)
#   - High   [70, 100]: Compound stress (both conditions p=0.85 -> score=85)
BAND_LOW_MAX: Final[int] = 34
BAND_MEDIUM_MAX: Final[int] = 69

# Missing-feature tolerance rule:
# Up to 2 missing features (out of 12) are allowed (e.g. Season 1 missing
# prev_season_ndvi_peak and early cloud cover missing ndvi_early).
# More than 2 missing features—or all core in-season signals missing—triggers
# `insufficient_data` with no score returned.
MAX_MISSING_FEATURES_ALLOWED: Final[int] = 2
CORE_INSEASON_FEATURES: Final[tuple[str, ...]] = (
    "ndvi_early",
    "ndvi_pre_cutoff_mean",
    "ndvi_trend_pre_cutoff",
    "rain_pre_cutoff_total_mm",
    "rain_pre_cutoff_deficit_pct",
)

CUTOFF_DATE_LABEL: Final[str] = date(2000, DEFAULT_CUTOFF_MONTH, DEFAULT_CUTOFF_DAY).strftime(
    "%B %d"
)

FIXED_INTERPRETATION: Final[str] = (
    "In-season farm stress risk estimate as of the January 31 cut-off date. "
    "This score is a model/heuristic estimate of crop stress for loan officer "
    "decision support only—not a measured probability of loan default, not a "
    "pre-sowing loan approval score, and never an automated loan decision."
)

FIXED_RELIABILITY_NOTE: Final[str] = (
    "Not validated: no stressed outcomes were available in the sample data, "
    "so this score has not been shown to predict crop stress."
)


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

    if scorer == "rules_baseline":
        rules_model = model if isinstance(model, AgronomicRulesBaseline) else None
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
