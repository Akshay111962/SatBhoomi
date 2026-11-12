"""Data provenance inspection and fixture-data guard utilities."""

from __future__ import annotations

import pandas as pd

SOURCE_COLUMNS: tuple[str, ...] = (
    "ndvi_source",
    "rain_source",
    "price_source",
    "yield_source",
)


def extract_source_counts(df: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Return value counts per provenance source column present in df."""
    counts: dict[str, dict[str, int]] = {}
    for col in SOURCE_COLUMNS:
        if col in df.columns:
            vc = df[col].fillna("missing").astype(str).value_counts()
            counts[col] = {str(k): int(v) for k, v in vc.items()}
    return counts


def format_provenance_summary(source_counts: dict[str, dict[str, int]]) -> str:
    """Format a human-readable provenance summary block."""
    if not source_counts:
        return "Data Provenance: (no *_source columns present)"
    lines = ["Data Provenance (Input Column Sources):"]
    for col, dist in source_counts.items():
        parts = ", ".join(f"{src}={cnt}" for src, cnt in dist.items())
        lines.append(f"  - {col}: {parts}")
    return "\n".join(lines)


def find_fixture_sources(source_counts: dict[str, dict[str, int]]) -> list[str]:
    """Return list of source columns containing 'fixture' entries."""
    flagged: list[str] = []
    for col, dist in source_counts.items():
        if any(src.strip().lower() == "fixture" and cnt > 0 for src, cnt in dist.items()):
            flagged.append(f"{col}={dist}")
    return flagged


def enforce_non_fixture_sources(
    source_counts: dict[str, dict[str, int]],
    *,
    allow_fixture: bool,
    context: str,
) -> None:
    """Raise ValueError if fixture-sourced data is present without --allow-fixture."""
    flagged = find_fixture_sources(source_counts)
    if flagged and not allow_fixture:
        joined = "; ".join(flagged)
        raise ValueError(
            f"[{context}] Refusing to run on fixture-sourced data ({joined}). "
            "Replace fixture inputs with live/real data or pass --allow-fixture explicitly."
        )
