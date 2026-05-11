#!/usr/bin/env python3
"""Build a combined water notices database from HealthSpace and WaterToday."""

import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


def normalize(value):
    value = (value or "").lower().replace("&", " and ")
    value = re.sub(r"['’_]", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def parse_date(value):
    if not value:
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def stable_id(prefix, value):
    slug = normalize(value).replace(" ", "-")[:90].strip("-")
    return f"{prefix}:{slug}"


def compact_healthspace(record):
    return {
        "source": "HealthSpace",
        "source_id": record.get("details_url"),
        "name": record.get("name") or record.get("facility_name"),
        "notice_type": record.get("notice_type"),
        "status": "Active",
        "start_date": record.get("start_date"),
        "start_date_iso": parse_date(record.get("start_date")),
        "location_summary": record.get("location_summary"),
        "connections": record.get("connections"),
        "facility_location": record.get("facility_location"),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "details_url": record.get("details_url"),
        "underlying_problems": record.get("underlying_problems"),
        "steps_taken_to_remedy": record.get("steps_taken_to_remedy"),
        "corrective_actions_remaining": record.get("corrective_actions_remaining"),
        "inspection_count": len(record.get("inspections") or []),
        "raw": record,
    }


def compact_watertoday(record):
    return {
        "source": "WaterToday",
        "source_id": record.get("details_url"),
        "name": record.get("name"),
        "notice_type": record.get("advisory_type"),
        "status": record.get("status"),
        "start_date": record.get("since"),
        "start_date_iso": parse_date(record.get("since")),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
        "details_url": record.get("details_url"),
        "details": record.get("details"),
        "map_details": record.get("map_details"),
        "map_icon_type": record.get("map_icon_type"),
        "raw": record,
    }


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_combined(healthspace, watertoday, overlap):
    watertoday_by_url = {record.get("details_url"): record for record in watertoday}
    linked_watertoday_urls = set()
    combined = []
    linkable_buckets = {
        "same_notice",
        "same_notice_needs_review",
        "same_facility_possible",
        "same_facility_confirmed",
        "same_facility_aggregate",
        "same_notice_promoted_from_detail",
        "same_notice_promoted_from_embedded_detail",
    }

    for match in overlap["matches"]:
        hs = match["healthspace"]
        wt = match["watertoday"]
        healthspace_record = next(
            record for record in healthspace if record.get("details_url") == hs.get("details_url")
        )
        wt_record = watertoday_by_url.get(wt.get("details_url"))
        sources = [compact_healthspace(healthspace_record)]
        if match["bucket"] in linkable_buckets and wt_record:
            sources.append(compact_watertoday(wt_record))
            linked_watertoday_urls.add(wt_record.get("details_url"))

        canonical = sources[0]
        combined.append(
            {
                "id": stable_id("combined-water-notice", canonical.get("source_id") or canonical.get("name")),
                "record_type": "combined_notice",
                "primary_source": "HealthSpace",
                "merge_bucket": match["bucket"],
                "match": {
                    "score": match["score"],
                    "name_ratio": match["name_ratio"],
                    "token_jaccard": match["token_jaccard"],
                    "distance_km": match["distance_km"],
                    "same_start_date": match["same_start_date"],
                    "review_decision": match.get("review_decision"),
                    "review_note": match.get("review_note"),
                },
                "name": canonical.get("name"),
                "notice_type": canonical.get("notice_type"),
                "status": canonical.get("status"),
                "start_date_iso": canonical.get("start_date_iso"),
                "latitude": canonical.get("latitude"),
                "longitude": canonical.get("longitude"),
                "location_summary": canonical.get("location_summary"),
                "source_count": len(sources),
                "sources": sources,
            }
        )

    for record in watertoday:
        if record.get("details_url") in linked_watertoday_urls:
            continue
        source = compact_watertoday(record)
        combined.append(
            {
                "id": stable_id("watertoday-only", source.get("source_id") or source.get("name")),
                "record_type": "watertoday_only_notice",
                "primary_source": "WaterToday",
                "merge_bucket": "watertoday_only",
                "name": source.get("name"),
                "notice_type": source.get("notice_type"),
                "status": source.get("status"),
                "start_date_iso": source.get("start_date_iso"),
                "latitude": source.get("latitude"),
                "longitude": source.get("longitude"),
                "source_count": 1,
                "sources": [source],
            }
        )

    combined.sort(key=lambda item: (item.get("start_date_iso") or "", item.get("name") or ""))
    return combined


def main():
    parser = argparse.ArgumentParser(description="Export combined HealthSpace + WaterToday water notices")
    parser.add_argument("--healthspace", default="data/water/active_water_notices.json")
    parser.add_argument("--watertoday", default="data/water/watertoday_bc_advisories.json")
    parser.add_argument("--overlap", default="data/water/watertoday_healthspace_overlap.json")
    parser.add_argument("--output", default="data/water/combined_water_notices.json")
    parser.add_argument("--summary", default="data/water/combined_water_notices_summary.json")
    args = parser.parse_args()

    healthspace = load_json(args.healthspace)
    watertoday = load_json(args.watertoday)
    overlap = load_json(args.overlap)
    combined = build_combined(healthspace, watertoday, overlap)
    summary = {
        "combined_count": len(combined),
        "healthspace_count": len(healthspace),
        "watertoday_count": len(watertoday),
        "record_type_counts": dict(Counter(record["record_type"] for record in combined)),
        "merge_bucket_counts": dict(Counter(record["merge_bucket"] for record in combined)),
        "primary_source_counts": dict(Counter(record["primary_source"] for record in combined)),
        "with_coordinates": sum(bool(record.get("latitude") and record.get("longitude")) for record in combined),
        "with_multiple_sources": sum(record["source_count"] > 1 for record in combined),
    }

    Path(args.output).write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(args.summary).write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Saved combined notices to {args.output}")
    print(f"Saved summary to {args.summary}")


if __name__ == "__main__":
    main()
