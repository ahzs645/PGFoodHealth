#!/usr/bin/env python3
"""
Resumable downloader for Northern Health HealthSpace restaurant inspection data.

This script wraps HealthSpaceAPI with safer progress handling than the original
all-cities helper: each city is saved independently, and each restaurant is
saved after it is processed so interrupted runs can resume.
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from healthspace_pg_restaurants import HealthSpaceAPI


def safe_name(name):
    """Return a stable filesystem-safe name for a city."""
    return (
        name.lower()
        .replace("&", "and")
        .replace(".", "")
        .replace("'", "")
        .replace("(", "")
        .replace(")", "")
        .replace("-", "_")
        .replace(" ", "_")
    )


def load_existing(path):
    """Load existing JSON list as a dict keyed by details URL, then name."""
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    existing = {}
    for item in data:
        key = item.get("details_url") or item.get("name")
        if key:
            existing[key] = item
    return existing


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def merge_restaurant(existing, fresh):
    """Keep already fetched detail/geocode fields while refreshing list fields."""
    merged = dict(existing or {})
    merged.update(fresh)

    for field in (
        "facility_type",
        "full_address",
        "current_hazard_rating",
        "non_smoking",
        "inspections",
        "details_fetched_at",
        "latitude",
        "longitude",
        "geocoded_address",
        "geocode_error",
    ):
        if existing and field in existing and field not in fresh:
            merged[field] = existing[field]

    return merged


def restaurant_is_complete(restaurant, include_details):
    if not include_details:
        return True
    return bool(restaurant.get("details_fetched_at")) and not restaurant.get("fetch_error")


def download_city(city, output_dir, include_details, max_inspections, delay, force):
    api = HealthSpaceAPI(city=city)
    output_path = output_dir / f"{safe_name(city)}_restaurants.json"

    print("=" * 72)
    print(f"Downloading {city}")
    print(f"Output: {output_path}")
    print("=" * 72)

    existing = load_existing(output_path)
    if existing:
        complete = sum(1 for item in existing.values() if restaurant_is_complete(item, include_details))
        print(f"Loaded {len(existing)} existing records ({complete} complete)")

    restaurants = api.get_all_restaurants()
    if not restaurants:
        print(f"No restaurants returned for {city}")
        return {
            "city": city,
            "file": str(output_path),
            "count": len(existing),
            "status": "empty",
        }

    by_key = dict(existing)
    fetched_details = 0
    skipped = 0
    errors = 0

    for index, restaurant in enumerate(restaurants, start=1):
        key = restaurant.get("details_url") or restaurant.get("name")
        current = merge_restaurant(by_key.get(key), restaurant)
        current["city"] = city

        if include_details and (force or not restaurant_is_complete(current, include_details)):
            print(f"[{index}/{len(restaurants)}] Details: {restaurant.get('name', 'Unknown')}")
            try:
                api.get_restaurant_full_details(
                    current,
                    fetch_inspections=True,
                    max_inspections=max_inspections,
                )
                current["city"] = city
                current.pop("fetch_error", None)
                fetched_details += 1
                time.sleep(delay)
            except Exception as exc:
                current["fetch_error"] = str(exc)
                current["fetch_error_at"] = datetime.now().isoformat()
                errors += 1
                print(f"  ERROR: {exc}")
        else:
            skipped += 1

        by_key[key] = current
        save_json(list(by_key.values()), output_path)

    print(f"Saved {len(by_key)} records for {city}")
    print(f"Fetched details: {fetched_details}; skipped: {skipped}; errors: {errors}")

    return {
        "city": city,
        "file": str(output_path),
        "count": len(by_key),
        "details_fetched": fetched_details,
        "skipped": skipped,
        "errors": errors,
        "status": "ok" if errors == 0 else "partial",
    }


def combine_city_files(results, output_path):
    combined = []
    for result in results:
        file_path = Path(result["file"])
        if not file_path.exists():
            continue
        with file_path.open("r", encoding="utf-8") as f:
            combined.extend(json.load(f))
    save_json(combined, output_path)
    print(f"Combined {len(combined)} records into {output_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download HealthSpace restaurant inspection data."
    )
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--city", default="Prince George", help="City to download")
    scope.add_argument("--all-cities", action="store_true", help="Download every known city")
    parser.add_argument(
        "--output-dir",
        default="data/healthspace",
        help="Directory for city JSON files",
    )
    parser.add_argument(
        "--basic-only",
        action="store_true",
        help="Only download facility list rows; skip inspection details and violations",
    )
    parser.add_argument(
        "--max-inspections",
        type=int,
        default=None,
        help="Maximum inspections per restaurant when downloading details",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between detail requests in seconds",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refetch details even for records already marked complete",
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Also write a combined all_restaurants.json file",
    )
    parser.add_argument("--list-cities", action="store_true", help="Print city names and exit")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.list_cities:
        for city in HealthSpaceAPI.get_cities():
            print(city)
        return

    output_dir = Path(args.output_dir)
    include_details = not args.basic_only
    cities = HealthSpaceAPI.get_cities() if args.all_cities else [args.city]

    results = []
    for index, city in enumerate(cities, start=1):
        print(f"\nCity {index}/{len(cities)}")
        try:
            results.append(
                download_city(
                    city=city,
                    output_dir=output_dir,
                    include_details=include_details,
                    max_inspections=args.max_inspections,
                    delay=args.delay,
                    force=args.force,
                )
            )
            if args.all_cities:
                time.sleep(max(args.delay, 2.0))
        except Exception as exc:
            print(f"ERROR processing {city}: {exc}")
            results.append({
                "city": city,
                "file": str(output_dir / f"{safe_name(city)}_restaurants.json"),
                "count": 0,
                "status": "error",
                "error": str(exc),
            })

        save_json(results, output_dir / "download_manifest.json")

    if args.combine:
        combine_city_files(results, output_dir / "all_restaurants.json")

    total = sum(result.get("count", 0) for result in results)
    print("\n" + "=" * 72)
    print(f"Done. Downloaded {total} records across {len(results)} city/cities.")
    print(f"Manifest: {output_dir / 'download_manifest.json'}")
    print("=" * 72)


if __name__ == "__main__":
    main()
