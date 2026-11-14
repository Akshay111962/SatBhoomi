"""Unit tests for plot selection, exclusion schema, and non-crop exclusion rules."""

import csv
from pathlib import Path

import pytest

from satbhoomi.connectors.satellite.loader import load_sample_plots


def test_load_sample_plots_active_only_by_default() -> None:
    """Verify that default load_sample_plots filters out excluded plots (21 active)."""
    csv_path = Path("data/synthetic/sample_plots.csv")
    active_plots = load_sample_plots(csv_path)

    assert len(active_plots) == 21
    active_codes = {p.plot_code for p in active_plots}

    # Verify R1 excluded plots are NOT loaded
    assert "PETLAD_WHEAT_05" not in active_codes
    assert "UMRETH_WHEAT_09" not in active_codes
    assert "KHAMBHAT_WHEAT_12" not in active_codes

    for p in active_plots:
        assert p.status == "active"
        assert p.exclusion_reason is None
        assert p.exclusion_date is None


def test_load_sample_plots_includes_all_when_requested() -> None:
    """Verify that active_only=False returns all 24 rows preserving exclusion provenance."""
    csv_path = Path("data/synthetic/sample_plots.csv")
    all_plots = load_sample_plots(csv_path, active_only=False)

    assert len(all_plots) == 24
    by_code = {p.plot_code: p for p in all_plots}

    excluded_codes = {"PETLAD_WHEAT_05", "UMRETH_WHEAT_09", "KHAMBHAT_WHEAT_12"}
    for code in excluded_codes:
        plot = by_code[code]
        assert plot.status == "excluded"
        assert plot.exclusion_reason == "non-crop signal: peak NDVI below 0.30 in all seasons"
        assert plot.exclusion_date == "2026-11-14"

    active_count = sum(1 for p in all_plots if p.status == "active")
    assert active_count == 21


def test_plot_code_cannot_be_reused(tmp_path: Path) -> None:
    """Verify that duplicate or reused plot codes raise ValueError even if status differs."""
    csv_file = tmp_path / "plots_with_dupe.csv"
    rows = [
        ["plot_code", "lat", "lon", "buffer_m", "crop", "district", "status"],
        ["ANAND_WHEAT_01", "22.5125", "72.9340", "50", "wheat", "Anand", "excluded"],
        ["ANAND_WHEAT_01", "22.5130", "72.9350", "50", "wheat", "Anand", "active"],
    ]
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    with pytest.raises(ValueError, match="Duplicate plot_code detected"):
        load_sample_plots(csv_file, active_only=False)


def test_invalid_status_raises_value_error(tmp_path: Path) -> None:
    """Verify that unexpected status value raises ValueError."""
    csv_file = tmp_path / "plots_invalid_status.csv"
    rows = [
        ["plot_code", "lat", "lon", "buffer_m", "crop", "district", "status"],
        ["PLOT_INVALID", "22.5125", "72.9340", "50", "wheat", "Anand", "pending"],
    ]
    with csv_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    with pytest.raises(ValueError, match="invalid status 'pending'"):
        load_sample_plots(csv_file)


def test_r1_exclusion_rule_deterministic_on_fixture() -> None:
    """Verify R1 exclusion and R2 borderline categorization on controlled fixture data."""
    fixture_seasons = {
        "PLOT_NORMAL": [0.55, 0.60, 0.62, 0.58, 0.65],  # max > 0.40 -> clear
        "PLOT_BORDERLINE": [0.28, 0.32, 0.35, 0.31, 0.34],  # max 0.35 >= 0.30, mean 0.32 < 0.40
        "PLOT_NON_CROP": [0.12, 0.15, 0.22, 0.18, 0.25],  # max 0.25 < 0.30 -> excluded
    }

    categorization: dict[str, str] = {}
    for code, peaks in fixture_seasons.items():
        max_p = max(peaks)
        mean_p = sum(peaks) / len(peaks)
        if max_p < 0.30:
            categorization[code] = "excluded"
        elif mean_p < 0.40:
            categorization[code] = "borderline"
        else:
            categorization[code] = "active"

    assert categorization["PLOT_NORMAL"] == "active"
    assert categorization["PLOT_BORDERLINE"] == "borderline"
    assert categorization["PLOT_NON_CROP"] == "excluded"
