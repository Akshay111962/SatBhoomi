"""Baseline heuristic risk models (T-05).

Implements three transparent reference baselines:
1. Majority-Class / No-Skill Baseline: Predicts empirical training class prior.
2. Persistence Baseline: Assumes vegetative stress autocorrelation from t-1.
3. Agronomic Rules Baseline: Pre-cutoff NDVI vegetative lag and rain deficit rule.

Conforms to ADR-2: Rules baseline first, ML second.
"""

from typing import Any

import numpy as np
import pandas as pd

from satbhoomi.risk.config import (
    NDVI_DROP_ACUTE_PCT,
    NDVI_DROP_MODERATE_PCT,
    PROB_ACUTE_STRESS,
    PROB_MODERATE_STRESS,
    PROB_NORMAL,
    RAIN_DEFICIT_ACUTE_PCT,
    RAIN_DEFICIT_MODERATE_PCT,
    RAINFED_TYPES,
)


class MajorityClassBaseline:
    """Majority-class / no-skill baseline predictor.

    Predicts a constant empirical event probability equal to the training
    class prevalence: p_hat = mean(y_train).
    """

    def __init__(self) -> None:
        self.prior_: float = 0.5
        self.classes_: np.ndarray = np.array([0, 1])

    def fit(self, X: Any, y: Any) -> "MajorityClassBaseline":
        """Fit baseline on training targets.

        Args:
            X: Features (ignored for majority class).
            y: Target array-like of binary stress outcomes (0 or 1).

        Returns:
            Self instance.
        """
        y_arr = np.asarray(y, dtype=float)
        if len(y_arr) == 0:
            self.prior_ = 0.5
        else:
            self.prior_ = float(np.mean(y_arr))
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        """Predict class probabilities for samples in X.

        Args:
            X: Samples (array-like or DataFrame).

        Returns:
            2D numpy array of shape (n_samples, 2) where column 1 is P(stressed=1).
        """
        n_samples = len(X)
        p1 = np.full(n_samples, self.prior_, dtype=float)
        p0 = 1.0 - p1
        return np.column_stack([p0, p1])

    def predict(self, X: Any, threshold: float = 0.5) -> np.ndarray:
        """Predict binary class labels for samples in X.

        Args:
            X: Samples.
            threshold: Decision threshold for positive class.

        Returns:
            1D numpy array of binary predictions (0 or 1).
        """
        proba = self.predict_proba(X)[:, 1]
        return (proba >= threshold).astype(int)


class PersistenceBaseline:
    """Persistence (Markovian lag) baseline.

    Assigns high risk (0.80) if the plot suffered stress in the immediately
    preceding season (t-1), and low risk (0.20) otherwise.
    """

    def __init__(self, p_stressed: float = 0.80, p_healthy: float = 0.20) -> None:
        self.p_stressed = p_stressed
        self.p_healthy = p_healthy
        self.classes_: np.ndarray = np.array([0, 1])
        # History map: (plot_code, season) -> stress status (0 or 1)
        self.history_: dict[tuple[str, str], int] = {}

    def fit(self, X: Any, y: Any) -> "PersistenceBaseline":
        """Fit persistence history from training data.

        Args:
            X: Features DataFrame or array. If DataFrame with 'plot_code' and
               'season', records historical outcomes.
            y: Target array-like of binary stress outcomes.

        Returns:
            Self instance.
        """
        y_arr = np.asarray(y, dtype=int)
        if isinstance(X, pd.DataFrame) and "plot_code" in X.columns and "season" in X.columns:
            for (_, row), label in zip(X.iterrows(), y_arr, strict=False):
                self.history_[(str(row["plot_code"]), str(row["season"]))] = int(label)
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        """Predict class probabilities based on prior season stress.

        Args:
            X: Feature set. Can be a DataFrame containing 'past_stressed_seasons_count',
               or containing 'plot_code' and 'season'.

        Returns:
            2D numpy array of shape (n_samples, 2).
        """
        n_samples = len(X)
        probs = np.full(n_samples, self.p_healthy, dtype=float)

        if isinstance(X, pd.DataFrame):
            # Check if explicit prior season stress indicator is present
            if "prev_season_stressed" in X.columns:
                stressed_mask = X["prev_season_stressed"].astype(bool)
                probs[stressed_mask] = self.p_stressed
            elif "past_stressed_seasons_count" in X.columns:
                # If cumulative past stressed seasons > 0, proxy prior stress
                stressed_mask = X["past_stressed_seasons_count"] > 0
                probs[stressed_mask] = self.p_stressed

        p0 = 1.0 - probs
        return np.column_stack([p0, probs])

    def predict(self, X: Any, threshold: float = 0.5) -> np.ndarray:
        """Predict binary class labels."""
        proba = self.predict_proba(X)[:, 1]
        return (proba >= threshold).astype(int)


class AgronomicRulesBaseline:
    """Heuristic agronomic rules baseline for wheat rabi (v2.0 Relative Baseline).

    Evaluates relative vegetative lag against the plot's own strictly prior historical
    baseline and applies differentiated rainfall deficit accounting for irrigated vs
    rainfed tracts, strictly on or before January 31 (ADR-12, docs/SCORER_REVIEW.md).

    Thresholds and tiers (imported directly from satbhoomi.risk.config):
    - Acute Vegetative Collapse (relative drop >= 25.0%) OR
      Compound Distress (moderate drop >= 15.0% AND rainfed deficit <= -25.0%):
        p_hat = 0.85 (High Risk Band)
    - Moderate Stress (relative drop >= 15.0% OR rainfed deficit <= -25.0%):
        p_hat = 0.45 (Medium Risk Band)
    - Normal Growth (drop < 15.0% and no unbuffered moisture deficit):
        p_hat = 0.10 (Low Risk Band)
    """

    def __init__(
        self,
        ndvi_drop_moderate_pct: float = NDVI_DROP_MODERATE_PCT,
        ndvi_drop_acute_pct: float = NDVI_DROP_ACUTE_PCT,
        rain_deficit_moderate_pct: float = RAIN_DEFICIT_MODERATE_PCT,
        rain_deficit_acute_pct: float = RAIN_DEFICIT_ACUTE_PCT,
        prob_high: float = PROB_ACUTE_STRESS,
        prob_medium: float = PROB_MODERATE_STRESS,
        prob_low: float = PROB_NORMAL,
    ) -> None:
        self.ndvi_drop_moderate_pct = ndvi_drop_moderate_pct
        self.ndvi_drop_acute_pct = ndvi_drop_acute_pct
        self.rain_deficit_moderate_pct = rain_deficit_moderate_pct
        self.rain_deficit_acute_pct = rain_deficit_acute_pct
        self.prob_high = prob_high
        self.prob_medium = prob_medium
        self.prob_low = prob_low
        self.classes_: np.ndarray = np.array([0, 1])
        # History map: (plot_code, season) -> prior baseline mean
        self.baseline_history_: dict[tuple[str, str], float] = {}
        self.prior_seasons_count_: dict[tuple[str, str], int] = {}

    def fit(self, X: Any, y: Any = None) -> "AgronomicRulesBaseline":
        """Fit historical plot baselines across chronological seasons.

        Args:
            X: Features DataFrame. If containing 'plot_code', 'season', and
               'ndvi_pre_cutoff_mean', builds historical expanding baselines.
            y: Ignored (unsupervised agronomic heuristic).

        Returns:
            Self instance.
        """
        if isinstance(X, pd.DataFrame) and "plot_code" in X.columns and "season" in X.columns:
            for plot, group in X.groupby("plot_code"):
                sorted_group = group.sort_values("season")
                history: list[float] = []
                for _, row in sorted_group.iterrows():
                    season = str(row["season"])
                    val = row.get("ndvi_pre_cutoff_mean")
                    key = (str(plot), season)
                    self.prior_seasons_count_[key] = len(history)
                    if history:
                        self.baseline_history_[key] = float(np.mean(history))
                    if val is not None and not pd.isna(val):
                        history.append(float(val))
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        """Predict stress probabilities based on relative agronomic thresholds.

        Args:
            X: Features DataFrame or array. Evaluates vegetative lag relative
               to plot's own historical baseline and rainfed moisture deficits.

        Returns:
            2D numpy array of shape (n_samples, 2).
        """
        n_samples = len(X)
        probs = np.full(n_samples, self.prob_low, dtype=float)

        if isinstance(X, pd.DataFrame):
            for idx, (_, row) in enumerate(X.iterrows()):
                # Legacy synthetic test fixture fallback (when ndvi_pre_cutoff_mean is absent)
                if "ndvi_pre_cutoff_mean" not in row and (
                    "ndvi_early" in row or "ndvi_trend_pre_cutoff" in row
                ):
                    c1_early = float(row.get("ndvi_early", 1.0) or 1.0) <= 0.35
                    c1_trend = float(row.get("ndvi_trend_pre_cutoff", 1.0) or 1.0) <= 0.0
                    c1 = c1_early or c1_trend
                    c2 = float(row.get("rain_pre_cutoff_deficit_pct", 0.0) or 0.0) <= -20.0
                    if c1 and c2:
                        probs[idx] = self.prob_high
                    elif c1 or c2:
                        probs[idx] = self.prob_medium
                    else:
                        probs[idx] = self.prob_low
                    continue

                plot_code = str(row.get("plot_code", ""))
                season = str(row.get("season", ""))
                key = (plot_code, season)

                # 1. Determine prior baseline
                baseline = None
                n_prior = 0
                if "ndvi_pre_cutoff_baseline" in row and not pd.isna(
                    row["ndvi_pre_cutoff_baseline"]
                ):
                    baseline = float(row["ndvi_pre_cutoff_baseline"])
                    n_prior = int(row.get("prior_seasons_count", 1))
                elif "prior_ndvi_pre_cutoff_mean" in row and not pd.isna(
                    row["prior_ndvi_pre_cutoff_mean"]
                ):
                    baseline = float(row["prior_ndvi_pre_cutoff_mean"])
                    n_prior = int(row.get("prior_seasons_count", 1))
                elif key in self.baseline_history_:
                    baseline = self.baseline_history_[key]
                    n_prior = self.prior_seasons_count_.get(key, 0)

                # 2. Compute relative vegetative drop
                curr_ndvi = row.get("ndvi_pre_cutoff_mean")
                drop_pct = 0.0
                if (
                    baseline is not None
                    and baseline > 0.05
                    and curr_ndvi is not None
                    and not pd.isna(curr_ndvi)
                    and n_prior >= 1
                ):
                    drop_pct = (baseline - float(curr_ndvi)) / baseline * 100.0

                is_acute_veg = drop_pct >= self.ndvi_drop_acute_pct
                is_mod_veg = drop_pct >= self.ndvi_drop_moderate_pct

                # 3. Compute differentiated rainfall stress (rainfed only)
                irr = str(row.get("irrigation", "tube_well")).strip().lower()
                is_rainfed = irr in RAINFED_TYPES
                rain_def = row.get("rain_pre_cutoff_deficit_pct")
                is_rain_stress = False
                if is_rainfed and rain_def is not None and not pd.isna(rain_def):
                    is_rain_stress = float(rain_def) <= self.rain_deficit_moderate_pct

                # 4. Assign probability tier
                if is_acute_veg or (is_mod_veg and is_rain_stress):
                    probs[idx] = self.prob_high
                elif is_mod_veg or is_rain_stress:
                    probs[idx] = self.prob_medium
                else:
                    probs[idx] = self.prob_low

        p0 = 1.0 - probs
        return np.column_stack([p0, probs])

    def predict(self, X: Any, threshold: float = 0.5) -> np.ndarray:
        """Predict binary class labels."""
        proba = self.predict_proba(X)[:, 1]
        return (proba >= threshold).astype(int)
