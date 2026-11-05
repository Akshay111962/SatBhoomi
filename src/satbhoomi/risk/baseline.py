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
    """Heuristic agronomic rules baseline for wheat rabi.

    Combines early-season vegetative progression (ndvi_early <= 0.35 or
    ndvi_trend_pre_cutoff <= 0) and winter rainfall deficit (<= -20%)
    evaluated strictly on or before January 31:

    - Compound Stress (Condition 1 AND Condition 2): p_hat = 0.85
    - Partial Stress (Condition 1 OR Condition 2): p_hat = 0.45
    - Normal Growth (Neither Condition): p_hat = 0.10
    """

    def __init__(
        self,
        ndvi_early_threshold: float = 0.35,
        ndvi_trend_threshold: float = 0.0,
        rain_deficit_threshold_pct: float = -20.0,
    ) -> None:
        self.ndvi_early_threshold = ndvi_early_threshold
        self.ndvi_trend_threshold = ndvi_trend_threshold
        self.rain_deficit_threshold_pct = rain_deficit_threshold_pct
        self.classes_: np.ndarray = np.array([0, 1])

    def fit(self, X: Any, y: Any = None) -> "AgronomicRulesBaseline":
        """Fit method for compatibility with scikit-learn estimator interface."""
        return self

    def predict_proba(self, X: Any) -> np.ndarray:
        """Predict probabilities based on fixed agronomic thresholds.

        Args:
            X: Features DataFrame or 2D array. Must contain column names if DataFrame.

        Returns:
            2D numpy array of shape (n_samples, 2).
        """
        n_samples = len(X)
        probs = np.full(n_samples, 0.10, dtype=float)

        if isinstance(X, pd.DataFrame):
            cond1 = pd.Series(False, index=X.index)
            if "ndvi_early" in X.columns:
                cond1 = cond1 | (X["ndvi_early"] <= self.ndvi_early_threshold)
            if "ndvi_trend_pre_cutoff" in X.columns:
                cond1 = cond1 | (X["ndvi_trend_pre_cutoff"] <= self.ndvi_trend_threshold)

            cond2 = pd.Series(False, index=X.index)
            if "rain_pre_cutoff_deficit_pct" in X.columns:
                cond2 = X["rain_pre_cutoff_deficit_pct"] <= self.rain_deficit_threshold_pct

            compound = cond1 & cond2
            partial = (cond1 | cond2) & ~compound

            probs[compound.to_numpy()] = 0.85
            probs[partial.to_numpy()] = 0.45

        p0 = 1.0 - probs
        return np.column_stack([p0, probs])

    def predict(self, X: Any, threshold: float = 0.5) -> np.ndarray:
        """Predict binary class labels."""
        proba = self.predict_proba(X)[:, 1]
        return (proba >= threshold).astype(int)
