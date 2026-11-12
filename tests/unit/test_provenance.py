"""Unit tests for data provenance guards and inspection."""

from __future__ import annotations

import pandas as pd
import pytest

from satbhoomi.features.provenance import (
    enforce_non_fixture_sources,
    extract_source_counts,
    find_fixture_sources,
    format_provenance_summary,
)


def test_extract_and_format_provenance() -> None:
    """Verify source counting and summary string generation."""
    df = pd.DataFrame(
        {
            "ndvi_source": ["planetary", "planetary"],
            "rain_source": ["nasa_power", "nasa_power"],
            "price_source": ["manual_csv", "manual_csv"],
            "yield_source": ["Directorate of Agriculture", "Directorate of Agriculture"],
        }
    )
    counts = extract_source_counts(df)
    assert counts["ndvi_source"] == {"planetary": 2}
    assert counts["rain_source"] == {"nasa_power": 2}
    assert find_fixture_sources(counts) == []

    summary = format_provenance_summary(counts)
    assert "planetary=2" in summary
    assert "nasa_power=2" in summary


def test_enforce_non_fixture_sources_raises_when_fixture_present() -> None:
    """Verify ValueError is raised if any fixture source is present without flag."""
    counts = {
        "ndvi_source": {"planetary": 12},
        "rain_source": {"fixture": 12},
    }
    assert len(find_fixture_sources(counts)) == 1

    with pytest.raises(ValueError, match="Refusing to run on fixture-sourced data"):
        enforce_non_fixture_sources(counts, allow_fixture=False, context="build_dataset")

    # When allow_fixture=True, no exception is raised
    enforce_non_fixture_sources(counts, allow_fixture=True, context="build_dataset")
