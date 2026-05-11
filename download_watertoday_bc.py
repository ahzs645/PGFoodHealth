#!/usr/bin/env python3
"""Download WaterToday British Columbia active water advisories."""

import argparse
import html as html_lib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.watertoday.ca/"
BC_LIST_URL = urljoin(BASE_URL, "textm-p.asp?province=2")
BC_MARKERS_URL = urljoin(BASE_URL, "provxml6.asp?province=2")


def normalize_space(value):
    return re.sub(r"\s+", " ", value or "").strip()


def match_key(value):
    return re.sub(r"[^a-z0-9]+", " ", normalize_space(value).lower()).strip()


def make_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    return session


def fetch_html(session, url, timeout=30, attempts=1):
    last_exc = None
    for attempt in range(attempts):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            return response.content.decode(response.encoding or "latin-1", errors="replace")
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < attempts:
                time.sleep(1 + attempt)
    raise last_exc


def parse_bc_list(html):
    soup = BeautifulSoup(html, "html.parser")
    advisories = []
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        number = normalize_space(cells[0].get_text(" ", strip=True)).rstrip(".")
        if not number.isdigit():
            continue
        link = cells[1].find("a", href=True)
        municipality = normalize_space(cells[1].get_text(" ", strip=True))
        advisory_type = normalize_space(cells[2].get_text(" ", strip=True))
        since = normalize_space(cells[3].get_text(" ", strip=True))
        advisories.append(
            {
                "source": "WaterToday",
                "province": "British Columbia",
                "list_number": int(number),
                "name": municipality,
                "advisory_type": advisory_type,
                "since": since,
                "details_url": urljoin(BASE_URL, link["href"]) if link else None,
                "scraped_at": datetime.now().isoformat(),
            }
        )
    return advisories


def parse_marker_popup(value):
    popup_html = html_lib.unescape(value or "")
    soup = BeautifulSoup(popup_html, "html.parser")
    lines = [
        normalize_space(line)
        for line in soup.get_text("\n", strip=True).splitlines()
        if normalize_space(line)
    ]
    parsed = {"map_popup_text": "\n".join(lines)}
    if len(lines) >= 2:
        parsed["map_advisory_type"] = lines[1]
    if len(lines) >= 3:
        parsed["map_details"] = "\n".join(lines[2:-1]) if len(lines) > 3 else lines[2]
    if lines:
        parsed["map_since"] = lines[-1]
    return parsed


def parse_bc_markers(xml_text):
    root = ET.fromstring(xml_text.strip())
    markers = {}
    for marker in root.findall("marker"):
        label = normalize_space(marker.get("label"))
        if not label:
            continue
        item = {
            "latitude": float(marker.get("lat")),
            "longitude": float(marker.get("lng")),
            "map_label": label,
            "map_icon_type": normalize_space(marker.get("icontype")),
        }
        item.update(parse_marker_popup(marker.get("html")))
        markers.setdefault(match_key(label), []).append(item)
    return markers


def parse_detail(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    detail = {}

    status_match = re.search(r"Type:\s*(.*?)\s*-\s*(Active|Inactive|Rescinded|Lifted)", text, re.I | re.S)
    if status_match:
        detail["detail_type"] = normalize_space(status_match.group(1))
        detail["status"] = normalize_space(status_match.group(2))

    issued_match = re.search(r"Issued:\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", text)
    if issued_match:
        detail["issued"] = issued_match.group(1)

    pre = soup.find("pre")
    if pre:
        details_text = normalize_space(pre.get_text(" ", strip=True))
        detail["details"] = re.sub(r"^Details:\s*", "", details_text, flags=re.I)
    return detail


def save_json(data, path):
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_existing(path):
    source = Path(path)
    if not source.exists():
        return {}
    with source.open("r", encoding="utf-8") as f:
        records = json.load(f)
    return {
        item["details_url"]: item
        for item in records
        if isinstance(item, dict) and item.get("details_url")
    }


def main():
    parser = argparse.ArgumentParser(description="Download WaterToday BC advisories")
    parser.add_argument("--output", default="data/water/watertoday_bc_advisories.json")
    parser.add_argument("--details", action="store_true", help="Fetch individual detail pages")
    parser.add_argument("--reuse-existing", action="store_true", help="Reuse detail fields already present in the output file")
    parser.add_argument("--limit", type=int, default=None, help="Limit records for test runs")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between detail requests")
    args = parser.parse_args()

    session = make_session()
    advisories = parse_bc_list(fetch_html(session, BC_LIST_URL))

    try:
        markers = parse_bc_markers(fetch_html(session, BC_MARKERS_URL, timeout=90, attempts=3))
        for advisory in advisories:
            matches = markers.get(match_key(advisory["name"])) or []
            if matches:
                advisory.update(matches.pop(0))
        print(f"Matched map coordinates for {sum(1 for item in advisories if 'latitude' in item)}/{len(advisories)} advisories")
    except Exception as exc:
        print(f"Warning: failed to fetch WaterToday map markers: {exc}")

    if args.limit is not None:
        advisories = advisories[: args.limit]

    existing = load_existing(args.output) if args.reuse_existing else {}

    if args.details:
        for index, advisory in enumerate(advisories, start=1):
            if not advisory.get("details_url"):
                continue
            cached = existing.get(advisory["details_url"])
            if cached and not cached.get("detail_error"):
                for key in ("detail_type", "status", "issued", "details"):
                    if key in cached:
                        advisory[key] = cached[key]
                continue
            print(f"[{index}/{len(advisories)}] {advisory['name']}")
            try:
                advisory.update(parse_detail(fetch_html(session, advisory["details_url"])))
            except Exception as exc:
                advisory["detail_error"] = str(exc)
            if args.delay:
                time.sleep(args.delay)

    save_json(advisories, args.output)
    print(f"Saved {len(advisories)} WaterToday BC advisories to {args.output}")


if __name__ == "__main__":
    main()
