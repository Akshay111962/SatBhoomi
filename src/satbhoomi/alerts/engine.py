"""Core alert evaluation and de-duplication engine (T-09, FR-008).

Implements deterministic in-season stress alert detection for:
1. Crop Health Decline (NDVI vs plot's own prior seasons on identical date)
2. Rainfall Deficit (weighted by irrigation infrastructure; capped at medium for irrigated)
3. Mandi Price Crash (district-level modal price drop vs prior seasons' monthly baseline)

Rule 2 Compliance:
Alerts strictly describe farm and repayment stress and support needed, never personal
mental state. All supportive actions are targeted at the bank loan officer.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from satbhoomi.alerts.config import (
    MIN_CLEAR_OBSERVATIONS_FOR_NDVI_ALERT,
    MIN_PRIOR_SEASONS_FOR_NDVI_ALERT,
    MIN_PRIOR_SEASONS_FOR_PRICE_ALERT,
    NDVI_DROP_HIGH_PCT,
    NDVI_DROP_MEDIUM_PCT,
    PRICE_DROP_ALERT_PCT,
    RAIN_DEFICIT_HIGH_PCT,
    RAIN_DEFICIT_MEDIUM_PCT,
)
from satbhoomi.alerts.models import AlertItem

SUPPORTIVE_ACTION_CROP_HEALTH: Final[str] = (
    "Schedule supportive field visit to verify plot moisture and canopy vigor; "
    "check whether PMFBY crop insurance claim assistance or irrigation support is needed."
)

SUPPORTIVE_ACTION_RAINFALL: Final[str] = (
    "Advise farmer on supplementary protective irrigation scheduling; inspect canal or "
    "tubewell water availability to mitigate moisture drag and prevent repayment stress."
)

SUPPORTIVE_ACTION_PRICE: Final[str] = (
    "Review post-harvest cash flow expectations; prepare for harvest-aligned repayment "
    "schedule flexibility and evaluate warehouse receipt or storage support to prevent "
    "distress selling."
)


def evaluate_crop_health_drop(
    *,
    plot_code: str,
    season: str,
    checkpoint_label: str,
    detected_on: date,
    current_ndvi: float | None,
    prior_ndvis_same_checkpoint: list[float],
    clear_obs_count: int,
) -> tuple[AlertItem | None, str | None]:
    """Evaluate crop health drop against the plot's own prior seasons on identical date.

    Returns:
        (alert_item, data_gap_reason)
    """
    if current_ndvi is None:
        return None, "Current season NDVI observation is missing at checkpoint."

    if clear_obs_count < MIN_CLEAR_OBSERVATIONS_FOR_NDVI_ALERT:
        return (
            None,
            f"Insufficient clear observations ({clear_obs_count} < "
            f"{MIN_CLEAR_OBSERVATIONS_FOR_NDVI_ALERT}); recorded as data_gap, not alert.",
        )

    if len(prior_ndvis_same_checkpoint) < MIN_PRIOR_SEASONS_FOR_NDVI_ALERT:
        return (
            None,
            f"Insufficient prior seasons history ({len(prior_ndvis_same_checkpoint)} < "
            f"{MIN_PRIOR_SEASONS_FOR_NDVI_ALERT}); recorded as data_gap, not alert.",
        )

    prior_mean = sum(prior_ndvis_same_checkpoint) / len(prior_ndvis_same_checkpoint)
    if prior_mean <= 0.05:
        return None, None

    drop_pct = (prior_mean - current_ndvi) / prior_mean * 100.0

    if drop_pct >= NDVI_DROP_HIGH_PCT:
        severity = "high"
    elif drop_pct >= NDVI_DROP_MEDIUM_PCT:
        severity = "medium"
    else:
        return None, None

    headline = (
        f"Early-season vegetation vigor decline ({drop_pct:0.1f}% drop below plot prior baseline)"
    )
    detail = (
        f"At {checkpoint_label}, plot {plot_code} recorded NDVI {current_ndvi:0.3f}, falling "
        f"{drop_pct:0.1f}% below its own historical baseline ({prior_mean:0.3f}) on this "
        "calendar date, indicating in-season vegetative drag and support needed."
    )

    alert = AlertItem(
        type="crop_health_drop",
        severity=severity,
        status="open",
        detected_on=detected_on,
        checkpoint_label=checkpoint_label,
        plot_code=plot_code,
        season=season,
        headline=headline,
        detail=detail,
        supportive_action=SUPPORTIVE_ACTION_CROP_HEALTH,
    )
    return alert, None


def evaluate_rainfall_deficit(
    *,
    plot_code: str,
    season: str,
    checkpoint_label: str,
    detected_on: date,
    rain_deficit_pct: float | None,
    irrigation: str,
) -> AlertItem | None:
    """Evaluate winter rainfall deficit with irrigation infrastructure weighting."""
    if rain_deficit_pct is None:
        return None

    is_rainfed = irrigation.strip().lower() == "rainfed"

    if rain_deficit_pct <= RAIN_DEFICIT_HIGH_PCT:
        # Assured irrigation buffers deficit: cap at medium for irrigated plots
        severity = "high" if is_rainfed else "medium"
        severity_note = (
            "Severe rainfall deficit on rainfed plot."
            if is_rainfed
            else (
                "Severe meteorological deficit, but capped at medium severity because "
                "assured irrigation provides water buffering."
            )
        )
    elif rain_deficit_pct <= RAIN_DEFICIT_MEDIUM_PCT:
        severity = "medium"
        severity_note = "Moderate winter precipitation deficit."
    else:
        return None

    headline = f"Winter precipitation deficit ({rain_deficit_pct:0.1f}% anomaly)"
    detail = (
        f"Cumulative winter precipitation at {checkpoint_label} is {rain_deficit_pct:0.1f}% "
        f"below normal. {severity_note} Irrigation type: {irrigation}. Early monitoring "
        "required to avoid repayment stress."
    )

    return AlertItem(
        type="rainfall_deficit",
        severity=severity,
        status="open",
        detected_on=detected_on,
        checkpoint_label=checkpoint_label,
        plot_code=plot_code,
        season=season,
        headline=headline,
        detail=detail,
        supportive_action=SUPPORTIVE_ACTION_RAINFALL,
    )


def evaluate_price_crash(
    *,
    plot_code: str,
    season: str,
    checkpoint_label: str,
    detected_on: date,
    current_district_price: float | None,
    prior_seasons_district_prices: list[float],
) -> AlertItem | None:
    """Evaluate district modal mandi price drop relative to prior seasons' monthly baseline."""
    if (
        current_district_price is None
        or len(prior_seasons_district_prices) < MIN_PRIOR_SEASONS_FOR_PRICE_ALERT
    ):
        return None

    prior_mean = sum(prior_seasons_district_prices) / len(prior_seasons_district_prices)
    if prior_mean <= 100:
        return None

    drop_pct = (prior_mean - current_district_price) / prior_mean * 100.0
    if drop_pct < PRICE_DROP_ALERT_PCT:
        return None

    severity = "high" if drop_pct >= 25.0 else "medium"
    headline = (
        f"District APMC mandi price decline ({drop_pct:0.1f}% drop below historical baseline)"
    )
    detail = (
        f"District modal wheat price at {checkpoint_label} is ₹{current_district_price:0.0f}/qtl, "
        f"reflecting a {drop_pct:0.1f}% decline below the historical monthly baseline of "
        f"₹{prior_mean:0.0f}/qtl. Lower expected harvest proceeds indicate heightened "
        "repayment stress risk."
    )

    return AlertItem(
        type="price_crash",
        severity=severity,
        status="open",
        detected_on=detected_on,
        checkpoint_label=checkpoint_label,
        plot_code=plot_code,
        season=season,
        headline=headline,
        detail=detail,
        supportive_action=SUPPORTIVE_ACTION_PRICE,
    )


class InSeasonAlertTracker:
    """De-duplication and severity escalation tracker for a plot across temporal checkpoints."""

    def __init__(self, plot_code: str, season: str) -> None:
        self.plot_code = plot_code
        self.season = season
        # Key: alert_type -> AlertItem
        self._active_alerts: dict[str, AlertItem] = {}
        self._history: list[AlertItem] = []

    @property
    def active_alerts(self) -> list[AlertItem]:
        """Return list of currently open/escalated alerts."""
        return list(self._active_alerts.values())

    def update_with_checkpoint_alerts(
        self,
        new_alerts: list[AlertItem],
    ) -> list[AlertItem]:
        """Incorporate alerts from a new checkpoint, enforcing de-duplication and escalation.

        Rules:
        - If alert type not active: add as new alert.
        - If alert type already active and new alert has higher severity: escalate.
        - If alert type already active and condition persists: preserve original detected_on.
        - If alert type was active but not present in new_alerts: mark as resolved.
        """
        severity_order: dict[str, int] = {"low": 1, "medium": 2, "high": 3}
        new_by_type = {a.type: a for a in new_alerts}

        updated_active: dict[str, AlertItem] = {}

        # 1. Update or escalate existing active alerts
        for alert_type, existing in self._active_alerts.items():
            if alert_type in new_by_type:
                new_candidate = new_by_type[alert_type]
                curr_rank = severity_order.get(existing.severity, 1)
                new_rank = severity_order.get(new_candidate.severity, 1)

                if new_rank > curr_rank:
                    # Escalation: update severity and detail, preserve original detected_on
                    escalated = AlertItem(
                        type=existing.type,
                        severity=new_candidate.severity,
                        status="open",
                        detected_on=existing.detected_on,
                        checkpoint_label=new_candidate.checkpoint_label,
                        plot_code=self.plot_code,
                        season=self.season,
                        headline=f"Escalated: {new_candidate.headline}",
                        detail=f"{new_candidate.detail} (Escalated from {existing.severity}).",
                        supportive_action=new_candidate.supportive_action,
                    )
                    updated_active[alert_type] = escalated
                else:
                    # Condition persists: keep existing active alert without creating duplicate
                    updated_active[alert_type] = existing
            else:
                # Condition normalized / resolved at this checkpoint
                resolved = AlertItem(
                    type=existing.type,
                    severity=existing.severity,
                    status="resolved",
                    detected_on=existing.detected_on,
                    checkpoint_label=existing.checkpoint_label,
                    plot_code=self.plot_code,
                    season=self.season,
                    headline=f"Resolved: {existing.headline}",
                    detail="Field conditions normalized at current checkpoint.",
                    supportive_action=existing.supportive_action,
                )
                self._history.append(resolved)

        # 2. Add brand new alerts
        for alert_type, new_alert in new_by_type.items():
            if alert_type not in updated_active:
                updated_active[alert_type] = new_alert

        self._active_alerts = updated_active
        return list(self._active_alerts.values())
