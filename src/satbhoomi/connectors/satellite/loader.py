"""Loader and schema validation for synthetic sample plot coordinates."""

import csv
from pathlib import Path

from satbhoomi.connectors.satellite.base import PlotLocation

# Geographic boundary constraints for mainland India
INDIA_LAT_MIN: float = 6.0
INDIA_LAT_MAX: float = 38.0
INDIA_LON_MIN: float = 68.0
INDIA_LON_MAX: float = 98.0

# Allowable buffer radius around plot centroid in meters
BUFFER_M_MIN: float = 30.0
BUFFER_M_MAX: float = 200.0


def validate_plot_record(plot: PlotLocation) -> None:
    """Validate spatial boundaries and buffer limits for a plot.

    Raises:
        ValueError: If coordinates or buffer violate geographical and physical rules.
    """
    if not (INDIA_LAT_MIN <= plot.lat <= INDIA_LAT_MAX):
        raise ValueError(
            f"Plot '{plot.plot_code}' latitude {plot.lat} outside India bounds "
            f"[{INDIA_LAT_MIN}, {INDIA_LAT_MAX}]."
        )
    if not (INDIA_LON_MIN <= plot.lon <= INDIA_LON_MAX):
        raise ValueError(
            f"Plot '{plot.plot_code}' longitude {plot.lon} outside India bounds "
            f"[{INDIA_LON_MIN}, {INDIA_LON_MAX}]."
        )
    if not (BUFFER_M_MIN <= plot.buffer_m <= BUFFER_M_MAX):
        raise ValueError(
            f"Plot '{plot.plot_code}' buffer_m {plot.buffer_m} must be between "
            f"{BUFFER_M_MIN} and {BUFFER_M_MAX} meters."
        )


def load_sample_plots(csv_path: str | Path) -> list[PlotLocation]:
    """Read and validate sample plot centroid records from CSV.

    Args:
        csv_path: Path to sample_plots.csv.

    Returns:
        List of validated PlotLocation instances.

    Raises:
        FileNotFoundError: If the file is missing.
        ValueError: If headers are missing, coordinates invalid, or duplicate plot codes found.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Sample plots file not found: {path}")

    required_columns = {"plot_code", "lat", "lon", "buffer_m", "crop", "district"}
    plots: list[PlotLocation] = []
    seen_codes: set[str] = set()

    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Empty or corrupted CSV file: {path}")

        missing_cols = required_columns - set(reader.fieldnames)
        if missing_cols:
            raise ValueError(f"CSV missing required columns: {sorted(missing_cols)}")

        for row_num, row in enumerate(reader, start=2):
            code = (row.get("plot_code") or "").strip()
            if not code:
                raise ValueError(f"Row {row_num}: missing plot_code")

            if code in seen_codes:
                raise ValueError(f"Duplicate plot_code detected at row {row_num}: '{code}'")
            seen_codes.add(code)

            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
                buffer_m = float(row.get("buffer_m", 50.0))
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Row {row_num} ('{code}'): invalid coordinate or buffer: {e}"
                ) from e

            insured_raw = row.get("insured", "0")
            insured = 1 if str(insured_raw).strip() in {"1", "true", "True"} else 0

            plot = PlotLocation(
                plot_code=code,
                lat=lat,
                lon=lon,
                buffer_m=buffer_m,
                crop=(row.get("crop") or "wheat").strip(),
                irrigation=(row.get("irrigation") or None),
                insured=insured,
                district=(row.get("district") or "Anand").strip(),
            )
            validate_plot_record(plot)
            plots.append(plot)

    if not plots:
        raise ValueError(f"No plot records found in {path}")

    return plots
