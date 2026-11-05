"""Proxy ground-truth crop stress label generator (T-04).

Builds the 'stressed' proxy label from full-season outcome data using
Option 1: Expanding Historical Baseline (strictly prior completed seasons only).
Rows without sufficient prior history are explicitly flagged with
'label_unavailable=True' and are never silently dropped or imputed.
"""

import pandas as pd

from satbhoomi.connectors.satellite.seasons import sort_seasons_chronologically
from satbhoomi.features.config import (
    DEFAULT_LABEL_DROP_THRESHOLD_PCT,
    DEFAULT_MIN_PRIOR_SEASONS,
    LABEL_COLUMNS,
)


def compute_proxy_labels(
    df: pd.DataFrame,
    drop_threshold_pct: float = DEFAULT_LABEL_DROP_THRESHOLD_PCT,
    min_prior_seasons: int = DEFAULT_MIN_PRIOR_SEASONS,
    plot_col: str = "plot_code",
    season_col: str = "season",
    peak_col: str = "ndvi_peak",
) -> pd.DataFrame:
    """Compute expanding-baseline proxy stress labels for each plot-season.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing at least plot_code, season, and ndvi_peak columns.
    drop_threshold_pct : float, optional
        Percentage drop below prior historical baseline to classify as stressed. Default is 15.0%.
    min_prior_seasons : int, optional
        Minimum number of strictly earlier completed seasons required to form a valid baseline.
        Default is 1.
    plot_col : str, optional
        Column name for plot identifier.
    season_col : str, optional
        Column name for season identifier.
    peak_col : str, optional
        Column name for outcome peak NDVI.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: plot_code, season, stressed, label_unavailable,
        peak_drop_pct, historical_baseline_ndvi.
    """
    required_cols = {plot_col, season_col, peak_col}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Input DataFrame is missing required columns: {sorted(missing)}")

    # Make working copy to prevent mutating caller's data
    work_df = df[[plot_col, season_col, peak_col]].copy()

    # Determine unique seasons and sort them chronologically
    unique_seasons = list(work_df[season_col].unique())
    sorted_seasons = sort_seasons_chronologically(unique_seasons)
    season_rank_map = {s: rank for rank, s in enumerate(sorted_seasons)}

    work_df["_season_rank"] = work_df[season_col].map(season_rank_map)
    work_df = work_df.sort_values([plot_col, "_season_rank"]).reset_index(drop=True)

    results: list[dict[str, object]] = []

    for plot_id, group in work_df.groupby(plot_col, sort=False):
        peaks = group[peak_col].tolist()
        seasons = group[season_col].tolist()

        for idx, (season_name, current_peak) in enumerate(zip(seasons, peaks, strict=True)):
            prior_peaks = [p for p in peaks[:idx] if p is not None and not pd.isna(p)]

            if len(prior_peaks) < min_prior_seasons:
                # Insufficient historical baseline
                results.append(
                    {
                        plot_col: plot_id,
                        season_col: season_name,
                        "stressed": None,
                        "label_unavailable": True,
                        "peak_drop_pct": None,
                        "historical_baseline_ndvi": None,
                    }
                )
            else:
                baseline = float(sum(prior_peaks) / len(prior_peaks))
                baseline = round(baseline, 4)

                if baseline <= 0 or current_peak is None or pd.isna(current_peak):
                    results.append(
                        {
                            plot_col: plot_id,
                            season_col: season_name,
                            "stressed": None,
                            "label_unavailable": True,
                            "peak_drop_pct": None,
                            "historical_baseline_ndvi": baseline,
                        }
                    )
                else:
                    curr_float = float(current_peak)
                    drop_pct = round(((baseline - curr_float) / baseline) * 100.0, 2)
                    is_stressed = 1 if drop_pct >= drop_threshold_pct else 0

                    results.append(
                        {
                            plot_col: plot_id,
                            season_col: season_name,
                            "stressed": is_stressed,
                            "label_unavailable": False,
                            "peak_drop_pct": drop_pct,
                            "historical_baseline_ndvi": baseline,
                        }
                    )

    res_df = pd.DataFrame(results)
    output_cols = [plot_col, season_col] + LABEL_COLUMNS
    return res_df[output_cols]
