#!/usr/bin/env python3
"""Export timeline events from WaterToday BC advisory records."""

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

DATE_PATTERN = re.compile(
    r"\b(?P<numeric>\d{1,2}/\d{1,2}/\d{4})\b"
    r"|\b(?P<day_month_year>\d{1,2}/[A-Za-z]{3,9}/\d{4})\b"
    r"|\b(?P<day_month_space_year>\d{1,2}/[A-Za-z]{3,9}\s+\d{4})\b"
    r"|\b(?P<month_year>[A-Za-z]{3,9}\s+\d{4})\b"
)


def normalize_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def parse_date_token(token):
    token = normalize_space(token)
    for fmt in ("%m/%d/%Y", "%d/%b/%Y", "%d/%B/%Y", "%d/%b %Y", "%d/%B %Y"):
        try:
            return datetime.strptime(token, fmt).date(), "day"
        except ValueError:
            pass

    match = re.fullmatch(r"([A-Za-z]{3,9})\s+(\d{4})", token)
    if match:
        month = MONTHS.get(match.group(1).lower())
        if month:
            return date(int(match.group(2)), month, 1), "month"
    return None, None


def split_detail_events(details):
    matches = list(DATE_PATTERN.finditer(details or ""))
    events = []
    for index, match in enumerate(matches):
        raw_date = match.group(0)
        parsed_date, precision = parse_date_token(raw_date)
        if not parsed_date:
            continue
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(details)
        snippet = normalize_space(details[start:end])
        events.append(
            {
                "event_date": parsed_date.isoformat(),
                "date_precision": precision,
                "raw_date": raw_date,
                "event_text": snippet,
            }
        )
    return events


def parse_simple_date(value):
    parsed, _precision = parse_date_token(value or "")
    return parsed


def main():
    parser = argparse.ArgumentParser(description="Export WaterToday BC timeline events")
    parser.add_argument("--input", default="data/water/watertoday_bc_advisories.json")
    parser.add_argument("--output", default="data/water/watertoday_bc_timeline.json")
    args = parser.parse_args()

    records = json.loads(Path(args.input).read_text(encoding="utf-8"))
    today = date.today()
    events = []

    for record in records:
        base = {
            "source": "WaterToday",
            "name": record.get("name"),
            "advisory_type": record.get("advisory_type"),
            "status": record.get("status"),
            "details_url": record.get("details_url"),
            "latitude": record.get("latitude"),
            "longitude": record.get("longitude"),
        }
        issued_date = parse_simple_date(record.get("issued") or record.get("since"))
        if issued_date:
            events.append(
                {
                    **base,
                    "event_kind": "advisory_record",
                    "event_date": issued_date.isoformat(),
                    "date_precision": "day",
                    "raw_date": record.get("issued") or record.get("since"),
                    "event_text": normalize_space(record.get("details")),
                    "future_date": issued_date > today,
                }
            )

        for detail_event in split_detail_events(record.get("details")):
            event_date = datetime.strptime(detail_event["event_date"], "%Y-%m-%d").date()
            events.append(
                {
                    **base,
                    "event_kind": "detail_mention",
                    **detail_event,
                    "future_date": event_date > today,
                }
            )

    events.sort(key=lambda item: (item.get("event_date") or "", item.get("name") or ""))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(events)} WaterToday timeline events to {output}")


if __name__ == "__main__":
    main()
