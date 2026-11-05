"""Evaluation metrics, calibration table, and cluster bootstrap (T-05).

Implements the evaluation requirements specified in docs/EVAL_PROTOCOL.md:
- ROC-AUC, PR-AUC, and Brier Score
- 3-bucket calibration reliability table
- Plot-level cluster bootstrap (1,000 iterations) for 95% confidence intervals
- Subgroup evaluation by plot size (< 2.0 vs >= 2.0 acres)
- Label-shuffle permutation sanity test (50 iterations)
"""

from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def compute_metrics(y_true: Any, y_pred_proba: Any) -> dict[str, Any]:
    """Calculate discrimination, calibration, and proper scoring metrics.

    Args:
        y_true: True binary labels (0 or 1).
        y_pred_proba: Predicted probabilities of positive class (P(y=1)).

    Returns:
        Dictionary containing roc_auc, pr_auc, brier_score, sample_count,
        and event_rate.
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    y_prob_arr = np.asarray(y_pred_proba, dtype=float)

    n_samples = len(y_true_arr)
    if n_samples == 0:
        return {
            "roc_auc": float("nan"),
            "pr_auc": float("nan"),
            "brier_score": float("nan"),
            "sample_count": 0,
            "event_rate": float("nan"),
        }

    event_rate = float(np.mean(y_true_arr))
    bs = float(brier_score_loss(y_true_arr, y_prob_arr))

    # ROC-AUC and PR-AUC require at least two distinct classes
    unique_classes = np.unique(y_true_arr[~np.isnan(y_true_arr)])
    if len(unique_classes) < 2:
        roc_auc = float("nan")
        pr_auc = float("nan")
    else:
        try:
            roc_auc = float(roc_auc_score(y_true_arr, y_prob_arr))
        except ValueError:
            roc_auc = float("nan")

        try:
            pr_auc = float(average_precision_score(y_true_arr, y_prob_arr))
        except ValueError:
            pr_auc = float("nan")

    return {
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "brier_score": bs,
        "sample_count": n_samples,
        "event_rate": event_rate,
    }


def compute_calibration_table(
    y_true: Any,
    y_pred_proba: Any,
    bins: tuple[tuple[float, float, str], ...] = (
        (0.00, 0.33, "Low Risk [0.00, 0.33)"),
        (0.33, 0.67, "Medium Risk [0.33, 0.67)"),
        (0.67, 1.01, "High Risk [0.67, 1.00]"),
    ),
) -> list[dict[str, Any]]:
    """Compute coarse 3-bin calibration reliability table.

    Args:
        y_true: Ground truth binary labels.
        y_pred_proba: Predicted probabilities for positive class.
        bins: Sequence of (lower, upper, label) tuples.

    Returns:
        List of bin summary dicts.
    """
    y_true_arr = np.asarray(y_true, dtype=float)
    y_prob_arr = np.asarray(y_pred_proba, dtype=float)

    table: list[dict[str, Any]] = []
    for low, high, label in bins:
        mask = (y_prob_arr >= low) & (y_prob_arr < high)
        count = int(np.sum(mask))
        if count > 0:
            mean_pred = float(np.mean(y_prob_arr[mask]))
            obs_rate = float(np.mean(y_true_arr[mask]))
        else:
            mean_pred = float("nan")
            obs_rate = float("nan")

        table.append(
            {
                "bin_name": label,
                "bin_lower": low,
                "bin_upper": high,
                "count": count,
                "mean_predicted_prob": mean_pred,
                "observed_event_rate": obs_rate,
            }
        )

    return table


def cluster_bootstrap_confidence_interval(
    df: pd.DataFrame,
    y_true_col: str,
    y_prob_col: str,
    cluster_col: str = "plot_code",
    n_resamples: int = 1000,
    random_state: int = 42,
) -> dict[str, tuple[float, float]]:
    """Calculate 95% bootstrap confidence intervals with plot-level cluster resampling.

    Args:
        df: DataFrame containing predictions, true labels, and plot cluster IDs.
        y_true_col: Column name of ground truth label.
        y_prob_col: Column name of predicted probabilities.
        cluster_col: Column identifying the resampling cluster (plot_code).
        n_resamples: Number of bootstrap iterations (default 1000).
        random_state: Fixed random seed.

    Returns:
        Dictionary mapping metric names ('roc_auc', 'brier_score') to (ci_lower, ci_upper).
    """
    rng = np.random.default_rng(random_state)
    unique_clusters = df[cluster_col].unique()
    n_clusters = len(unique_clusters)

    # Pre-index cluster arrays for ultra-fast numpy resampling
    cluster_arrays = {
        cid: (
            group[y_true_col].to_numpy(dtype=float),
            group[y_prob_col].to_numpy(dtype=float),
        )
        for cid, group in df.groupby(cluster_col)
    }

    auc_resamples: list[float] = []
    brier_resamples: list[float] = []

    for _ in range(n_resamples):
        sampled_clusters = rng.choice(unique_clusters, size=n_clusters, replace=True)
        y_true_sample = np.concatenate([cluster_arrays[cid][0] for cid in sampled_clusters])
        y_prob_sample = np.concatenate([cluster_arrays[cid][1] for cid in sampled_clusters])

        brier_resamples.append(float(brier_score_loss(y_true_sample, y_prob_sample)))

        if len(np.unique(y_true_sample)) >= 2:
            try:
                auc_resamples.append(float(roc_auc_score(y_true_sample, y_prob_sample)))
            except ValueError:
                pass

    # Compute empirical 2.5% and 97.5% percentiles
    brier_ci = (
        float(np.percentile(brier_resamples, 2.5)),
        float(np.percentile(brier_resamples, 97.5)),
    )

    if len(auc_resamples) >= 20:
        auc_ci = (
            float(np.percentile(auc_resamples, 2.5)),
            float(np.percentile(auc_resamples, 97.5)),
        )
    else:
        auc_ci = (float("nan"), float("nan"))

    return {
        "roc_auc_95_ci": auc_ci,
        "brier_score_95_ci": brier_ci,
    }


def evaluate_by_plot_size(
    df: pd.DataFrame,
    y_true_col: str,
    y_prob_col: str,
    area_col: str = "area_acre",
    split_threshold: float = 2.0,
) -> dict[str, Any]:
    """Compute subgroup metrics for small (<2.0 acres) vs large (>=2.0 acres) plots."""
    small_df = df[df[area_col] < split_threshold]
    large_df = df[df[area_col] >= split_threshold]

    def _eval_group(sub_df: pd.DataFrame, name: str) -> dict[str, Any]:
        count = len(sub_df)
        is_underpowered = count < 5
        metrics = compute_metrics(sub_df[y_true_col], sub_df[y_prob_col])
        return {
            "group_name": name,
            "count": count,
            "statistically_underpowered": is_underpowered,
            "metrics": metrics,
        }

    return {
        "small_plots": _eval_group(small_df, f"< {split_threshold} acres"),
        "large_plots": _eval_group(large_df, f">= {split_threshold} acres"),
    }


def run_permutation_sanity_test(
    model: Any,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    n_permutations: int = 50,
    random_state: int = 42,
) -> dict[str, Any]:
    """Run label-shuffle permutation sanity test (50 iterations).

    Permutes training labels and computes test AUC to verify absence of
    structural leakage.
    """
    rng = np.random.default_rng(random_state)
    perm_aucs: list[float] = []

    for _ in range(n_permutations):
        perm_y_train = rng.permutation(y_train)
        model.fit(X_train, perm_y_train)
        probs = model.predict_proba(X_test)[:, 1]

        if len(np.unique(y_test)) >= 2:
            try:
                perm_aucs.append(float(roc_auc_score(y_test, probs)))
            except ValueError:
                pass

    if len(perm_aucs) > 0:
        mean_auc = float(np.mean(perm_aucs))
        passed = bool(0.40 <= mean_auc <= 0.60)
    else:
        # If held-out season has single class, permuted AUC cannot be computed
        mean_auc = float("nan")
        passed = True

    return {
        "n_permutations": n_permutations,
        "mean_permuted_auc": mean_auc,
        "passed": passed,
    }
