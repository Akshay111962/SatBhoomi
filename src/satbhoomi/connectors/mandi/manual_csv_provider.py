"""Manual CSV fallback provider for mandi price data."""

import csv
import logging
from datetime import datetime
from pathlib import Path

from satbhoomi.connectors.mandi.base import DailyMandiRecord, PriceProvider
from satbhoomi.connectors.satellite.base import SeasonWindow

logger = logging.getLogger(__name__)

DEFAULT_MANDI_CSV_PATH = Path("data/external/mandi_prices_wheat.csv")
REQUIRED_COLUMNS = {
    "date",
    "market",
    "state",
    "district",
    "commodity",
    "modal_price",
    "min_price",
    "max_price",
    "arrivals_tonnes",
}


class ManualCsvPriceProvider(PriceProvider):
    """Loads validated historical mandi price records from an external CSV file."""

    def __init__(self, csv_path: Path = DEFAULT_MANDI_CSV_PATH) -> None:
        self.csv_path = Path(csv_path)

    @property
    def source_name(self) -> str:
        return "manual_csv"

    def fetch_prices(
        self,
        crop: str,
        state: str,
        district: str,
        window: SeasonWindow,
    ) -> list[DailyMandiRecord]:
        """Load and filter daily mandi prices matching crop, district, and season window."""
        if not self.csv_path.exists():
            raise FileNotFoundError(
                f"Mandi price CSV file not found at '{self.csv_path}'. "
                f"Please ensure historical APMC prices are saved to {self.csv_path}."
            )

        records: list[DailyMandiRecord] = []
        with open(self.csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError(f"Empty CSV file at '{self.csv_path}'.")

            missing_cols = REQUIRED_COLUMNS - set(reader.fieldnames)
            if missing_cols:
                raise ValueError(f"Mandi CSV missing required columns: {sorted(missing_cols)}")

            for line_no, row in enumerate(reader, start=2):
                # Filter by commodity and district (case-insensitive)
                row_crop = row["commodity"].strip().lower()
                row_dist = row["district"].strip().lower()
                if row_crop != crop.strip().lower() or row_dist != district.strip().lower():
                    continue

                try:
                    obs_date = datetime.strptime(row["date"].strip(), "%Y-%m-%d").date()
                except ValueError as e:
                    raise ValueError(
                        f"Line {line_no}: Invalid date format '{row['date']}'. Expected YYYY-MM-DD."
                    ) from e

                if not window.contains(obs_date):
                    continue

                try:
                    modal = float(row["modal_price"].strip())
                except ValueError as e:
                    raise ValueError(
                        f"Line {line_no}: Invalid modal price '{row['modal_price']}'."
                    ) from e

                if modal <= 0:
                    raise ValueError(
                        f"Line {line_no}: Modal price {modal} must be strictly positive."
                    )

                min_p = (
                    float(row["min_price"].strip())
                    if row.get("min_price") and row["min_price"].strip()
                    else None
                )
                max_p = (
                    float(row["max_price"].strip())
                    if row.get("max_price") and row["max_price"].strip()
                    else None
                )
                arrivals = (
                    float(row["arrivals_tonnes"].strip())
                    if row.get("arrivals_tonnes") and row["arrivals_tonnes"].strip()
                    else None
                )

                records.append(
                    DailyMandiRecord(
                        date=obs_date,
                        market=row["market"].strip(),
                        state=row["state"].strip(),
                        district=row["district"].strip(),
                        commodity=row["commodity"].strip(),
                        modal_price=modal,
                        min_price=min_p,
                        max_price=max_p,
                        arrivals_tonnes=arrivals,
                        source=self.source_name,
                        metadata={"csv_line": line_no},
                    )
                )

        records.sort(key=lambda r: (r.date, r.market))
        return records
