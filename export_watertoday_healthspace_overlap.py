#!/usr/bin/env python3
"""Compare WaterToday BC advisories with HealthSpace active water notices."""

import argparse
import json
import math
import re
from collections import Counter
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path


STOPWORDS = {
    "and",
    "advisory",
    "bc",
    "bwn",
    "camp",
    "campground",
    "community",
    "first",
    "nation",
    "notice",
    "of",
    "park",
    "provincial",
    "system",
    "the",
    "water",
    "ws",
}


def normalize(value):
    value = (value or "").lower().replace("&", " and ")
    value = re.sub(r"['’_]", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokens(value):
    return {token for token in normalize(value).split() if token not in STOPWORDS and not token.isdigit()}


def parse_date(value):
    if not value:
        return None
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def distance_km(left, right):
    lat1, lon1 = left
    lat2, lon2 = right
    radius = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    value = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(value))


def best_match(healthspace, watertoday):
    hs_name = healthspace.get("name") or healthspace.get("facility_name") or ""
    hs_tokens = tokens(hs_name)
    best = None
    for advisory in watertoday:
        wt_name = advisory.get("name") or ""
        ratio = SequenceMatcher(None, normalize(hs_name), normalize(wt_name)).ratio()
        wt_tokens = tokens(wt_name)
        token_jaccard = len(hs_tokens & wt_tokens) / len(hs_tokens | wt_tokens) if hs_tokens | wt_tokens else 0
        km = None
        if all(healthspace.get(key) for key in ("latitude", "longitude")) and all(
            advisory.get(key) for key in ("latitude", "longitude")
        ):
            km = distance_km(
                (healthspace["latitude"], healthspace["longitude"]),
                (advisory["latitude"], advisory["longitude"]),
            )
        score = max(ratio, token_jaccard)
        candidate = {
            "sort_key": (score, ratio, token_jaccard, -(km or 9999)),
            "score": score,
            "ratio": ratio,
            "token_jaccard": token_jaccard,
            "advisory": advisory,
            "distance_km": km,
        }
        if best is None or candidate["sort_key"] > best["sort_key"]:
            best = candidate
    score = best["score"]
    ratio = best["ratio"]
    token_jaccard = best["token_jaccard"]
    advisory = best["advisory"]
    km = best["distance_km"]
    hs_date = parse_date(healthspace.get("start_date"))
    wt_date = parse_date(advisory.get("since"))
    same_date = bool(hs_date and wt_date and hs_date == wt_date)
    exact_name = normalize(hs_name) == normalize(advisory.get("name"))
    probable_same_facility = exact_name or ratio >= 0.88 or token_jaccard >= 0.62 or (km is not None and km <= 2)
    probable_same_notice = probable_same_facility and same_date
    return {
        "bucket": "same_notice" if probable_same_notice else "same_facility_possible" if probable_same_facility else "no_clear_match",
        "score": round(score, 3),
        "name_ratio": round(ratio, 3),
        "token_jaccard": round(token_jaccard, 3),
        "distance_km": round(km, 3) if km is not None else None,
        "same_start_date": same_date,
        "healthspace": {
            "name": healthspace.get("name"),
            "notice_type": healthspace.get("notice_type"),
            "start_date": healthspace.get("start_date"),
            "start_date_iso": hs_date,
            "location_summary": healthspace.get("location_summary"),
            "details_url": healthspace.get("details_url"),
            "latitude": healthspace.get("latitude"),
            "longitude": healthspace.get("longitude"),
        },
        "watertoday": {
            "name": advisory.get("name"),
            "advisory_type": advisory.get("advisory_type"),
            "since": advisory.get("since"),
            "since_iso": wt_date,
            "details_url": advisory.get("details_url"),
            "latitude": advisory.get("latitude"),
            "longitude": advisory.get("longitude"),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Compare HealthSpace notices with WaterToday advisories")
    parser.add_argument("--healthspace", default="data/water/active_water_notices.json")
    parser.add_argument("--watertoday", default="data/water/watertoday_bc_advisories.json")
    parser.add_argument("--output", default="data/water/watertoday_healthspace_overlap.json")
    args = parser.parse_args()

    healthspace = json.loads(Path(args.healthspace).read_text(encoding="utf-8"))
    watertoday = json.loads(Path(args.watertoday).read_text(encoding="utf-8"))
    matches = [best_match(record, watertoday) for record in healthspace]
    summary = {
        "healthspace_count": len(healthspace),
        "watertoday_count": len(watertoday),
        "bucket_counts": dict(Counter(match["bucket"] for match in matches)),
        "healthspace_notice_types": dict(Counter(record.get("notice_type") for record in healthspace)),
        "watertoday_advisory_types": dict(Counter(record.get("advisory_type") for record in watertoday)),
        "watertoday_with_coordinates": sum(
            bool(record.get("latitude") and record.get("longitude")) for record in watertoday
        ),
    }
    output = {"summary": summary, "matches": matches}
    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Saved overlap report to {args.output}")


if __name__ == "__main__":
    main()
