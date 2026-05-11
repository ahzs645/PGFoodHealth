#!/usr/bin/env python3
"""Apply manual review decisions to the WaterToday/HealthSpace overlap report."""

import argparse
import argparse
import json
from collections import Counter
from pathlib import Path


DO_NOT_LINK = {
    "Kitimat Community Water System": "WaterToday KITIMAT (1) detail is Kitimat Animal Control, not the community water system.",
}

NEEDS_REVIEW = {
    "Tete Jaune Weigh Scale": "Same date/type, but coordinates are hundreds of km apart.",
    "Finlay River Outfitters": "Exact name/date, but type differs and coordinates are hundreds of km apart.",
    "Summit Lake Park": "Same date/type, but WaterToday name is generic and coordinates are far apart.",
    "West Coast Fishing Club - The Clubhouse": "Same date, but WaterToday is a generic grouped record with different type and distant coordinates.",
    "West Coast Fishing Club - The Outpost": "Same date, but WaterToday is a generic grouped record with different type and distant coordinates.",
    "Whiskers Bay Resort": "Exact name/date/type, but coordinates are far apart.",
    "Gwillim Lake Provincial Park": "Exact name/date/type, but coordinates are far apart.",
    "One Island Lake Provincial Park, Well 1": "Likely related, but two HealthSpace well records map to one generic WaterToday record.",
    "One Island Lake Provincial Park, Well 2": "Likely related, but two HealthSpace well records map to one generic WaterToday record.",
    "Mackenzie CWS Gantahaz Subdivision": "Name/date/location plausible, but WaterToday type differs.",
}

CONFIRMED_SAME_FACILITY = {
    "10 Mile Lake Provincial Park": "Same facility, same notice type, coordinates within 0.5 km; dates differ.",
    "Benjamin Water System": "Exact name, same WQA, coordinates within 0.1 km; WaterToday detail matches manganese issue.",
    "King's Valley Christian Camp": "Exact normalized name and matching cause text; WaterToday coordinates appear approximate.",
    "Prespatou Store [2013] Water System": "Same named facility and manganese issue; WaterToday top-level type appears inconsistent with its detail text.",
}

CONFIRMED_AGGREGATE = {
    "Prince George Refinery": "WaterToday grouped PRINCE GEORGE (2) detail explicitly includes Prince George Refinery.",
    "Quesnel CWS": "WaterToday grouped Quesnel (8) detail explicitly includes Quesnel Water System with matching date/cause.",
    "Smithers Community Water System": "WaterToday grouped SMITHERS (14) detail explicitly includes Smithers Community Water System with matching date/cause.",
}

DIRECT_PROMOTIONS = {
    "Hixon Firehall": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=43433", "Same date, nearby coordinates, exact facility in WaterToday detail."),
    "K & L Water Service - Unit W137 Western Star Unit": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=41854", "Same date, nearby coordinates, facility variant in WaterToday detail."),
    "Tangle Ridge Custom Crushing": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=42387", "Same date, nearby coordinates, exact WaterToday detail name."),
    "Dunster Fine Arts School Society": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=2753", "Same date, nearby coordinates, exact WaterToday detail name."),
    "Alamo Water System": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=42610", "Same date, nearby coordinates, WaterToday detail says Alamo Motel & RV WS."),
    "Sikanni River RV Park": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=41856", "Same date, nearby coordinates, exact WaterToday detail name."),
    "Camp Sagitawa Water System": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=41552", "Same date, nearby coordinates, WaterToday detail says Camp Sagitawa WS."),
    "United Initiators Canada Ltd": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=43113", "Same date, nearby coordinates, exact WaterToday detail name."),
    "Red Goat Lodge Water System": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=22506", "Same date, nearby coordinates, WaterToday detail has Red Goat Lodge variant."),
    "Chemtrade": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=43412", "Same date, nearby coordinates, exact WaterToday detail name."),
    "Tetsa River Services Campground": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=40963", "Same date and exact WaterToday detail name."),
    "Birch Bay Resort and Cabins": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=31730", "Same date and exact WaterToday detail name."),
    "Babine Camp": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=1284", "Same date and exact WaterToday detail name."),
    "Cale Creek Water Club": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=38470", "Same date and exact WaterToday detail name in grouped row."),
    "Willow River General Store": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=7677", "Same date and exact WaterToday detail name."),
    "Camp Hughes": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=41551", "Same date and exact WaterToday detail name."),
    "Takysie Lake Resort": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=42549", "Same date and strong name/detail match; WaterToday coordinates appear approximate."),
}

EMBEDDED_DATE_PROMOTIONS = {
    "Bearpaw Heli Skiing": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=1328", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Sinclair Mills Water Users Community": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=1328", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Silver Queen Camp": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=480", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Hutda Lake Correctional Camp": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=34579", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Tchentlo Lake Lodge": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=34290", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Bearclaw Lodge": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=29272", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Spruce Capital Trailer Park": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=34579", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Canfor Intercon": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=34579", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Barendregt Water System": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=33956", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Smithers Regional Airport - Water System": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=33956", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "BCR Industrial Site Fort St. James": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=34290", "WaterToday grouped row detail includes facility and HealthSpace start date."),
    "Walker Camp": ("https://www.watertoday.ca/textm-a.asp?province=2&advisory=43412", "WaterToday grouped row detail includes exact facility; detail date differs slightly from grouped row date."),
}


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def wt_summary(record):
    return {
        "name": record.get("name"),
        "advisory_type": record.get("advisory_type"),
        "since": record.get("since"),
        "since_iso": None,
        "details_url": record.get("details_url"),
        "latitude": record.get("latitude"),
        "longitude": record.get("longitude"),
    }


def main():
    parser = argparse.ArgumentParser(description="Export reviewed WaterToday/HealthSpace overlap")
    parser.add_argument("--healthspace", default="data/water/active_water_notices.json")
    parser.add_argument("--watertoday", default="data/water/watertoday_bc_advisories.json")
    parser.add_argument("--overlap", default="data/water/watertoday_healthspace_overlap.json")
    parser.add_argument("--output", default="data/water/watertoday_healthspace_overlap_reviewed.json")
    args = parser.parse_args()

    healthspace = load(args.healthspace)
    watertoday = load(args.watertoday)
    overlap = load(args.overlap)
    wt_by_url = {record.get("details_url"): record for record in watertoday}
    existing_by_hs = {match["healthspace"]["details_url"]: match for match in overlap["matches"]}
    hs_by_name = {record.get("name"): record for record in healthspace}

    reviewed_by_hs_url = {}
    for match in overlap["matches"]:
        name = match["healthspace"]["name"]
        match = dict(match)
        match["review_decision"] = "auto"
        match["review_note"] = None
        if name in DO_NOT_LINK:
            match["bucket"] = "do_not_link"
            match["review_decision"] = "manual_do_not_link"
            match["review_note"] = DO_NOT_LINK[name]
        elif name in NEEDS_REVIEW:
            match["bucket"] = "same_notice_needs_review"
            match["review_decision"] = "manual_needs_review"
            match["review_note"] = NEEDS_REVIEW[name]
        elif name in CONFIRMED_SAME_FACILITY:
            match["bucket"] = "same_facility_confirmed"
            match["review_decision"] = "manual_confirmed"
            match["review_note"] = CONFIRMED_SAME_FACILITY[name]
        elif name in CONFIRMED_AGGREGATE:
            match["bucket"] = "same_facility_aggregate"
            match["review_decision"] = "manual_confirmed_aggregate"
            match["review_note"] = CONFIRMED_AGGREGATE[name]
        reviewed_by_hs_url[match["healthspace"]["details_url"]] = match

    for source, bucket, decision in [
        (DIRECT_PROMOTIONS, "same_notice_promoted_from_detail", "manual_promoted"),
        (EMBEDDED_DATE_PROMOTIONS, "same_notice_promoted_from_embedded_detail", "manual_promoted_embedded_date"),
    ]:
        for hs_name, (wt_url, note) in source.items():
            hs = hs_by_name[hs_name]
            wt = wt_by_url[wt_url]
            hs_url = hs.get("details_url")
            base = dict(reviewed_by_hs_url.get(hs_url) or existing_by_hs.get(hs_url, {}))
            if not base:
                continue
            base["bucket"] = bucket
            base["review_decision"] = decision
            base["review_note"] = note
            base["watertoday"] = wt_summary(wt)
            reviewed_by_hs_url[hs_url] = base

    reviewed = list(reviewed_by_hs_url.values())

    output = {
        "summary": {
            "reviewed_match_count": len(reviewed),
            "healthspace_count": len(healthspace),
            "watertoday_count": len(watertoday),
            "bucket_counts": dict(Counter(match["bucket"] for match in reviewed)),
            "review_decision_counts": dict(Counter(match["review_decision"] for match in reviewed)),
        },
        "matches": reviewed,
    }
    Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(output["summary"], indent=2))
    print(f"Saved reviewed overlap to {args.output}")


if __name__ == "__main__":
    main()
