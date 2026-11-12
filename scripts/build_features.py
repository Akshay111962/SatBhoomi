"""CLI script to build in-season features and proxy labels for farm credit underwriting (T-04).

Reads data/processed/season_dataset.csv, extracts pre-cutoff features (strictly <= Jan 31),
computes Option 1 expanding-baseline proxy labels, and exports data/processed/features.csv.
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    sys.path.insert(0, str(PROJECT_ROOT))

from satbhoomi.features import (  # noqa: E402
    FEATURE_COLUMNS,
    LABEL_COLUMNS,
    METADATA_COLUMNS,
    FeaturePipelineConfig,
    build_feature_dataset,
)
from satbhoomi.features.provenance import (  # noqa: E402
    enforce_non_fixture_sources,
    extract_source_counts,
    format_provenance_summary,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_features")

DEFAULT_INPUT_CSV = PROJECT_ROOT / "data" / "processed" / "season_dataset.csv"
DEFAULT_OUTPUT_CSV = PROJECT_ROOT / "data" / "processed" / "features.csv"
DEFAULT_RAW_SAT_DIR = PROJECT_ROOT / "data" / "raw" / "satellite"


def main() -> int:
    """Run feature engineering and proxy label pipeline."""
    parser = argparse.ArgumentParser(
        description="Build in-season features and proxy labels for wheat rabi plots."
    )
    parser.add_argument(
        "--input-csv",
        type=Path,
        default=DEFAULT_INPUT_CSV,
        help="Path to input seasonal dataset CSV (default: data/processed/season_dataset.csv)",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help="Path to output features CSV (default: data/processed/features.csv)",
    )
    parser.add_argument(
        "--raw-sat-dir",
        type=Path,
        default=DEFAULT_RAW_SAT_DIR,
        help="Path to raw satellite observations JSON directory",
    )
    parser.add_argument(
        "--drop-threshold",
        type=float,
        default=15.0,
        help="Percentage drop below prior historical baseline to label as stressed (default: 15.0)",
    )
    parser.add_argument(
        "--allow-fixture",
        action="store_true",
        help="Explicitly allow fixture-sourced data (blocked by default).",
    )
    args = parser.parse_args()

    if not args.input_csv.is_file():
        logger.error("Input seasonal dataset not found at %s", args.input_csv)
        return 1

    logger.info("Loading seasonal dataset from %s", args.input_csv)
    season_df = pd.read_csv(args.input_csv)
    logger.info("Loaded %d rows across %d seasons", len(season_df), season_df["season"].nunique())

    source_counts = extract_source_counts(season_df)
    logger.info("%s", format_provenance_summary(source_counts))
    try:
        enforce_non_fixture_sources(
            source_counts,
            allow_fixture=args.allow_fixture,
            context="build_features",
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    config = FeaturePipelineConfig(drop_threshold_pct=args.drop_threshold)
    sat_dir = args.raw_sat_dir if args.raw_sat_dir.is_dir() else None

    logger.info("Executing pre-cutoff feature extraction (Cutoff: Jan 31)...")
    feat_df = build_feature_dataset(season_df, config=config, raw_satellite_dir=sat_dir)

    # Save output features CSV
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    feat_df.to_csv(args.output_csv, index=False)
    logger.info("Successfully exported features dataset to %s", args.output_csv)

    # Print summary statistics
    total_rows = len(feat_df)
    labelled_mask = ~feat_df["label_unavailable"]
    labelled_count = int(labelled_mask.sum())
    unlabelled_count = total_rows - labelled_count

    print("\n" + "=" * 70)
    print("SATBHOOMI FEATURE PIPELINE SUMMARY (T-04)")
    print("=" * 70)
    print(f"Total Rows:                {total_rows}")
    print(f"Labelled Rows:             {labelled_count}")
    print(f"Unlabelled Rows (History): {unlabelled_count} (Flagged with label_unavailable=True)")
    print(f"Metadata Columns ({len(METADATA_COLUMNS)}):    {METADATA_COLUMNS}")
    print(f"Feature Columns ({len(FEATURE_COLUMNS)}):     {FEATURE_COLUMNS}")
    print(f"Label Columns ({len(LABEL_COLUMNS)}):       {LABEL_COLUMNS}")

    print("\n--- Class Balance per Season ---")
    for season_name, s_group in feat_df.groupby("season", sort=False):
        s_labelled = s_group[~s_group["label_unavailable"]]
        if s_labelled.empty:
            print(f"  Season {season_name}: 0 labelled rows (Historical initialization year)")
        else:
            s_stressed = int((s_labelled["stressed"] == 1).sum())
            s_normal = len(s_labelled) - s_stressed
            pct_stressed = (s_stressed / len(s_labelled)) * 100.0
            print(
                f"  Season {season_name}: {len(s_labelled)} labelled | "
                f"Stressed: {s_stressed} ({pct_stressed:.1f}%) | "
                f"Normal: {s_normal} ({100.0 - pct_stressed:.1f}%)"
            )

    print("\n--- Missing Values per Feature Column ---")
    missing_counts = feat_df[FEATURE_COLUMNS].isnull().sum()
    for col, null_n in missing_counts.items():
        flag = " [!] GAPS PRESERVED" if null_n > 0 else " [OK] Complete"
        print(f"  {col:<30}: {null_n:>3} missing{flag}")

    print("=" * 70 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
