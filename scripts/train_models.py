"""CLI script to train and evaluate baseline and ML models (T-05).

Executes model training per docs/EVAL_PROTOCOL.md, writes structured
evaluation results to reports/metrics.json, and writes the benchmark
report to docs/MODEL_EVAL.md.
"""

import json
import sys
from pathlib import Path

from satbhoomi.risk.train import train_and_evaluate_pipeline


def generate_markdown_report(result: dict) -> str:
    """Generate Markdown report for docs/MODEL_EVAL.md."""
    res = result["results"]
    lines = [
        "# SatBhoomi Model Evaluation and Benchmark Report (T-05)",
        "",
        f"**Model Version**: `{result['model_version']}`  ",
        f"**Dataset Hash**: `{result['data_hash']}`  ",
        f"**Evaluation Status**: `{result['criteria_status']}`  ",
        "",
        "---",
        "",
        "## 1. Executive Summary and Benchmark Findings",
        "",
        f"> **Scientific Narrative**:  \n> {result['narrative']}",
        "",
        "In accordance with our pre-registered evaluation protocol (`docs/EVAL_PROTOCOL.md`) and ",
        "Architecture Decision ADR-2 (*Rules baseline first, ML second*), all baseline heuristics ",
        "and ML models were evaluated under strict temporal isolation.",
        "",
        "---",
        "",
        "## 2. Held-Out Season Performance (Season: `2024-25`)",
        "",
        "| Model / Baseline | ROC-AUC | 95% Bootstrap CI | Brier Score | 95% Bootstrap CI |",
        "| :--- | :---: | :---: | :---: | :---: |",
    ]

    for model_name, m_data in res.items():
        metrics = m_data["metrics"]
        boot_ci = m_data["bootstrap_95_ci"]

        has_auc = not sys.float_info.min > metrics["roc_auc"] and str(metrics["roc_auc"]) != "nan"
        auc_str = f"{metrics['roc_auc']:.3f}" if has_auc else "N/A*"
        brier_str = f"{metrics['brier_score']:.4f}"

        auc_ci = boot_ci["roc_auc_95_ci"]
        brier_ci = boot_ci["brier_score_95_ci"]

        has_ci = str(auc_ci[0]) != "nan"
        auc_ci_str = f"[{auc_ci[0]:.3f}, {auc_ci[1]:.3f}]" if has_ci else "N/A*"
        brier_ci_str = f"[{brier_ci[0]:.4f}, {brier_ci[1]:.4f}]"

        lines.append(
            f"| `{model_name}` | {auc_str} | {auc_ci_str} | {brier_str} | {brier_ci_str} |"
        )

    lines.extend(
        [
            "",
            (
                "\\* *Note*: ROC-AUC cannot be mathematically computed when the held-out "
                "test season contains only a single observed class. Brier score provides "
                "the definitive probability calibration scoring rule."
            ),
            "",
            "---",
            "",
            "## 3. Calibration Reliability Table (Selected Model)",
            "",
            "| Risk Tier | Probability Range | Count | Mean Pred Prob | Observed Rate |",
            "| :--- | :---: | :---: | :---: | :---: |",
        ]
    )

    logreg_cal = res["logistic_regression"]["calibration_table"]
    for bin_row in logreg_cal:
        m_val = bin_row["mean_predicted_prob"]
        o_val = bin_row["observed_event_rate"]
        m_prob = f"{m_val:.3f}" if str(m_val) != "nan" else "N/A"
        o_rate = f"{o_val:.3f}" if str(o_val) != "nan" else "N/A"
        b_low, b_high = bin_row["bin_lower"], bin_row["bin_upper"]
        b_count = bin_row["count"]
        b_name = bin_row["bin_name"]
        lines.append(
            f"| {b_name} | [{b_low:.2f}, {b_high:.2f}) | {b_count} | {m_prob} | {o_rate} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 4. Forward-Chaining Cross-Validation (Inside Training Seasons)",
            "",
            "| Fold | Train Seasons | Val Season | Train N | Val N | LogReg Brier |",
            "| :-: | :--- | :---: | :-: | :-: | :-: |",
        ]
    )

    for fc in result["forward_chaining"]:
        train_s = ", ".join(fc["train_seasons"])
        val_s = fc["val_season"]
        t_cnt, v_cnt = fc["train_count"], fc["val_count"]
        b_score = fc["logreg_brier"]
        lines.append(
            f"| {fc['fold']} | {train_s} | `{val_s}` | {t_cnt} | {v_cnt} | {b_score:.4f} |"
        )

    perm = result["permutation_test"]
    lines.extend(
        [
            "",
            "---",
            "",
            "## 5. Leakage and Permutation Sanity Verification",
            "",
            (
                f"- **Label-Shuffle Permutation Test**: Passed: `{perm['passed']}` "
                f"(N={perm['n_permutations']}, Mean AUC={perm['mean_permuted_auc']})"
            ),
            "- **Cut-off Date Truncation**: All features strictly $\\le$ January 31.",
            f"- **Model Artifact Serialized**: `{result['artifact_path']}`",
            "",
        ]
    )

    return "\n".join(lines)


def main() -> None:
    """Run model training CLI."""
    print("Executing SatBhoomi model training and validation pipeline...")
    output_dir = Path("models")
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    result = train_and_evaluate_pipeline(
        features_csv_path="data/processed/features.csv",
        output_dir=output_dir,
        test_season="2024-25",
    )

    # Save metrics JSON
    metrics_path = reports_dir / "metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"Metrics saved to {metrics_path}")

    # Save Markdown Report
    doc_path = Path("docs/MODEL_EVAL.md")
    report_md = generate_markdown_report(result)
    with open(doc_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"Evaluation report written to {doc_path}")
    print(f"Selected model version: {result['model_version']}")
    print(f"Status: {result['criteria_status']}")


if __name__ == "__main__":
    main()
