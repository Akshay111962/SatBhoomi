"""Centralized configuration and agronomic thresholds for Raksha alerts (T-09, FR-008).

All thresholds are established from agronomic reasoning BEFORE running replay.
Permanent rule: No thresholds may be tuned or adjusted post-hoc after inspecting replay outputs.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Replay Checkpoints (Rabi Wheat Cycle in Anand District)
# ---------------------------------------------------------------------------
# Rabi wheat sowing occurs in Nov-Dec.
# Checkpoints track:
# - Early tillering / vegetative establishment: Dec 15
# - Late tillering / jointing stage: Jan 15
# - Terminal vegetative / pre-heading cut-off: Jan 31
CHECKPOINTS: Final[tuple[tuple[int, int], ...]] = (
    (12, 15),  # December 15
    (1, 15),  # January 15
    (1, 31),  # January 31 (In-season cut-off barrier)
)

HARVEST_MONTH: Final[int] = 4  # April typical wheat harvest in Gujarat

# ---------------------------------------------------------------------------
# 1. Crop Health Decline Thresholds (NDVI vs Plot's Own Prior Seasons)
# ---------------------------------------------------------------------------
# Agronomic assumption: Comparing plot NDVI at the checkpoint date against the
# plot's OWN mean NDVI on the identical calendar date in strictly prior completed
# seasons. A drop >= 15% indicates significant vegetative drag / stunted canopy.
NDVI_DROP_MEDIUM_PCT: Final[float] = 15.0
NDVI_DROP_HIGH_PCT: Final[float] = 25.0

MIN_PRIOR_SEASONS_FOR_NDVI_ALERT: Final[int] = 1
MIN_CLEAR_OBSERVATIONS_FOR_NDVI_ALERT: Final[int] = 2

# ---------------------------------------------------------------------------
# 2. Rainfall Deficit Thresholds (Winter Moisture Anomaly)
# ---------------------------------------------------------------------------
# Agronomic assumption: Rabi wheat in Gujarat is predominantly irrigated (canal/tubewell).
# Moderate winter rainfall deficits are buffered by irrigation infrastructure.
# Therefore, high-severity rainfall alerts are restricted to rainfed plots;
# for irrigated plots, rainfall alerts are capped at medium severity.
RAIN_DEFICIT_MEDIUM_PCT: Final[float] = -25.0
RAIN_DEFICIT_HIGH_PCT: Final[float] = -50.0

# ---------------------------------------------------------------------------
# 3. Mandi Price Crash Thresholds (APMC Anand District Series)
# ---------------------------------------------------------------------------
# Agronomic/Economic assumption: A drop of >= 15% in district modal wheat price
# relative to the same calendar month in strictly prior completed seasons indicates
# severe market softening / repayment cash-flow stress.
PRICE_DROP_ALERT_PCT: Final[float] = 15.0
MIN_PRIOR_SEASONS_FOR_PRICE_ALERT: Final[int] = 1

# ---------------------------------------------------------------------------
# Allowed Enums (Must match db/models/alert.py constraints)
# ---------------------------------------------------------------------------
ALLOWED_ALERT_TYPES: Final[tuple[str, ...]] = (
    "crop_health_drop",
    "rainfall_deficit",
    "price_crash",
)

ALLOWED_SEVERITIES: Final[tuple[str, ...]] = (
    "low",
    "medium",
    "high",
)

ALLOWED_STATUSES: Final[tuple[str, ...]] = (
    "open",
    "acknowledged",
    "resolved",
    "dismissed",
)
