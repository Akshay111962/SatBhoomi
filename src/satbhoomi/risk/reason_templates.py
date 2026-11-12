"""Plain-language reason templates for risk score explanations (T-06).

Every feature in FEATURE_COLUMNS has a fixed English template grounded strictly
in observed row values. Templates follow PROJECT_CONTEXT.md ethical language rules:
- Use "farm stress", "repayment stress", and "support needed".
- Never describe a person's mental health or psychological state.
- No blame or judgment language.
- Assigned attributes (area_acre, irrigation, insured) explicitly state
  "as recorded by the officer".
"""

from typing import Any

from satbhoomi.features.config import FEATURE_COLUMNS

# Fixed wording constants per PROJECT_CONTEXT.md
OFFICER_RECORDED_PHRASE = "as recorded by the officer"


def _fmt_float(val: Any, decimals: int = 2) -> str:
    return f"{float(val):.{decimals}f}"


def _fmt_int(val: Any) -> str:
    return f"{int(round(float(val)))}"


def render_feature_reason(
    feature_name: str,
    value: Any,
    direction: str = "up",
    row_context: dict[str, Any] | None = None,
) -> str:
    """Render a grounded, plain-language English reason for a single feature.

    Args:
        feature_name: Name of the feature from FEATURE_COLUMNS.
        value: Observed non-missing value from the input row.
        direction: "up" if pushing farm stress risk up, "down" if protective,
            or "neutral" for contextual grounding.
        row_context: Optional full row dict for comparative grounding (e.g.
            comparing current NDVI to plot's own previous peak NDVI).

    Returns:
        Plain-language English sentence containing only numbers from the row.
    """
    if feature_name not in FEATURE_COLUMNS:
        raise ValueError(f"Unknown feature '{feature_name}' not in FEATURE_COLUMNS")

    ctx = row_context or {}

    if feature_name == "ndvi_early":
        v = _fmt_float(value, 2)
        prev_peak = ctx.get("prev_season_ndvi_peak")
        if prev_peak is not None and prev_peak == prev_peak:  # not NaN
            p_str = _fmt_float(prev_peak, 2)
            if direction == "up":
                return (
                    f"Early-season vegetation greenness (NDVI {v}) is low compared with "
                    f"the plot's prior peak ({p_str}), indicating early farm stress and "
                    f"possible support needed."
                )
            return (
                f"Early-season vegetation greenness (NDVI {v}, prior peak {p_str}) "
                f"shows steady initial crop establishment."
            )
        if direction == "up":
            return (
                f"Early-season vegetation greenness is low (NDVI {v}), indicating "
                f"early farm stress and possible support needed."
            )
        return f"Early-season vegetation greenness is healthy (NDVI {v})."

    if feature_name == "ndvi_pre_cutoff_mean":
        v = _fmt_float(value, 2)
        if direction == "up":
            return (
                f"Average vegetation greenness up to the cut-off date is low (NDVI {v}), "
                f"pointing to farm stress."
            )
        return f"Average vegetation greenness up to the cut-off date is {v} (NDVI)."

    if feature_name == "ndvi_pre_cutoff_std":
        v = _fmt_float(value, 3)
        if direction == "up":
            return (
                f"Vegetation greenness varied widely before the cut-off date "
                f"(NDVI standard deviation {v}), indicating uneven crop growth."
            )
        return (
            f"Vegetation greenness remained stable before the cut-off date "
            f"(NDVI standard deviation {v})."
        )

    if feature_name == "ndvi_trend_pre_cutoff":
        v = _fmt_float(value, 4)
        if direction == "up":
            return (
                f"Crop canopy growth trend up to the cut-off date is flat or declining "
                f"(NDVI slope {v} per day), signaling farm stress and support needed."
            )
        return (
            f"Crop canopy growth trend up to the cut-off date is positive (NDVI slope {v} per day)."
        )

    if feature_name == "rain_pre_cutoff_total_mm":
        v = _fmt_float(value, 1)
        if direction == "up":
            return (
                f"Cumulative rainfall up to the cut-off date was {v} mm, "
                f"contributing to moisture-related farm stress."
            )
        return f"Cumulative rainfall up to the cut-off date was {v} mm."

    if feature_name == "rain_pre_cutoff_deficit_pct":
        v = _fmt_float(value, 1)
        if direction == "up":
            return (
                f"Pre-cutoff rainfall departure is {v}% from normal, indicating "
                f"moisture deficit and potential farm stress."
            )
        return f"Pre-cutoff rainfall departure is {v}% from normal."

    if feature_name == "mandi_pre_cutoff_volatility":
        v = _fmt_float(value, 3)
        if direction == "up":
            return (
                f"Pre-cutoff mandi wheat price volatility is {v} (coefficient of "
                f"variation), increasing potential repayment stress."
            )
        return (
            f"Pre-cutoff mandi wheat price volatility is {v} (coefficient of "
            f"variation), indicating relatively stable market prices."
        )

    if feature_name == "past_stressed_seasons_count":
        v = _fmt_int(value)
        if direction == "up":
            return (
                f"Plot recorded {v} prior stressed season(s), indicating recurring "
                f"farm stress and potential support needed."
            )
        return f"Plot recorded {v} prior stressed season(s) in available history."

    if feature_name == "prev_season_ndvi_peak":
        v = _fmt_float(value, 2)
        if direction == "up":
            return (
                f"Previous season's peak vegetation greenness was {v} (NDVI), "
                f"associated with higher farm stress sensitivity."
            )
        return f"Previous season's peak vegetation greenness was {v} (NDVI)."

    if feature_name == "area_acre":
        v = _fmt_float(value, 2)
        return (
            f"Plot area is {v} acres ({OFFICER_RECORDED_PHRASE}), which factors "
            f"into repayment stress sensitivity."
        )

    if feature_name == "irrigation":
        irr_str = str(value).replace("_", " ")
        return (
            f"Irrigation source is {irr_str} ({OFFICER_RECORDED_PHRASE}), "
            f"affecting resilience to farm stress."
        )

    if feature_name == "insured":
        status_str = (
            "enrolled in crop insurance" if int(round(float(value))) == 1 else "not insured"
        )
        return (
            f"Plot is {status_str} (indicator {int(round(float(value)))}, "
            f"{OFFICER_RECORDED_PHRASE}), which relates to repayment stress buffer."
        )

    raise ValueError(f"No template defined for feature '{feature_name}'")  # pragma: no cover


# Explicit registry of supported template keys for completeness verification
TEMPLATE_FEATURES: tuple[str, ...] = tuple(FEATURE_COLUMNS)
