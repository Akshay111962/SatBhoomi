"""Machine Learning model wrappers and hyperparameter grids (T-05).

Implements three ML model candidates conforming to docs/EVAL_PROTOCOL.md:
1. Regularized Logistic Regression (StandardScaler + SimpleImputer + L2)
2. Shallow Random Forest Classifier
3. Shrinkage Extreme Gradient Boosting (XGBoost)

All models handle small-sample edge cases gracefully and expose pre-registered
hyperparameter grids for time-aware cross-validation.
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from satbhoomi.features.config import FEATURE_COLUMNS

# Categorical and numerical columns partitioning
CATEGORICAL_FEATURES: list[str] = ["irrigation"]
NUMERICAL_FEATURES: list[str] = [col for col in FEATURE_COLUMNS if col not in CATEGORICAL_FEATURES]

# Pre-registered hyperparameter search grids (docs/EVAL_PROTOCOL.md Section 4)
LOGREG_PARAM_GRID: dict[str, list[Any]] = {
    "classifier__C": [0.01, 0.1, 1.0, 10.0],
    "classifier__class_weight": ["balanced", None],
    "classifier__penalty": ["l2"],
}

RF_PARAM_GRID: dict[str, list[Any]] = {
    "classifier__n_estimators": [25, 50],
    "classifier__max_depth": [2, 3],
    "classifier__min_samples_split": [3, 5],
    "classifier__max_features": ["sqrt", 0.5],
}

XGB_PARAM_GRID: dict[str, list[Any]] = {
    "classifier__n_estimators": [20, 40],
    "classifier__max_depth": [2, 3],
    "classifier__learning_rate": [0.05, 0.1],
    "classifier__subsample": [0.8, 1.0],
    "classifier__colsample_bytree": [0.8, 1.0],
}


def create_preprocessor(scale_numeric: bool = True) -> ColumnTransformer:
    """Build preprocessor for feature pipelines.

    Args:
        scale_numeric: If True, applies StandardScaler to numerical features.

    Returns:
        Configured ColumnTransformer.
    """
    numeric_steps: list[tuple[str, Any]] = [
        ("imputer", SimpleImputer(strategy="median")),
    ]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))

    numeric_transformer = Pipeline(steps=numeric_steps)
    categorical_transformer = OneHotEncoder(handle_unknown="ignore", sparse_output=False)

    return ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, NUMERICAL_FEATURES),
            ("cat", categorical_transformer, CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )


class SafeClassifierWrapper(BaseEstimator, ClassifierMixin):
    """Wrapper that prevents solver crashes when training labels have only 1 class."""

    def __init__(
        self,
        base_estimator: BaseEstimator,
        scale_numeric: bool = True,
    ) -> None:
        self.base_estimator = base_estimator
        self.scale_numeric = scale_numeric
        self.pipeline_: Pipeline | None = None
        self.classes_: np.ndarray = np.array([0, 1])
        self.single_class_target_: int | None = None

    def fit(self, X: pd.DataFrame, y: Any) -> "SafeClassifierWrapper":
        """Fit pipeline, handling single-class edge case gracefully."""
        y_arr = np.asarray(y, dtype=int)
        unique_classes = np.unique(y_arr)

        if len(unique_classes) < 2:
            # When only 1 class is present, standard solvers fail.
            # Store the single class outcome directly.
            self.single_class_target_ = int(unique_classes[0]) if len(unique_classes) == 1 else 0
            self.pipeline_ = None
            return self

        self.single_class_target_ = None
        preprocessor = create_preprocessor(scale_numeric=self.scale_numeric)
        self.pipeline_ = Pipeline(
            steps=[
                ("preprocessor", preprocessor),
                ("classifier", self.base_estimator),
            ]
        )
        self.pipeline_.fit(X, y_arr)
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Predict class probabilities."""
        n_samples = len(X)
        if self.single_class_target_ is not None:
            # Deterministically predict 1.0 for the observed single class
            p1 = np.full(n_samples, float(self.single_class_target_), dtype=float)
            p0 = 1.0 - p1
            return np.column_stack([p0, p1])

        if self.pipeline_ is not None:
            return self.pipeline_.predict_proba(X)

        return np.full((n_samples, 2), 0.5)

    def predict(self, X: pd.DataFrame, threshold: float = 0.5) -> np.ndarray:
        """Predict binary labels."""
        proba = self.predict_proba(X)[:, 1]
        return (proba >= threshold).astype(int)

    def get_feature_importances(self) -> dict[str, float]:
        """Extract feature importances or standardized coefficients."""
        if self.pipeline_ is None:
            return {}

        classifier = self.pipeline_.named_steps["classifier"]
        preprocessor = self.pipeline_.named_steps["preprocessor"]

        # Extract transformed feature names
        try:
            feature_names = preprocessor.get_feature_names_out()
        except Exception:
            feature_names = [f"feat_{i}" for i in range(len(NUMERICAL_FEATURES))]

        if hasattr(classifier, "feature_importances_"):
            importances = classifier.feature_importances_
            total = float(np.sum(importances))
            norm = importances / total if total > 0 else importances
            return {name: float(val) for name, val in zip(feature_names, norm, strict=False)}

        if hasattr(classifier, "coef_"):
            coefs = np.abs(classifier.coef_[0])
            total = float(np.sum(coefs))
            norm = coefs / total if total > 0 else coefs
            return {name: float(val) for name, val in zip(feature_names, norm, strict=False)}

        return {}


def build_logistic_regression(
    C: float = 1.0,
    class_weight: Any = None,
    random_state: int = 42,
) -> SafeClassifierWrapper:
    """Build regularized Logistic Regression model."""
    estimator = LogisticRegression(
        C=C,
        class_weight=class_weight,
        solver="lbfgs",
        random_state=random_state,
        max_iter=1000,
    )
    return SafeClassifierWrapper(base_estimator=estimator, scale_numeric=True)


def build_random_forest(
    n_estimators: int = 25,
    max_depth: int = 2,
    min_samples_split: int = 3,
    max_features: Any = "sqrt",
    random_state: int = 42,
    n_jobs: int = 1,
) -> SafeClassifierWrapper:
    """Build shallow Random Forest model."""
    estimator = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        min_samples_split=min_samples_split,
        max_features=max_features,
        random_state=random_state,
        n_jobs=n_jobs,
    )
    return SafeClassifierWrapper(base_estimator=estimator, scale_numeric=False)


def build_xgboost(
    n_estimators: int = 20,
    max_depth: int = 2,
    learning_rate: float = 0.05,
    subsample: float = 1.0,
    colsample_bytree: float = 1.0,
    random_state: int = 42,
    n_jobs: int = 1,
) -> SafeClassifierWrapper:
    """Build shrinkage XGBoost model."""
    estimator = XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        random_state=random_state,
        eval_metric="logloss",
        n_jobs=n_jobs,
    )
    return SafeClassifierWrapper(base_estimator=estimator, scale_numeric=False)
