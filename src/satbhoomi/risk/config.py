"""Centralized risk scoring, banding, and loan underwriting configuration (Stage B).

All thresholds, versions, and underwriting parameters are centralized here as the
single source of truth, directly grounded in the approved agronomic review
(docs/SCORER_REVIEW.md, Approved 2026-11-14).
"""

from __future__ import annotations

from datetime import date
from typing import Final, Literal

from satbhoomi.features.config import (
    DEFAULT_CUTOFF_DAY,
    DEFAULT_CUTOFF_MONTH,
)

# ---------------------------------------------------------------------------
# 1. Model Version & Cut-Off Date
# ---------------------------------------------------------------------------
# Version incremented following approved relative threshold review (ADR-12)
RULES_BASELINE_VERSION: Final[str] = "satbhoomi-rules-v2.0-relative-20261114"
DEFAULT_ACTIVE_SCORER: Final[Literal["rules_baseline", "logreg"]] = "rules_baseline"

# Cut-off date: January 31 (month=1, day=31) - strictly unshifted
CUTOFF_DATE_LABEL: Final[str] = date(2000, DEFAULT_CUTOFF_MONTH, DEFAULT_CUTOFF_DAY).strftime(
    "%B %d"
)

# ---------------------------------------------------------------------------
# 2. Relative Vegetation Anomaly Thresholds (docs/SCORER_REVIEW.md Section A4 Principle 1)
# ---------------------------------------------------------------------------
# Evaluates plot's pre-cutoff mean NDVI against its own strictly prior historical baseline.
# Grounded in empirical natural variability (MAD = 7.24%):
# - Moderate lag: >= 15.0% drop (~2.0 * MAD, 10th percentile of natural variation)
# - Acute lag: >= 25.0% drop (> 3.0 * MAD, extreme vegetative collapse)
NDVI_DROP_MODERATE_PCT: Final[float] = 15.0
NDVI_DROP_ACUTE_PCT: Final[float] = 25.0
MIN_PRIOR_SEASONS_FOR_RELATIVE_BASELINE: Final[int] = 1

# ---------------------------------------------------------------------------
# 3. Differentiated Rainfall Deficit Thresholds (docs/SCORER_REVIEW.md Section A4 Principle 2)
# ---------------------------------------------------------------------------
# Anand district rabi wheat is 85.7% irrigated (canal/tubewell) with normal winter
# rainfall of only 10.5 mm. Rainfall deficit is secondary on irrigated tracts (buffered)
# and primary only on rainfed plots.
RAIN_DEFICIT_MODERATE_PCT: Final[float] = -25.0  # IMD moderate drought classification
RAIN_DEFICIT_ACUTE_PCT: Final[float] = -50.0  # IMD severe drought classification

IRRIGATED_TYPES: Final[frozenset[str]] = frozenset(
    {"tube_well", "canal", "drip", "sprinkler", "irrigated"}
)
RAINFED_TYPES: Final[frozenset[str]] = frozenset({"rainfed"})

# ---------------------------------------------------------------------------
# 4. Rules Baseline Output Probability Tiers (ADR-2 & docs/SCORER_REVIEW.md Section A4 Principle 4)
# ---------------------------------------------------------------------------
PROB_NORMAL: Final[float] = 0.10  # Normal vegetative progression (low risk)
PROB_MODERATE_STRESS: Final[float] = 0.45  # Moderate vegetative lag or rainfed moisture deficit
PROB_ACUTE_STRESS: Final[float] = 0.85  # Acute vegetative collapse or compound distress

# ---------------------------------------------------------------------------
# 5. Risk Band Thresholds (docs/SCORER_REVIEW.md Section A4 Principle 4)
# ---------------------------------------------------------------------------
# Integer score scale [0, 100] derived strictly from probability tiers:
# - Low:    [0, 34]   (PROB_NORMAL 0.10 -> score 10)
# - Medium: [35, 69]  (PROB_MODERATE_STRESS 0.45 -> score 45)
# - High:   [70, 100] (PROB_ACUTE_STRESS 0.85 -> score 85)
BAND_LOW_MAX: Final[int] = 34
BAND_MEDIUM_MAX: Final[int] = 69
BAND_HIGH_MIN: Final[int] = 70

# ---------------------------------------------------------------------------
# 6. Missing Feature Tolerance (docs/SCORER_REVIEW.md Section A1)
# ---------------------------------------------------------------------------
MAX_MISSING_FEATURES_ALLOWED: Final[int] = 2
CORE_INSEASON_FEATURES: Final[tuple[str, ...]] = (
    "ndvi_early",
    "ndvi_pre_cutoff_mean",
    "ndvi_trend_pre_cutoff",
    "rain_pre_cutoff_total_mm",
    "rain_pre_cutoff_deficit_pct",
)

# ---------------------------------------------------------------------------
# 7. Loan Underwriting Parameters (docs/SCORER_REVIEW.md Section A5)
# ---------------------------------------------------------------------------
# Scale of Finance (INR per acre) - classified as PLACEHOLDER pending official Anand DLTC
SCALE_OF_FINANCE_WHEAT_IRRIGATED: Final[int] = 32_000
SCALE_OF_FINANCE_WHEAT_RAINFED: Final[int] = 22_000

# Statutory limits & verified market windows
RBI_COLLATERAL_FREE_LIMIT_INR: Final[int] = 200_000  # RBI KCC circular FIDD.CO.FSD.BC.No.13/2018-19
REPAYMENT_MONTH_RABI_WHEAT: Final[str] = "May"  # Post-harvest marketing peak
HARVEST_WINDOW_LABEL: Final[str] = "March–April"
MARKETING_WINDOW_LABEL: Final[str] = "April–May"
REPAYMENT_WINDOW_LABEL: Final[str] = (
    "April–May (aligned with post-harvest APMC mandi arrivals and marketing window)"
)

# Underwriting limit haircut ratios [min_ratio, max_ratio] (Status: ASSUMPTION)
LIMIT_BAND_RATIOS: Final[dict[str, tuple[float, float]]] = {
    "low": (0.90, 1.00),  # 90% - 100% of maximum scale limit
    "medium": (0.65, 0.80),  # 65% - 80% haircut to prevent over-indebtedness
    "high": (0.40, 0.50),  # 40% - 50% conservative cap for elevated risk
}

# ---------------------------------------------------------------------------
# 8. Standard Regulatory Disclaimers & Fixed Interpretations
# ---------------------------------------------------------------------------
FIXED_INTERPRETATION: Final[str] = (
    "In-season farm stress risk estimate as of the January 31 cut-off date. "
    "This score is a model/heuristic estimate of crop stress for loan officer "
    "decision support only—not a measured probability of loan default, not a "
    "pre-sowing loan approval score, and never an automated loan decision."
)

FIXED_RELIABILITY_NOTE: Final[str] = (
    "Descriptive heuristic rules baseline evaluated on Sentinel-2 offset-corrected data. "
    "Under Evaluation Protocol v2, machine learning evaluation remains frozen under "
    "the Feasibility Gate (feasibility gate failed; status: NOT EVALUABLE)."
)

DISCLAIMER_LOAN_SUGGESTION: Final[str] = (
    "Decision-support suggestion only. SatBhoomi does not approve or reject loans. "
    "Final credit sanction, limit approval, and risk determination rest exclusively "
    "with the designated bank loan officer (Rule 1: Human-in-the-Loop)."
)

DISCLAIMER_WHAT_IF: Final[str] = (
    "Model-based sensitivity estimate only, not proof of causation (Rule 6). "
    "What-if simulations project prospective score and limit changes under "
    "hypothetical interventions. Final credit terms and verification rest "
    "exclusively with the bank loan officer."
)
