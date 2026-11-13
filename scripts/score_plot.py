"""CLI script to score a single plot-season from features.csv (T-06).

Outputs a deterministic, zero-PII JSON RiskScoreResult using the active
AgronomicRulesBaseline scorer.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

from satbhoomi.risk.loan_suggestions import generate_loan_suggestion
from satbhoomi.risk.scoring import score_plot_season


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Score a single plot-season and print RiskScoreResult as JSON."
    )
    parser.add_argument(
        "--plot",
        default="ANAND_WHEAT_01",
        help="Plot code to score (default: ANAND_WHEAT_01).",
    )
    parser.add_argument(
        "--season",
        default="2024-25",
        help="Rabi season to score (default: 2024-25).",
    )
    parser.add_argument(
        "--features-csv",
        default="data/processed/features.csv",
        help="Path to features CSV (default: data/processed/features.csv).",
    )
    parser.add_argument(
        "--suggest-loan",
        action="store_true",
        help="Output right-sized loan limit band and repayment schedule suggestion (T-07).",
    )
    parser.add_argument(
        "--area-acre",
        type=float,
        default=2.5,
        help="Operational farm area in acres for loan sizing (default: 2.5).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run plot-season scoring CLI."""
    args = parse_args(argv)
    csv_path = Path(args.features_csv)
    if not csv_path.exists():
        print(f"Error: features file not found at {csv_path}", file=sys.stderr)
        return 1

    df = pd.read_csv(csv_path)
    matched = df[(df["plot_code"] == args.plot) & (df["season"] == args.season)]
    if matched.empty:
        print(
            f"Error: no row found for plot_code={args.plot!r}, season={args.season!r}",
            file=sys.stderr,
        )
        return 1

    row = matched.iloc[0]
    score_result = score_plot_season(row)

    if args.suggest_loan:
        irrigation = str(row.get("irrigation", "tube_well"))
        insured = bool(row.get("insured", 0))
        crop = str(row.get("crop", "wheat"))
        suggestion = generate_loan_suggestion(
            score_result,
            area_acre=args.area_acre,
            crop=crop,
            irrigation=irrigation,
            insured=insured,
        )
        print(suggestion.model_dump_json(indent=2))
    else:
        print(score_result.model_dump_json(indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
