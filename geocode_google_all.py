#!/usr/bin/env python3
"""Geocode restaurant and water datasets with Google Geocoding API.

The script deduplicates Google requests, stores a reusable cache, and can attach
the same water facility coordinate to drinking, notice, bacteriological, and
chemical records that share a facility-name/city key.
"""

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


DEFAULT_ENV_FILE = "/Users/ahmadjalil/github/PGfoodmap/.env"
DEFAULT_RESTAURANTS = "/Users/ahmadjalil/github/PGMaps/public/data/restaurants.json"
DEFAULT_WATER_DIR = "data/water"
DEFAULT_CACHE = "data/geocoding/google_geocode_cache.json"

WATER_FILES = {
    "notices": "active_water_notices.json",
    "drinking": "drinking_water_facilities.json",
    "bacteriological": "bacteriological_samples.json",
    "chemical": "chemical_samples.json",
}


def normalize(value):
    value = (value or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s*,\s*", ", ", value)
    return value.strip(" ,")


def join_query(*parts):
    return ", ".join(part.strip() for part in parts if (part or "").strip())


def read_json(path):
    with Path(path).open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_env_file(path):
    env_path = Path(path)
    if not env_path.exists():
        return {}
    values = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_api_key(env_file):
    values = load_env_file(env_file)
    return (
        os.environ.get("GOOGLE_MAPS_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or values.get("GOOGLE_MAPS_API_KEY")
        or values.get("GOOGLE_API_KEY")
        or values.get("googleapi")
    )


def has_bc_canada(value):
    lowered = (value or "").lower()
    return (
        bool(re.search(r"\bbc\b", lowered))
        or "british columbia" in lowered
        or "canada" in lowered
    )


def restaurant_query(record):
    address = (record.get("full_address") or record.get("address") or "").strip()
    city = (record.get("city") or "Prince George").strip()
    name = (record.get("name") or "").strip()
    if address:
        return address if has_bc_canada(address) else join_query(address, city, "BC, Canada")
    return join_query(name, city, "BC, Canada")


def water_name_city_key(record):
    name = (record.get("facility_name") or record.get("name") or "").strip()
    city = (record.get("city") or record.get("location_summary") or "").strip()
    return normalize(join_query(name, city))


def water_query(record, dataset):
    if dataset in {"notices", "drinking"}:
        location = (record.get("facility_location") or "").strip()
        if location:
            return location if has_bc_canada(location) else join_query(location, "BC, Canada")
        name = (record.get("facility_name") or record.get("name") or "").strip()
        city = (record.get("city") or record.get("location_summary") or "").strip()
        return join_query(name, city, "BC, Canada")
    name = (record.get("name") or "").strip()
    city = (record.get("city") or "").strip()
    return join_query(name, city, "BC, Canada")


def load_cache(path):
    cache_path = Path(path)
    if not cache_path.exists():
        return {}
    return read_json(cache_path)


def cache_key(query):
    return normalize(query)


def geocode_google(query, api_key, timeout=20):
    params = urlencode({"address": query, "key": api_key})
    url = f"https://maps.googleapis.com/maps/api/geocode/json?{params}"
    with urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    status = payload.get("status")
    result = {
        "query": query,
        "status": status,
        "fetched_at": datetime.now().isoformat(),
    }
    if status == "OK" and payload.get("results"):
        top = payload["results"][0]
        location = top.get("geometry", {}).get("location", {})
        result.update(
            {
                "latitude": location.get("lat"),
                "longitude": location.get("lng"),
                "formatted_address": top.get("formatted_address"),
                "place_id": top.get("place_id"),
                "location_type": top.get("geometry", {}).get("location_type"),
                "partial_match": bool(top.get("partial_match")),
                "types": top.get("types") or [],
            }
        )
    else:
        result["error_message"] = payload.get("error_message")
    return result


def attach_geocode(record, query, cached_result):
    record["google_geocode_query"] = query
    record["google_geocode_status"] = cached_result.get("status")
    record["google_geocoded_at"] = cached_result.get("fetched_at")
    if cached_result.get("status") == "OK" and cached_result.get("latitude") is not None:
        record["latitude"] = cached_result.get("latitude")
        record["longitude"] = cached_result.get("longitude")
        record["google_geocoded_address"] = cached_result.get("formatted_address")
        record["google_place_id"] = cached_result.get("place_id")
        record["google_location_type"] = cached_result.get("location_type")
        record["google_partial_match"] = cached_result.get("partial_match")
        record.pop("google_geocode_error", None)
    else:
        record["google_geocode_error"] = cached_result.get("error_message") or cached_result.get("status")


def build_targets(restaurants, water_records):
    restaurant_queries = [restaurant_query(record) for record in restaurants]

    water_key_to_query = {}
    water_address_queries = []
    for dataset in ("notices", "drinking"):
        for record in water_records[dataset]:
            query = water_query(record, dataset)
            key = water_name_city_key(record)
            if query:
                water_address_queries.append(query)
            if key and (record.get("facility_location") or "").strip():
                water_key_to_query[key] = query

    water_record_queries = {}
    for dataset, records in water_records.items():
        water_record_queries[dataset] = []
        for record in records:
            key = water_name_city_key(record)
            query = water_key_to_query.get(key) or water_query(record, dataset)
            water_record_queries[dataset].append(query)

    all_queries = set(cache_key(q) for q in restaurant_queries if cache_key(q))
    for queries in water_record_queries.values():
        all_queries.update(cache_key(q) for q in queries if cache_key(q))

    return restaurant_queries, water_record_queries, all_queries


def main():
    parser = argparse.ArgumentParser(description="Google geocode restaurant and water datasets")
    parser.add_argument("--env-file", default=DEFAULT_ENV_FILE, help="Path to .env containing googleapi or GOOGLE_MAPS_API_KEY")
    parser.add_argument("--restaurants", default=DEFAULT_RESTAURANTS, help="Restaurant JSON file to update")
    parser.add_argument("--water-dir", default=DEFAULT_WATER_DIR, help="Directory containing water JSON files")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="Google geocode cache JSON path")
    parser.add_argument("--apply", action="store_true", help="Call Google and write geocoded data. Default is dry-run only.")
    parser.add_argument("--force", action="store_true", help="Refetch cached Google results")
    parser.add_argument("--limit", type=int, default=None, help="Maximum uncached Google requests for this run")
    parser.add_argument("--delay", type=float, default=0.05, help="Delay between Google requests")
    parser.add_argument(
        "--max-denied",
        type=int,
        default=3,
        help="Abort after this many REQUEST_DENIED responses in one run",
    )
    args = parser.parse_args()

    restaurants = read_json(args.restaurants)
    water_dir = Path(args.water_dir)
    water_records = {
        dataset: read_json(water_dir / filename) for dataset, filename in WATER_FILES.items()
    }
    restaurant_queries, water_record_queries, all_queries = build_targets(restaurants, water_records)

    cache = load_cache(args.cache)
    uncached = [query for query in sorted(all_queries) if args.force or query not in cache]
    if args.limit is not None:
        uncached_to_fetch = uncached[: args.limit]
    else:
        uncached_to_fetch = uncached

    print("Google geocode plan")
    print(f"restaurants: {len(restaurants)} records, {len(set(cache_key(q) for q in restaurant_queries if cache_key(q)))} unique queries")
    for dataset, records in water_records.items():
        unique = len(set(cache_key(q) for q in water_record_queries[dataset] if cache_key(q)))
        print(f"water {dataset}: {len(records)} records, {unique} unique attached queries")
    print(f"combined unique queries: {len(all_queries)}")
    print(f"cache entries: {len(cache)}")
    print(f"uncached/refetch queries: {len(uncached)}")
    if args.limit is not None:
        print(f"run limit: {args.limit}")

    if not args.apply:
        print("Dry-run only. Re-run with --apply to call Google and write files.")
        return

    api_key = get_api_key(args.env_file)
    if not api_key:
        raise SystemExit(f"No Google API key found in environment or {args.env_file}")

    print(f"Fetching {len(uncached_to_fetch)} Google geocode result(s)")
    denied_count = 0
    for index, query_key in enumerate(uncached_to_fetch, start=1):
        original_query = None
        for query in list(restaurant_queries) + [q for values in water_record_queries.values() for q in values]:
            if cache_key(query) == query_key:
                original_query = query
                break
        if not original_query:
            continue
        print(f"[{index}/{len(uncached_to_fetch)}] {original_query}")
        cache[query_key] = geocode_google(original_query, api_key)
        write_json(args.cache, cache)
        if cache[query_key].get("status") == "REQUEST_DENIED":
            denied_count += 1
            message = cache[query_key].get("error_message") or "Google returned REQUEST_DENIED"
            print(f"REQUEST_DENIED: {message}")
            if denied_count >= args.max_denied:
                raise SystemExit(
                    f"Aborting after {denied_count} REQUEST_DENIED responses. "
                    "Enable the Google Geocoding API for this key/project, then rerun."
                )
        if args.delay:
            time.sleep(args.delay)

    for record, query in zip(restaurants, restaurant_queries):
        result = cache.get(cache_key(query))
        if result:
            attach_geocode(record, query, result)
    write_json(args.restaurants, restaurants)

    for dataset, records in water_records.items():
        for record, query in zip(records, water_record_queries[dataset]):
            result = cache.get(cache_key(query))
            if result:
                attach_geocode(record, query, result)
        write_json(water_dir / WATER_FILES[dataset], records)

    ok = sum(1 for item in cache.values() if item.get("status") == "OK")
    print(f"Done. Cache entries: {len(cache)}; OK results: {ok}")


if __name__ == "__main__":
    main()
