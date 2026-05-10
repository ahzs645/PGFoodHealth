#!/usr/bin/env python3
"""Validate water reference/interpreter coverage against scraped water data."""

import argparse
import json
from collections import Counter
from pathlib import Path

from water_reference import (
    get_chemical_guideline,
    interpret_bacteriological_code,
    parse_chemical_result_value,
)


BACTERIOLOGICAL_FIELDS = ("total_coliform", "fecal_coliform", "e_coli")


def load_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def validate_bacteriological(records):
    status_counts = Counter()
    raw_counts = Counter()
    sample_rows = 0
    value_count = 0
    blank_count = 0

    for record in records:
        samples = record.get("samples") or []
        sample_rows += len(samples)
        for sample in samples:
            for field in BACTERIOLOGICAL_FIELDS:
                value_count += 1
                raw = (sample.get(field) or "").strip()
                if not raw:
                    blank_count += 1
                    continue
                raw_counts[raw] += 1
                status_counts[interpret_bacteriological_code(raw)["status"]] += 1

    unknown = Counter(
        {
            raw: count
            for raw, count in raw_counts.items()
            if interpret_bacteriological_code(raw)["status"] == "unknown"
        }
    )
    interpreted = sum(status_counts.values()) - status_counts.get("unknown", 0)
    return {
        "records": len(records),
        "sample_rows": sample_rows,
        "values": value_count,
        "blank_values": blank_count,
        "interpreted_nonblank_values": interpreted,
        "unknown_nonblank_values": status_counts.get("unknown", 0),
        "status_counts": dict(status_counts),
        "top_unknown_values": unknown.most_common(25),
    }


def validate_chemical(records):
    matched = Counter()
    missed = Counter()
    qualifier_counts = Counter()
    unparsed_values = Counter()
    package_count = 0
    result_rows = 0

    for record in records:
        packages = record.get("chemical_result_packages") or []
        package_count += len(packages)
        for package in packages:
            for result in package.get("results") or []:
                result_rows += 1
                parameter = (result.get("type") or "").strip()
                value = (result.get("value") or "").strip()
                if get_chemical_guideline(parameter):
                    matched[parameter] += 1
                else:
                    missed[parameter] += 1
                parsed = parse_chemical_result_value(value)
                qualifier_counts[parsed["qualifier"] or "no_qualifier"] += 1
                if value and parsed["value"] is None:
                    unparsed_values[value] += 1

    return {
        "records": len(records),
        "packages": package_count,
        "result_rows": result_rows,
        "matched_guideline_rows": sum(matched.values()),
        "missing_guideline_rows": sum(missed.values()),
        "unique_matched_parameters": len(matched),
        "unique_missing_parameters": len(missed),
        "top_missing_parameters": missed.most_common(50),
        "value_qualifier_counts": dict(qualifier_counts),
        "top_unparsed_nonblank_values": unparsed_values.most_common(25),
    }


def main():
    parser = argparse.ArgumentParser(description="Validate water reference coverage")
    parser.add_argument(
        "--bacteriological",
        default="data/water/bacteriological_samples.json",
        help="Bacteriological samples JSON path",
    )
    parser.add_argument(
        "--chemical",
        default="data/water/chemical_samples.json",
        help="Chemical samples JSON path",
    )
    args = parser.parse_args()

    report = {
        "bacteriological": validate_bacteriological(load_json(args.bacteriological)),
        "chemical": validate_chemical(load_json(args.chemical)),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
