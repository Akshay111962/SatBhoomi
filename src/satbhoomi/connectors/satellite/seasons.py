"""Cropping season temporal definitions and standards for SatBhoomi."""

from datetime import date

from satbhoomi.connectors.satellite.base import SeasonWindow


def format_rabi_season_name(start_year: int) -> str:
    """Format season standard string e.g. 2021 -> '2021-22'."""
    end_year_short = str(start_year + 1)[-2:]
    return f"{start_year}-{end_year_short}"


def parse_rabi_season_name(season_name: str) -> tuple[int, int]:
    """Parse season string 'YYYY-YY' into (start_year, end_year)."""
    parts = season_name.strip().split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
        raise ValueError(
            f"Invalid season format '{season_name}'. Expected 'YYYY-YY' (e.g. '2021-22')."
        )
    start_year = int(parts[0])
    century = parts[0][:2]
    end_year = int(f"{century}{parts[1]}")
    if end_year != start_year + 1:
        raise ValueError(
            f"Inconsistent season years in '{season_name}': {start_year} -> {end_year}"
        )
    return start_year, end_year


def get_rabi_season_window(start_year: int) -> SeasonWindow:
    """Return the standard Rabi wheat season window (Nov 1 to Apr 15)."""
    season_name = format_rabi_season_name(start_year)
    start_date = date(start_year, 11, 1)
    end_date = date(start_year + 1, 4, 15)
    return SeasonWindow(season_name=season_name, start_date=start_date, end_date=end_date)


def get_default_rabi_seasons(count: int = 5, latest_start_year: int = 2024) -> list[SeasonWindow]:
    """Return the last `count` completed Rabi seasons ending with latest_start_year.

    Default gives: 2020-21, 2021-22, 2022-23, 2023-24, 2024-25.
    """
    seasons: list[SeasonWindow] = []
    start_years = range(latest_start_year - count + 1, latest_start_year + 1)
    for yr in start_years:
        seasons.append(get_rabi_season_window(yr))
    return seasons
