"""District-level historical crop yield statistics loader and data validation."""

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from satbhoomi.connectors.satellite.seasons import parse_rabi_season_name

logger = logging.getLogger(__name__)

DEFAULT_YIELD_CSV_PATH = Path("data/external/district_yield_wheat.csv")
REQUIRED_YIELD_COLUMNS = {
    "district",
    "season",
    "area_ha",
    "production_tonnes",
    "yield_kg_per_ha",
    "source_name",
    "source_url",
    "retrieved_on",
}

# Physical bounds for irrigated/semi-irrigated wheat yield in India (kg/hectare)
# National averages range ~2500 - 3500 kg/ha; Punjab/Haryana peak ~5000 kg/ha.
# Severe drought/failure floor ~500 kg/ha; upper agro-climatic ceiling ~6000 kg/ha.
WHEAT_YIELD_MIN_BOUND_KG_HA = 500.0
WHEAT_YIELD_MAX_BOUND_KG_HA = 6000.0

# Tolerance threshold for verifying yield consistency:
# (production_tonnes * 1000 / area_ha) vs yield_kg_per_ha
MAX_YIELD_DISCREPANCY_RATIO = 0.01  # 1% discrepancy allowance for rounding


class YieldDataValidationError(ValueError):
    """Raised when district yield statistics violate required schema, format, or bounds."""

    pass


@dataclass(frozen=True)
class DistrictYieldRecord:
    """Historical administrative crop yield and production record for a district-season.

    IMPORTANT STATISTICAL LIMITATION:
    District yield represents an administrative, aggregate statistical average across
    an entire administrative unit (e.g. Anand district, ~50,000 hectares of wheat).
    It CANNOT represent plot-level ground truth or capture intra-district microclimate,
    soil variation, or individual management differences. In SatBhoomi, it serves strictly
    as an administrative regional baseline.
    """

    district: str
    season: str
    area_ha: float
    production_tonnes: float
    yield_kg_per_ha: float
    source_name: str
    source_url: str
    retrieved_on: str


def load_district_yield_records(
    csv_path: Path = DEFAULT_YIELD_CSV_PATH,
    district_filter: str | None = None,
) -> list[DistrictYieldRecord]:
    """Load and validate district crop yield records from CSV.

    Validates:
    1. CSV file existence and column header schema.
    2. Season name conforms to 'YYYY-YY' standard (e.g. '2021-22').
    3. Numeric columns (area_ha, production_tonnes, yield_kg_per_ha) are strictly positive.
    4. Physical plausibility bounds (500 to 6000 kg/ha for wheat in India).
    5. Mathematical consistency between area, production, and yield within 1% tolerance.

    Raises:
        YieldDataValidationError: If any validation checks fail.
    """
    path = Path(csv_path)
    if not path.exists():
        raise YieldDataValidationError(
            f"District yield data file not found at '{path}'.\n"
            "Action Required: Obtain official district yield statistics from:\n"
            "  1. Directorate of Agriculture, Government of Gujarat: https://dag.gujarat.gov.in\n"
            "  2. Directorate of Economics & Statistics (DESAg): https://desagri.gov.in\n"
            f"Populate {path} with columns: {sorted(REQUIRED_YIELD_COLUMNS)}"
        )

    records: list[DistrictYieldRecord] = []
    seen_district_seasons: set[tuple[str, str]] = set()

    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise YieldDataValidationError(f"Empty yield statistics file at '{path}'.")

        missing_cols = REQUIRED_YIELD_COLUMNS - set(reader.fieldnames)
        if missing_cols:
            raise YieldDataValidationError(
                f"District yield CSV missing required columns: {sorted(missing_cols)}"
            )

        for line_no, row in enumerate(reader, start=2):
            district = row["district"].strip()
            season = row["season"].strip()

            # Optional district filter
            if district_filter and district.lower() != district_filter.lower():
                continue

            # Validate season naming convention
            try:
                parse_rabi_season_name(season)
            except ValueError as e:
                raise YieldDataValidationError(
                    f"Line {line_no}: Invalid season format '{season}'. "
                    "Must follow 'YYYY-YY' standard (e.g. '2021-22')."
                ) from e

            # Check uniqueness of (district, season)
            key = (district.lower(), season)
            if key in seen_district_seasons:
                raise YieldDataValidationError(
                    f"Line {line_no}: Duplicate record for district '{district}' "
                    f"and season '{season}'."
                )
            seen_district_seasons.add(key)

            # Validate numeric values strictly positive
            try:
                area_ha = float(row["area_ha"].strip())
                production_tonnes = float(row["production_tonnes"].strip())
                yield_kg_per_ha = float(row["yield_kg_per_ha"].strip())
            except ValueError as e:
                raise YieldDataValidationError(
                    f"Line {line_no}: Non-numeric value in area/production/yield: {e}"
                ) from e

            if area_ha <= 0:
                raise YieldDataValidationError(
                    f"Line {line_no}: area_ha ({area_ha}) must be strictly positive."
                )
            if production_tonnes <= 0:
                raise YieldDataValidationError(
                    f"Line {line_no}: production_tonnes ({production_tonnes}) "
                    "must be strictly positive."
                )
            if yield_kg_per_ha <= 0:
                raise YieldDataValidationError(
                    f"Line {line_no}: yield_kg_per_ha ({yield_kg_per_ha}) "
                    "must be strictly positive."
                )

            # Plausibility range check [500, 6000] kg/ha
            if not (WHEAT_YIELD_MIN_BOUND_KG_HA <= yield_kg_per_ha <= WHEAT_YIELD_MAX_BOUND_KG_HA):
                raise YieldDataValidationError(
                    f"Line {line_no}: Reported wheat yield {yield_kg_per_ha} kg/ha falls outside "
                    f"plausible agro-climatic bounds "
                    f"[{WHEAT_YIELD_MIN_BOUND_KG_HA}, {WHEAT_YIELD_MAX_BOUND_KG_HA}]."
                )

            # Mathematical consistency check: yield = (production * 1000) / area
            calculated_yield = (production_tonnes * 1000.0) / area_ha
            discrepancy = abs(yield_kg_per_ha - calculated_yield) / calculated_yield
            if discrepancy > MAX_YIELD_DISCREPANCY_RATIO:
                raise YieldDataValidationError(
                    f"Line {line_no}: Reported yield {yield_kg_per_ha} kg/ha is inconsistent "
                    f"with area {area_ha} ha and production {production_tonnes} tonnes "
                    f"(calculated {calculated_yield:.1f} kg/ha, discrepancy "
                    f"{discrepancy * 100:.2f}% > {MAX_YIELD_DISCREPANCY_RATIO * 100}%)."
                )

            records.append(
                DistrictYieldRecord(
                    district=district,
                    season=season,
                    area_ha=area_ha,
                    production_tonnes=production_tonnes,
                    yield_kg_per_ha=yield_kg_per_ha,
                    source_name=row["source_name"].strip(),
                    source_url=row["source_url"].strip(),
                    retrieved_on=row["retrieved_on"].strip(),
                )
            )

    return records
