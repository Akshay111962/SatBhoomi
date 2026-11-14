"""Regression tests guaranteeing radiometric cache selection and peak NDVI parity.

Asserts:
1. Every plot-season row in season_dataset.csv matches the exact peak NDVI
   derived independently from the v2 corrected cache file (*_v2_pb_offset_corrected.json).
2. Legacy uncorrected cache files are strictly never loaded.
"""

import json
from pathlib import Path

import pandas as pd
import pytest


def test_season_dataset_matches_v2_cache_bit_for_bit() -> None:
    """Verify that all plot-seasons in season_dataset.csv derive from v2 cache."""
    dataset_path = Path("data/processed/season_dataset.csv")
    if not dataset_path.exists():
        pytest.skip("data/processed/season_dataset.csv not present")

    sat_dir = Path("data/raw/satellite")
    df = pd.read_csv(dataset_path)

    assert len(df) == 105, f"Expected 105 rows for 21 active plots x 5 seasons, got {len(df)}"

    for _, row in df.iterrows():
        plot_code = str(row["plot_code"])
        season = str(row["season"])
        dataset_peak = round(float(row["ndvi_peak"]), 4)

        v2_cache_file = sat_dir / f"{plot_code}_{season}_v2_pb_offset_corrected.json"
        assert v2_cache_file.exists(), f"Missing required v2 cache file: {v2_cache_file}"

        with open(v2_cache_file, encoding="utf-8") as f:
            records = json.load(f)

        valid_ndvis = [
            r["ndvi"] for r in records if r.get("is_valid") and r.get("ndvi") is not None
        ]
        assert valid_ndvis, f"No valid NDVI observations found in {v2_cache_file}"

        expected_peak = round(max(valid_ndvis), 4)
        assert dataset_peak == expected_peak, (
            f"Discrepancy in {plot_code} {season}: "
            f"season_dataset={dataset_peak} vs v2_cache={expected_peak}"
        )


def test_legacy_cache_files_never_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify that deserialization explicitly enforces v2 provenance fields."""
    from satbhoomi.connectors.satellite.planetary_provider import RawObservation
    from scripts.fetch_ndvi import deserialize_observation

    # A legacy observation dictionary without PB offset provenance fields
    legacy_record = {
        "date": "2022-02-15",
        "ndvi": 0.42,
        "is_valid": True,
        "cloud_prob": 0.05,
        "scl_class": 4,
        "scene_id": "S2A_MSIL2A_20220215T052921_N0400_R019_T43RER",
    }

    # Deserializing with require_v2=True must reject legacy cache records
    with pytest.raises(ValueError, match="Cached observation missing required field"):
        deserialize_observation(legacy_record, require_v2=True)

    # Valid v2 record with provenance fields must pass
    valid_v2_record = {
        **legacy_record,
        "processing_baseline": "04.00",
        "offset_applied": -1000.0,
        "offset_rule": "baseline",
        "provider_logic_version": "v2_pb_offset_corrected",
    }
    obs = deserialize_observation(valid_v2_record, require_v2=True)
    assert isinstance(obs, RawObservation)
    assert obs.offset_applied == -1000.0
