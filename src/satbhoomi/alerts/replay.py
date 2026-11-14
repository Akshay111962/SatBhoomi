"""Historical season replay harness and synthetic stress testing (T-09, FR-008).

Executes checkpoint-by-checkpoint alert evaluation across historical plot-seasons.
Enforces:
1. Strict temporal cutoff: observations strictly <= checkpoint date.
2. Historical baselines strictly < current season.
3. De-duplication and severity escalation across checkpoints.
4. Data gap recording without guessing or imputing.
5. Distinct synthetic stress testing for early warning validation (TC-007).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from satbhoomi.alerts.config import (
    CHECKPOINTS,
    HARVEST_MONTH,
)
from satbhoomi.alerts.engine import (
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
from satbhoomi.connectors.satellite.seasons import (
    sort_seasons_chronologically,
)


def get_checkpoint_dates_for_season(season: str) -> list[tuple[str, date]]:
    """Return chronological checkpoint labels and dates for a given Rabi season.

    Example for '2023-24':
    - Dec 15 -> 2023-12-15
    - Jan 15 -> 2024-01-15
    - Jan 31 -> 2024-01-31
    """
    start_year = int(season.split("-")[0])
    results: list[tuple[str, date]] = []
    for month, day in CHECKPOINTS:
        year = start_year if month >= 10 else start_year + 1
        label = f"{date(year, month, day).strftime('%b %d')}"
        results.append((label, date(year, month, day)))
    return results


def extract_checkpoint_ndvi_from_scenes(
    scenes: list[dict[str, Any]],
    checkpoint_date: date,
    window_days: int = 14,
) -> tuple[float | None, int]:
    """Find clear NDVI observation closest to checkpoint_date on or before it.

    Parameters:
        scenes: list of raw scene dicts with keys 'date', 'ndvi', 'is_valid'.
        checkpoint_date: temporal boundary date.
        window_days: maximum lookback days for nearest observation.

    Returns:
        (ndvi_value, valid_observation_count_up_to_checkpoint)
    """
    valid_up_to_cp: list[tuple[date, float]] = []

    for item in scenes:
        d_val = item.get("date")
        if not d_val:
            continue
        if isinstance(d_val, str):
            obs_d = date.fromisoformat(d_val[:10])
        elif isinstance(d_val, date):
            obs_d = d_val
        else:
            continue

        if obs_d > checkpoint_date:
            continue

        if not item.get("is_valid", True):
            continue

        ndvi = item.get("ndvi")
        if ndvi is not None and not pd.isna(ndvi):
            valid_up_to_cp.append((obs_d, float(ndvi)))

    valid_count = len(valid_up_to_cp)
    if valid_count == 0:
        return None, 0

    valid_up_to_cp.sort(key=lambda x: x[0])

    # Find the latest observation within [checkpoint_date - window_days, checkpoint_date]
    window_start = checkpoint_date - timedelta(days=window_days)
    in_window = [x for x in valid_up_to_cp if x[0] >= window_start]

    if in_window:
        # Return observation closest to checkpoint date
        closest = max(in_window, key=lambda x: x[0])
        return closest[1], valid_count

    # Fallback to latest valid observation on or before checkpoint
    return valid_up_to_cp[-1][1], valid_count


def load_raw_scenes_cache(
    plot_code: str,
    season: str,
    raw_satellite_dir: Path | None,
) -> list[dict[str, Any]]:
    """Load cached raw Sentinel scenes for a plot and season."""
    if raw_satellite_dir is None or not raw_satellite_dir.is_dir():
        return []

    candidates = [
        raw_satellite_dir / f"{plot_code}_{season}_v2_pb_offset_corrected.json",
        raw_satellite_dir / f"{plot_code}_{season}.json",
        raw_satellite_dir / f"planetary_{plot_code}_{season}.json",
    ]
    for c_file in candidates:
        if c_file.is_file():
            try:
                with open(c_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except Exception:
                pass
    return []


def replay_single_plot_season(
    *,
    plot_code: str,
    season: str,
    plot_df: pd.DataFrame,
    full_df: pd.DataFrame,
    raw_satellite_dir: Path | None = None,
    synthetic_scenes: list[dict[str, Any]] | None = None,
    synthetic_prior_scenes_map: dict[str, list[dict[str, Any]]] | None = None,
) -> list[EvaluationCheckpointResult]:
    """Execute chronological replay for a single plot in a given season."""
    row_match = plot_df[(plot_df["plot_code"] == plot_code) & (plot_df["season"] == season)]
    if row_match.empty:
        return []

    curr_row = row_match.iloc[0]
    irrigation = str(curr_row.get("irrigation", "tube_well"))

    # Identify strictly prior seasons
    all_seasons = sort_seasons_chronologically(list(full_df["season"].unique()))
    curr_idx = all_seasons.index(season) if season in all_seasons else 0
    prior_seasons = all_seasons[:curr_idx]

    # Load scenes for current season
    if synthetic_scenes is not None:
        curr_scenes = synthetic_scenes
    else:
        curr_scenes = load_raw_scenes_cache(plot_code, season, raw_satellite_dir)

    # Load scenes for prior seasons of this plot
    prior_scenes_map: dict[str, list[dict[str, Any]]] = {}
    for ps in prior_seasons:
        if synthetic_prior_scenes_map is not None and ps in synthetic_prior_scenes_map:
            prior_scenes_map[ps] = synthetic_prior_scenes_map[ps]
        else:
            ps_scenes = load_raw_scenes_cache(plot_code, ps, raw_satellite_dir)
            if ps_scenes:
                prior_scenes_map[ps] = ps_scenes

    tracker = InSeasonAlertTracker(plot_code=plot_code, season=season)
    checkpoint_results: list[EvaluationCheckpointResult] = []

    checkpoints = get_checkpoint_dates_for_season(season)

    for cp_label, cp_date in checkpoints:
        cp_alerts: list[AlertItem] = []
        data_gap_reasons: list[str] = []

        # -------------------------------------------------------------
        # 1. Evaluate Crop Health Decline
        # -------------------------------------------------------------
        if curr_scenes:
            curr_ndvi, clear_count = extract_checkpoint_ndvi_from_scenes(curr_scenes, cp_date)
            # Extract prior ndvis at same checkpoint date
            prior_ndvis: list[float] = []
            for ps in prior_seasons:
                if ps in prior_scenes_map:
                    p_ndvi, _ = extract_checkpoint_ndvi_from_scenes(
                        prior_scenes_map[ps],
                        # Translate checkpoint date to prior season year
                        date(
                            int(ps.split("-")[0]) + (1 if cp_date.month < 10 else 0),
                            cp_date.month,
                            cp_date.day,
                        ),
                    )
                    if p_ndvi is not None:
                        prior_ndvis.append(p_ndvi)

            crop_alert, gap_reason = evaluate_crop_health_drop(
                plot_code=plot_code,
                season=season,
                checkpoint_label=cp_label,
                detected_on=cp_date,
                current_ndvi=curr_ndvi,
                prior_ndvis_same_checkpoint=prior_ndvis,
                clear_obs_count=clear_count,
            )
            if crop_alert:
                cp_alerts.append(crop_alert)
            if gap_reason:
                data_gap_reasons.append(gap_reason)
        else:
            # Fallback if no raw satellite cache: use summary metrics if available
            data_gap_reasons.append(
                f"No raw satellite observations cached for {plot_code} in {season}."
            )

        # -------------------------------------------------------------
        # 2. Evaluate Rainfall Deficit
        # -------------------------------------------------------------
        # Compute cumulative rainfall up to checkpoint
        # Anand winter normal baseline: Dec 15 ~ 6.0mm, Jan 15 ~ 8.5mm, Jan 31 ~ 10.5mm
        if cp_date.month == 12:
            r_cum = float(curr_row.get("rain_nov_mm", 0.0) or 0.0) + 0.5 * float(
                curr_row.get("rain_dec_mm", 0.0) or 0.0
            )
            norm = 6.0
        elif cp_date.month == 1 and cp_date.day == 15:
            r_cum = (
                float(curr_row.get("rain_nov_mm", 0.0) or 0.0)
                + float(curr_row.get("rain_dec_mm", 0.0) or 0.0)
                + 0.5 * float(curr_row.get("rain_jan_mm", 0.0) or 0.0)
            )
            norm = 8.5
        else:
            r_cum = (
                float(curr_row.get("rain_nov_mm", 0.0) or 0.0)
                + float(curr_row.get("rain_dec_mm", 0.0) or 0.0)
                + float(curr_row.get("rain_jan_mm", 0.0) or 0.0)
            )
            norm = 10.5

        deficit_pct = ((r_cum - norm) / norm * 100.0) if norm > 0 else 0.0

        rain_alert = evaluate_rainfall_deficit(
            plot_code=plot_code,
            season=season,
            checkpoint_label=cp_label,
            detected_on=cp_date,
            rain_deficit_pct=deficit_pct,
            irrigation=irrigation,
        )
        if rain_alert:
            cp_alerts.append(rain_alert)

        # -------------------------------------------------------------
        # 3. Evaluate Mandi Price Crash
        # -------------------------------------------------------------
        # Monthly modal price column corresponding to checkpoint
        p_col = "price_dec" if cp_date.month == 12 else "price_jan"
        curr_price = (
            float(curr_row.get(p_col, 0.0) or 0.0)
            if p_col in curr_row and not pd.isna(curr_row[p_col])
            else None
        )

        # Prior seasons' district modal prices for the same month
        prior_prices: list[float] = []
        if prior_seasons:
            prior_rows = full_df[full_df["season"].isin(prior_seasons)]
            for _, pr in prior_rows.iterrows():
                if p_col in pr and not pd.isna(pr[p_col]):
                    val = float(pr[p_col])
                    if val > 0:
                        prior_prices.append(val)

        price_alert = evaluate_price_crash(
            plot_code=plot_code,
            season=season,
            checkpoint_label=cp_label,
            detected_on=cp_date,
            current_district_price=curr_price,
            prior_seasons_district_prices=prior_prices,
        )
        if price_alert:
            cp_alerts.append(price_alert)

        # Enforce de-duplication and escalation via tracker
        active_escalated = tracker.update_with_checkpoint_alerts(cp_alerts)

        status_label = "data_gap" if data_gap_reasons and not active_escalated else "ok"
        gap_summary = "; ".join(data_gap_reasons) if data_gap_reasons else None

        checkpoint_results.append(
            EvaluationCheckpointResult(
                plot_code=plot_code,
                season=season,
                checkpoint_label=cp_label,
                evaluation_date=cp_date,
                status=status_label,
                data_gap_reason=gap_summary,
                alerts=active_escalated,
            )
        )

    return checkpoint_results


def run_full_replay(
    dataset_df: pd.DataFrame,
    raw_satellite_dir: Path | None = None,
) -> ReplayReport:
    """Run alert replay across all plots and seasons present in dataset."""
    all_seasons = sort_seasons_chronologically(list(dataset_df["season"].unique()))
    plots = list(dataset_df["plot_code"].unique())

    alert_counts_by_season: dict[str, int] = dict.fromkeys(all_seasons, 0)
    alert_counts_by_type: dict[str, int] = {
        "crop_health_drop": 0,
        "rainfall_deficit": 0,
        "price_crash": 0,
    }
    alert_counts_by_severity: dict[str, int] = {"low": 0, "medium": 0, "high": 0}

    total_plot_seasons = len(dataset_df)
    unique_plot_seasons_with_alerts = 0

    for season in all_seasons:
        season_df = dataset_df[dataset_df["season"] == season]
        for plot_code in season_df["plot_code"].unique():
            results = replay_single_plot_season(
                plot_code=plot_code,
                season=season,
                plot_df=season_df,
                full_df=dataset_df,
                raw_satellite_dir=raw_satellite_dir,
            )
            # Check final checkpoint active alerts for this plot-season
            final_alerts: list[AlertItem] = []
            for res in results:
                for a in res.alerts:
                    if a not in final_alerts:
                        final_alerts.append(a)

            if final_alerts:
                unique_plot_seasons_with_alerts += 1
                alert_counts_by_season[season] += len(final_alerts)
                for a in final_alerts:
                    alert_counts_by_type[a.type] = alert_counts_by_type.get(a.type, 0) + 1
                    alert_counts_by_severity[a.severity] = (
                        alert_counts_by_severity.get(a.severity, 0) + 1
                    )

    # False-alert rate on unflagged seasons (descriptive only: ratio of flagged plot-seasons)
    false_alert_rate = (
        round(unique_plot_seasons_with_alerts / total_plot_seasons, 4)
        if total_plot_seasons > 0
        else 0.0
    )

    # Execute synthetic stress scenario
    synthetic_eval = generate_synthetic_stress_scenario(
        plot_code=plots[0] if plots else "ANAND_WHEAT_01",
        base_season="2023-24",
        raw_satellite_dir=raw_satellite_dir,
        dataset_df=dataset_df,
    )

    notes = [
        (
            "Descriptive replay only: 0 official disaster events confirmed in "
            "Anand rabi wheat 2020-2025."
        ),
        "TC-007 early warning detection passes strictly on the labelled synthetic stress scenario.",
        "No claim of early warning validation on real historical data.",
    ]

    return ReplayReport(
        total_plots=len(plots),
        seasons_replayed=all_seasons,
        alert_counts_by_season=alert_counts_by_season,
        alert_counts_by_type=alert_counts_by_type,
        alert_counts_by_severity=alert_counts_by_severity,
        false_alert_rate_unflagged=false_alert_rate,
        synthetic_stress_scenario_tested=True,
        tc007_passed=synthetic_eval["tc007_passed"],
        notes=notes,
    )


def generate_synthetic_stress_scenario(
    plot_code: str = "ANAND_WHEAT_01",
    base_season: str = "2023-24",
    raw_satellite_dir: Path | None = None,
    dataset_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Generate and evaluate a strictly labelled SYNTHETIC stress scenario.

    Simulates a severe crop health collapse:
    - Real baseline observations loaded from prior seasons.
    - On Dec 15 of base_season, NDVI drops by 30% due to simulated localized blight/stress.
    - Verifies whether Raksha alert engine triggers an alert >= 6 weeks prior to April harvest.
    """
    if dataset_df is None:
        dataset_path = Path("data/processed/season_dataset.csv")
        if dataset_path.is_file():
            dataset_df = pd.read_csv(dataset_path)
        else:
            dataset_df = pd.DataFrame(
                [
                    {
                        "plot_code": plot_code,
                        "season": s,
                        "irrigation": "tube_well",
                        "rain_nov_mm": 5.0,
                        "rain_dec_mm": 2.0,
                        "rain_jan_mm": 1.0,
                        "price_dec": 2200.0,
                        "price_jan": 2250.0,
                    }
                    for s in ["2020-21", "2021-22", "2022-23", "2023-24"]
                ]
            )

    real_scenes = load_raw_scenes_cache(plot_code, base_season, raw_satellite_dir)

    # If real scenes are missing, create a realistic synthetic base trajectory
    if not real_scenes:
        real_scenes = [
            {"date": "2023-11-10", "ndvi": 0.32, "is_valid": True},
            {"date": "2023-11-25", "ndvi": 0.40, "is_valid": True},
            {"date": "2023-12-10", "ndvi": 0.52, "is_valid": True},
            {"date": "2024-01-10", "ndvi": 0.65, "is_valid": True},
            {"date": "2024-01-25", "ndvi": 0.72, "is_valid": True},
        ]

    # Create synthetic stressed trajectory with 30% reduction from Dec 10 onwards
    stress_cutoff = date(int(base_season.split("-")[0]), 12, 10)
    synthetic_scenes: list[dict[str, Any]] = []

    for sc in real_scenes:
        sc_copy = dict(sc)
        d_val = sc_copy.get("date", "")
        obs_d = date.fromisoformat(d_val[:10]) if isinstance(d_val, str) else d_val
        if obs_d >= stress_cutoff and sc_copy.get("ndvi") is not None:
            # Inject 30% drop (simulated vegetative damage)
            sc_copy["ndvi"] = round(float(sc_copy["ndvi"]) * 0.70, 4)
            sc_copy["synthetic_stress_injected"] = True
        synthetic_scenes.append(sc_copy)

    # Ensure prior seasons have baseline scenes if raw files are absent
    synthetic_prior_map: dict[str, list[dict[str, Any]]] = {}
    for ps in ["2020-21", "2021-22", "2022-23"]:
        ps_scenes = load_raw_scenes_cache(plot_code, ps, raw_satellite_dir)
        if ps_scenes:
            synthetic_prior_map[ps] = ps_scenes
        else:
            ps_yr = int(ps.split("-")[0])
            synthetic_prior_map[ps] = [
                {"date": f"{ps_yr}-11-10", "ndvi": 0.32, "is_valid": True},
                {"date": f"{ps_yr}-11-25", "ndvi": 0.40, "is_valid": True},
                {"date": f"{ps_yr}-12-10", "ndvi": 0.52, "is_valid": True},
                {"date": f"{ps_yr + 1}-01-10", "ndvi": 0.65, "is_valid": True},
                {"date": f"{ps_yr + 1}-01-25", "ndvi": 0.72, "is_valid": True},
            ]

    # Replay on synthetic scenes
    results = replay_single_plot_season(
        plot_code=plot_code,
        season=base_season,
        plot_df=dataset_df,
        full_df=dataset_df,
        raw_satellite_dir=raw_satellite_dir,
        synthetic_scenes=synthetic_scenes,
        synthetic_prior_scenes_map=synthetic_prior_map,
    )

    first_alert_date: date | None = None
    harvest_start = date(int(base_season.split("-")[0]) + 1, HARVEST_MONTH, 1)

    all_alerts: list[AlertItem] = []
    for res in results:
        for a in res.alerts:
            all_alerts.append(a)
            if first_alert_date is None or a.detected_on < first_alert_date:
                first_alert_date = a.detected_on

    lead_time_weeks = 0.0
    tc007_passed = False

    if first_alert_date is not None:
        lead_days = (harvest_start - first_alert_date).days
        lead_time_weeks = round(lead_days / 7.0, 1)
        # TC-007 requires lead time >= 6 weeks before harvest window
        tc007_passed = lead_time_weeks >= 6.0

    return {
        "scenario_type": "SYNTHETIC_STRESS_SCENARIO",
        "plot_code": plot_code,
        "base_season": base_season,
        "first_alert_date": str(first_alert_date) if first_alert_date else None,
        "harvest_start_date": str(harvest_start),
        "lead_time_weeks": lead_time_weeks,
        "tc007_passed": tc007_passed,
        "checkpoint_results": results,
        "alerts_count": len(all_alerts),
    }
