"""Raksha in-season stress alert engine and historical replay (T-09, FR-008).

Monitors farm health during the cropping cycle, raises early stress alerts
(crop health decline, rainfall deficit, APMC price crash), and generates
supportive loan officer action summaries to prevent distress.
"""

from satbhoomi.alerts.config import (
    ALLOWED_ALERT_TYPES,
    ALLOWED_SEVERITIES,
    ALLOWED_STATUSES,
    CHECKPOINTS,
    HARVEST_MONTH,
    MIN_CLEAR_OBSERVATIONS_FOR_NDVI_ALERT,
    MIN_PRIOR_SEASONS_FOR_NDVI_ALERT,
    MIN_PRIOR_SEASONS_FOR_PRICE_ALERT,
    NDVI_DROP_HIGH_PCT,
    NDVI_DROP_MEDIUM_PCT,
    PRICE_DROP_ALERT_PCT,
    RAIN_DEFICIT_HIGH_PCT,
    RAIN_DEFICIT_MEDIUM_PCT,
)
from satbhoomi.alerts.engine import (
    SUPPORTIVE_ACTION_CROP_HEALTH,
    SUPPORTIVE_ACTION_PRICE,
    SUPPORTIVE_ACTION_RAINFALL,
    InSeasonAlertTracker,
    evaluate_crop_health_drop,
    evaluate_price_crash,
    evaluate_rainfall_deficit,
)
from satbhoomi.alerts.models import (
    AlertItem,
    EvaluationCheckpointResult,
    ReplayReport,
)
from satbhoomi.alerts.replay import (
    generate_synthetic_stress_scenario,
    replay_single_plot_season,
    run_full_replay,
)

__all__ = [
    "ALLOWED_ALERT_TYPES",
    "ALLOWED_SEVERITIES",
    "ALLOWED_STATUSES",
    "CHECKPOINTS",
    "HARVEST_MONTH",
    "MIN_CLEAR_OBSERVATIONS_FOR_NDVI_ALERT",
    "MIN_PRIOR_SEASONS_FOR_NDVI_ALERT",
    "MIN_PRIOR_SEASONS_FOR_PRICE_ALERT",
    "NDVI_DROP_HIGH_PCT",
    "NDVI_DROP_MEDIUM_PCT",
    "PRICE_DROP_ALERT_PCT",
    "RAIN_DEFICIT_HIGH_PCT",
    "RAIN_DEFICIT_MEDIUM_PCT",
    "SUPPORTIVE_ACTION_CROP_HEALTH",
    "SUPPORTIVE_ACTION_PRICE",
    "SUPPORTIVE_ACTION_RAINFALL",
    "AlertItem",
    "EvaluationCheckpointResult",
    "InSeasonAlertTracker",
    "ReplayReport",
    "evaluate_crop_health_drop",
    "evaluate_price_crash",
    "evaluate_rainfall_deficit",
    "generate_synthetic_stress_scenario",
    "replay_single_plot_season",
    "run_full_replay",
]
