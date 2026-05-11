#!/usr/bin/env python3
"""Flag likely bad Google geocodes for restaurant and water records."""

import argparse
import json
import math
from pathlib import Path

from geocode_google_all import DEFAULT_RESTAURANTS, DEFAULT_WATER_DIR, WATER_FILES, read_json, write_json


COMMUNITY_CENTERS = {
    "arras": (55.758, -120.481),
    "atlin": (59.578, -133.690),
    "bear lake": (54.508, -122.681),
    "burns lake": (54.233, -125.763),
    "charlie lake": (56.276, -120.963),
    "chetwynd": (55.697, -121.637),
    "dawson creek": (55.760, -120.235),
    "dease lake": (58.438, -129.997),
    "fort nelson": (58.805, -122.697),
    "fort st james": (54.443, -124.254),
    "fort st. john": (56.252, -120.847),
    "fraser lake": (54.061, -124.849),
    "hazelton": (55.256, -127.673),
    "hixon": (53.407, -122.585),
    "houston": (54.397, -126.650),
    "hudson's hope": (56.030, -121.906),
    "kitimat": (54.052, -128.653),
    "mackenzie": (55.336, -123.093),
    "mcbride": (53.302, -120.164),
    "prince george": (53.917, -122.749),
    "prince rupert": (54.315, -130.320),
    "quesnel": (52.978, -122.494),
    "smithers": (54.782, -127.168),
    "stewart": (55.936, -129.987),
    "telkwa": (54.699, -127.050),
    "terrace": (54.516, -128.603),
    "tumbler ridge": (55.126, -120.993),
    "valemount": (52.831, -119.265),
    "vanderhoof": (54.014, -124.008),
}

EXPECTED_CITY_IN_ADDRESS = {
    "prince george",
    "quesnel",
    "smithers",
    "terrace",
    "kitimat",
    "hazelton",
    "houston",
    "burns lake",
    "vanderhoof",
    "fort st. john",
    "fort nelson",
    "dawson creek",
    "chetwynd",
    "mackenzie",
    "mcbride",
    "valemount",
    "stewart",
    "atlin",
    "dease lake",
    "tumbler ridge",
    "prince rupert",
}

GENERIC_ADDRESS_TERMS = {
    "canada",
    "bc, canada",
    "british columbia, canada",
    "north coast, bc, canada",
}


def normalize(value):
    return (value or "").strip().lower()


def haversine_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def expected_city(record):
    return normalize(record.get("city") or record.get("location_summary"))


def validate_record(record):
    issues = []
    lat = record.get("latitude")
    lon = record.get("longitude")
    address = normalize(record.get("google_geocoded_address"))
    city = expected_city(record)

    if lat is None or lon is None:
        issues.append("missing_coordinates")
    else:
        if not (48.0 <= float(lat) <= 60.1 and -139.2 <= float(lon) <= -114.0):
            issues.append("outside_bc_bbox")
        center = COMMUNITY_CENTERS.get(city)
        if center:
            distance = haversine_km(float(lat), float(lon), center[0], center[1])
            record["google_expected_city_distance_km"] = round(distance, 1)
            threshold = 175
            if city in {"stewart", "atlin", "dease lake", "fort nelson", "north coast regional district"}:
                threshold = 300
            if distance > threshold:
                issues.append("far_from_expected_city")

    if record.get("google_partial_match"):
        issues.append("partial_match")
    if record.get("google_location_type") == "APPROXIMATE":
        issues.append("approximate_location")
    if address in GENERIC_ADDRESS_TERMS or address.startswith("yellowhead hwy, canada"):
        issues.append("generic_geocoded_address")
    if city in EXPECTED_CITY_IN_ADDRESS and address and city not in address:
        issues.append("geocoded_address_missing_expected_city")

    record["google_geocode_quality"] = "review" if issues else "ok"
    record["google_geocode_quality_issues"] = sorted(set(issues))
    return record


def validate_file(path):
    records = read_json(path)
    for record in records:
        validate_record(record)
    write_json(path, records)
    return records


def main():
    parser = argparse.ArgumentParser(description="Validate geocoded restaurant and water locations")
    parser.add_argument("--restaurants", default=DEFAULT_RESTAURANTS)
    parser.add_argument("--water-dir", default=DEFAULT_WATER_DIR)
    parser.add_argument("--report", default="data/geocoding/geocode_quality_report.json")
    args = parser.parse_args()

    files = {"restaurants": Path(args.restaurants)}
    water_dir = Path(args.water_dir)
    for dataset, filename in WATER_FILES.items():
        files[f"water_{dataset}"] = water_dir / filename

    report = {}
    for label, path in files.items():
        records = validate_file(path)
        review = [record for record in records if record.get("google_geocode_quality") == "review"]
        issue_counts = {}
        for record in review:
            for issue in record.get("google_geocode_quality_issues") or []:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
        report[label] = {
            "total": len(records),
            "ok": len(records) - len(review),
            "review": len(review),
            "issue_counts": issue_counts,
            "examples": [
                {
                    "name": record.get("facility_name") or record.get("name"),
                    "city": record.get("city") or record.get("location_summary"),
                    "facility_location": record.get("facility_location"),
                    "query": record.get("google_geocode_query"),
                    "address": record.get("google_geocoded_address"),
                    "latitude": record.get("latitude"),
                    "longitude": record.get("longitude"),
                    "distance_km": record.get("google_expected_city_distance_km"),
                    "issues": record.get("google_geocode_quality_issues"),
                }
                for record in review[:50]
            ],
        }

    write_json(args.report, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
