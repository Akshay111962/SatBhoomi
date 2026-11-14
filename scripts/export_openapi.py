#!/usr/bin/env python3
"""Export deterministic OpenAPI specification for SatBhoomi API contract v1 (T-10 / Section 8).

Usage:
    python scripts/export_openapi.py [--output PATH]

Example:
    python scripts/export_openapi.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from satbhoomi.api.main import API_CONTRACT_VERSION, app


def export_openapi(output_path: Path) -> None:
    """Generate and write sorted, deterministic OpenAPI JSON specification."""
    openapi_schema = app.openapi()
    openapi_schema["info"]["version"] = API_CONTRACT_VERSION

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Exported OpenAPI spec (v{API_CONTRACT_VERSION}) to {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export deterministic OpenAPI JSON specification.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/api/openapi.json"),
        help="Target output path for openapi.json",
    )
    args = parser.parse_args()
    export_openapi(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
