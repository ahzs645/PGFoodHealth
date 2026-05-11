#!/usr/bin/env python3
"""Export a deduplicated Google geocoding worklist without calling Google."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from geocode_google_all import (
    DEFAULT_RESTAURANTS,
    DEFAULT_WATER_DIR,
    WATER_FILES,
    build_targets,
    cache_key,
    read_json,
    write_json,
)


def main():
    parser = argparse.ArgumentParser(description="Export deduped Google geocoding worklist")
    parser.add_argument("--restaurants", default=DEFAULT_RESTAURANTS)
    parser.add_argument("--water-dir", default=DEFAULT_WATER_DIR)
    parser.add_argument("--output", default="data/geocoding/google_geocode_worklist.json")
    args = parser.parse_args()

    restaurants = read_json(args.restaurants)
    water_dir = Path(args.water_dir)
    water_records = {
        dataset: read_json(water_dir / filename) for dataset, filename in WATER_FILES.items()
    }
    restaurant_queries, water_record_queries, _ = build_targets(restaurants, water_records)

    grouped = defaultdict(lambda: {"query": "", "records": []})

    for index, (record, query) in enumerate(zip(restaurants, restaurant_queries)):
        key = cache_key(query)
        grouped[key]["query"] = query
        grouped[key]["records"].append(
            {
                "dataset": "restaurants",
                "file": str(Path(args.restaurants)),
                "index": index,
                "name": record.get("name"),
                "city": record.get("city"),
                "address": record.get("full_address") or record.get("address"),
                "existing_latitude": record.get("latitude"),
                "existing_longitude": record.get("longitude"),
            }
        )

    for dataset, records in water_records.items():
        file_path = water_dir / WATER_FILES[dataset]
        for index, (record, query) in enumerate(zip(records, water_record_queries[dataset])):
            key = cache_key(query)
            grouped[key]["query"] = query
            grouped[key]["records"].append(
                {
                    "dataset": f"water_{dataset}",
                    "file": str(file_path),
                    "index": index,
                    "name": record.get("facility_name") or record.get("name"),
                    "city": record.get("city") or record.get("location_summary"),
                    "facility_location": record.get("facility_location"),
                    "existing_latitude": record.get("latitude"),
                    "existing_longitude": record.get("longitude"),
                }
            )

    worklist = []
    for key, item in sorted(grouped.items(), key=lambda pair: pair[1]["query"].lower()):
        records = item["records"]
        worklist.append(
            {
                "id": key,
                "query": item["query"],
                "record_count": len(records),
                "datasets": sorted({record["dataset"] for record in records}),
                "records": records,
            }
        )

    summary = {
        "unique_query_count": len(worklist),
        "linked_record_count": sum(item["record_count"] for item in worklist),
        "source_files": {
            "restaurants": str(Path(args.restaurants)),
            **{
                f"water_{dataset}": str(water_dir / filename)
                for dataset, filename in WATER_FILES.items()
            },
        },
    }
    output = {"summary": summary, "worklist": worklist}
    write_json(args.output, output)
    print(f"Saved {len(worklist)} deduped geocode queries to {args.output}")


if __name__ == "__main__":
    main()
