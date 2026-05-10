#!/usr/bin/env python3
"""
Fetch detail pages for already-scraped water facility lists.
Reads existing JSON files, fetches each facility's detail URL, and updates the file.
Resumable - skips already-fetched records.
"""

import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

BASE_URL = "https://www.healthspace.ca/Clients/NHA/NHA_Website.nsf/"
SITE_ROOT = "https://www.healthspace.ca"

def normalize_space(value):
    return re.sub(r"\s+", " ", value or "").strip()

def make_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    return session

def fetch(session, url, retries=5):
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=60)
            if "Let's confirm you are human" in response.text:
                raise RuntimeError("HealthSpace returned a human-verification challenge")
            if response.status_code in {405, 429, 500, 502, 503, 504}:
                wait = 2 ** attempt
                print(f"    status={response.status_code}, waiting {wait}s...")
                time.sleep(wait)
                continue
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"    request error: {e}, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    response.raise_for_status()

def parse_key_value_table(table):
    data = {}
    for row in table.find_all("tr"):
        cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
        cells = [cell for cell in cells if cell]
        if not cells:
            continue
        if len(cells) >= 2:
            key = cells[0].rstrip(":").lower().replace(" ", "_").replace("-", "_")
            data[key] = cells[1]
    return data

def parse_table_rows(table):
    rows = []
    headers = []
    for row_index, row in enumerate(table.find_all("tr")):
        cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
        if row_index == 0:
            headers = [cell.lower().replace(".", "").replace(" ", "_") for cell in cells if cell]
            continue
        if not any(cells):
            continue
        rows.append(cells)
    return headers, rows

def parse_bacteriological_sample_rows(table):
    headers, rows = parse_table_rows(table)
    if rows:
        return rows

    header_count = len(headers) or 5
    cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in table.find_all("td")]
    cells = cells[header_count:]
    return [cells[index:index + 5] for index in range(0, len(cells), 5) if len(cells[index:index + 5]) >= 5]

# ---- Notice detail fetching ----
def fetch_notice_detail(session, notice, delay):
    soup = fetch(session, notice["details_url"])
    detail = {}

    h2 = soup.find("h2")
    if h2:
        detail["facility_name"] = normalize_space(h2.get_text(" ", strip=True))

    text = soup.get_text("\n", strip=True)
    if "Facility Location:" in text:
        lines = [normalize_space(line) for line in text.splitlines()]
        location_lines = []
        capture = False
        for line in lines:
            if line == "Facility Location:":
                capture = True
                continue
            if capture and line.startswith("Facility Information"):
                break
            if capture and line:
                location_lines.append(line)
        if location_lines:
            detail["facility_location"] = ", ".join(location_lines)

    tables = soup.find_all("table")
    if tables:
        detail.update(parse_key_value_table(tables[0]))

    for table in tables:
        if "Underlying Problems:" in table.get_text(" ", strip=True):
            detail["notice_details"] = parse_key_value_table(table)
            break

    inspections = []
    for table in tables:
        if "Document Type" not in table.get_text(" ", strip=True):
            continue
        for row in table.find_all("tr")[1:]:
            cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
            cells = [cell for cell in cells if cell]
            link = row.find("a", href=True)
            if not cells:
                continue
            inspection = {
                "document_type": cells[0],
                "details_url": urljoin(BASE_URL, link["href"]) if link else None,
            }
            if len(cells) >= 2:
                inspection["date"] = cells[1]
            if len(cells) >= 3:
                inspection["hazard_rating"] = cells[2]
            inspections.append(inspection)
        break

    detail["inspections"] = inspections
    detail["details_fetched_at"] = datetime.now().isoformat()
    return detail

# ---- Bacteriological detail fetching ----
def fetch_bacteriological_detail(session, facility, delay):
    samples = []
    next_url = facility["details_url"]
    current_start = 0
    page_size = 30

    while next_url:
        soup = fetch(session, next_url)
        tables = soup.find_all("table")

        for table in tables:
            if "Current Hazard Rating:" in table.get_text(" ", strip=True):
                facility.update(parse_key_value_table(table))

        sample_table = None
        for table in tables:
            if "Total Coliform" in table.get_text(" ", strip=True):
                sample_table = table
                break
        page_rows = []
        if sample_table:
            page_rows = parse_bacteriological_sample_rows(sample_table)
            for row in page_rows:
                if len(row) >= 5:
                    samples.append({
                        "location": row[0],
                        "date": row[1],
                        "total_coliform": row[2],
                        "fecal_coliform": row[3],
                        "e_coli": row[4],
                    })

        if len(page_rows) < page_size:
            break

        from urllib.parse import urlparse, urlunparse, urlencode
        next_link = None
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.startswith("/"):
                href = urljoin(BASE_URL, href)
            else:
                href = urljoin(BASE_URL, href)
            query = parse_qs(urlparse(href).query)
            start_values = query.get("start") or query.get("Start")
            if not start_values:
                continue
            try:
                link_start = int(start_values[0])
            except ValueError:
                continue
            if link_start > current_start:
                next_link = href
                current_start = link_start
                break
        if not next_link or next_link == next_url:
            break
        next_url = next_link
        time.sleep(delay)

    return {
        "samples": samples,
        "samples_fetched_at": datetime.now().isoformat(),
        "details_fetched_at": datetime.now().isoformat(),
    }

# ---- Chemical detail fetching ----
def fetch_chemical_detail(session, facility, fetch_results, delay):
    soup = fetch(session, facility["details_url"])
    result_packages = []

    table = soup.find("table")
    if table:
        for row in table.find_all("tr")[1:]:
            cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
            link = row.find("a", href=True)
            if len(cells) < 2:
                continue
            package = {
                "name": cells[0],
                "date": cells[1],
                "details_url": urljoin(BASE_URL, link["href"]) if link else None,
            }
            if fetch_results and package.get("details_url"):
                time.sleep(delay)
                package["results"] = fetch_chemical_results(session, package["details_url"])
                package["results_fetched_at"] = datetime.now().isoformat()
            result_packages.append(package)

    return {
        "chemical_result_packages": result_packages,
        "details_fetched_at": datetime.now().isoformat(),
    }

def fetch_chemical_results(session, url):
    soup = fetch(session, url)
    results = []
    table = soup.find("table")
    if not table:
        return results
    for row in table.find_all("tr")[1:]:
        cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in row.find_all("td")]
        if not cells:
            continue
        result = {"type": cells[0]}
        if len(cells) >= 2:
            result["value"] = cells[1]
        results.append(result)
    if results:
        return results

    cells = [normalize_space(cell.get_text(" ", strip=True)) for cell in table.find_all("td")]
    cells = cells[2:]
    for index in range(0, len(cells), 2):
        pair = cells[index:index + 2]
        if len(pair) < 2 or not pair[0]:
            continue
        results.append({"type": pair[0], "value": pair[1]})
    return results

def fetch_inspection_report(session, url):
    soup = fetch(session, url)
    report = {}

    h2 = soup.find("h2")
    if h2:
        report["title"] = normalize_space(h2.get_text(" ", strip=True))

    tables = soup.find_all("table")
    if tables:
        report.update(parse_key_value_table(tables[0]))

    page_text = soup.get_text(" ", strip=True)
    if "No violations were found" in page_text:
        report["violations"] = []

    report["details_fetched_at"] = datetime.now().isoformat()
    return report

def fetch_nested_inspection_reports(session, record, delay):
    inspections = record.get("inspections") or []
    for inspection in inspections:
        if not inspection.get("details_url") or inspection.get("details"):
            continue
        time.sleep(delay)
        inspection["details"] = fetch_inspection_report(session, inspection["details_url"])
    return {
        "inspections": inspections,
        "details_fetched_at": record.get("details_fetched_at") or datetime.now().isoformat(),
    }

# ---- Main ----
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def needs_nested_chemical_results(record):
    packages = record.get("chemical_result_packages") or []
    return any(package.get("details_url") and not package.get("results_fetched_at") for package in packages)

def needs_nested_inspection_reports(record):
    inspections = record.get("inspections") or []
    return any(inspection.get("details_url") and not inspection.get("details") for inspection in inspections)

def needs_bacteriological_samples(record):
    return bool(record.get("details_url")) and not record.get("samples_fetched_at")

def main():
    parser = argparse.ArgumentParser(description="Fetch water detail pages")
    parser.add_argument("--input", required=True, help="Input JSON file with facility records")
    parser.add_argument("--output", help="Output JSON file (default: overwrite input)")
    parser.add_argument("--dataset", choices=["notices", "drinking", "bacteriological", "chemical"], required=True)
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests")
    parser.add_argument(
        "--nested-details",
        action="store_true",
        help="Fetch chemical result values or nested notice/drinking inspection report pages",
    )
    parser.add_argument("--limit", type=int, help="Max facilities to process")
    parser.add_argument("--force", action="store_true", help="Refetch already-fetched records")
    return parser.parse_args()

if __name__ == "__main__":
    args = main()
    session = make_session()
    output_path = Path(args.output) if args.output else Path(args.input)

    data = load_json(args.input)
    print(f"Loaded {len(data)} records from {args.input}")

    already = sum(1 for d in data if d.get("details_fetched_at"))
    print(f"Already fetched: {already}, remaining: {len(data) - already}")

    processed = 0
    errors = 0
    skipped = 0

    records = data if args.limit is None else data[:args.limit]

    for i, record in enumerate(records):
        name = record.get("name", "Unknown")
        city = record.get("city", "?")

        needs_nested = (
            args.nested_details
            and (
                (args.dataset == "chemical" and needs_nested_chemical_results(record))
                or (args.dataset in {"notices", "drinking"} and needs_nested_inspection_reports(record))
                or (args.dataset == "bacteriological" and needs_bacteriological_samples(record))
            )
        )

        if not args.force and record.get("details_fetched_at") and not record.get("fetch_error") and not needs_nested:
            skipped += 1
            continue

        url = record.get("details_url")
        if not url:
            skipped += 1
            continue

        print(f"[{i+1}/{len(records)}] {city}/{name}")
        try:
            if args.dataset == "notices":
                if args.nested_details and record.get("details_fetched_at"):
                    record.update(fetch_nested_inspection_reports(session, record, args.delay))
                else:
                    record.update(fetch_notice_detail(session, record, args.delay))
                    if args.nested_details:
                        record.update(fetch_nested_inspection_reports(session, record, args.delay))
            elif args.dataset == "bacteriological":
                record.update(fetch_bacteriological_detail(session, record, args.delay))
            elif args.dataset == "chemical":
                record.update(fetch_chemical_detail(session, record, args.nested_details, args.delay))
            elif args.dataset == "drinking":
                if args.nested_details and record.get("details_fetched_at"):
                    record.update(fetch_nested_inspection_reports(session, record, args.delay))
                else:
                    from download_water_data import parse_drinking_detail
                    record.update(parse_drinking_detail(session, record, False, args.delay))
                    if args.nested_details:
                        record.update(fetch_nested_inspection_reports(session, record, args.delay))
            record.pop("fetch_error", None)
            processed += 1
        except Exception as exc:
            record["fetch_error"] = str(exc)
            record["fetch_error_at"] = datetime.now().isoformat()
            errors += 1
            print(f"  ERROR: {exc}")

        if (processed + errors) % 10 == 0:
            save_json(data, output_path)
            print(f"  [checkpoint saved]")

        time.sleep(args.delay)

    save_json(data, output_path)
    print(f"\nDone. Processed: {processed}, skipped: {skipped}, errors: {errors}")
    print(f"Saved to {output_path}")
