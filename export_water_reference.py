#!/usr/bin/env python3
"""Export water interpretation reference tables to JSON."""

import argparse
import json
from pathlib import Path

from water_reference import get_water_reference


def main():
    parser = argparse.ArgumentParser(description="Export water reference metadata")
    parser.add_argument(
        "--output",
        default="data/water/water_reference.json",
        help="Output JSON path",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(get_water_reference(), f, indent=2, ensure_ascii=False)
    print(f"Saved water reference metadata to {output_path}")


if __name__ == "__main__":
    main()
