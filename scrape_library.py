#!/usr/bin/env python3
"""
Small Scrapling-backed scrape library for PGFoodHealth.

It stores reusable scrape templates, scheduled jobs, and run history as JSON
files so the Flask API can show what ran and trigger/schedule future scrapes.
"""

from __future__ import annotations

import json
import os
import threading
import time
import traceback
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

try:
    from scrapling.fetchers import DynamicFetcher, Fetcher, StealthyFetcher
except Exception:  # pragma: no cover - runtime dependency may be absent locally
    DynamicFetcher = Fetcher = StealthyFetcher = None

try:
    import requests
except Exception:  # pragma: no cover
    requests = None


DATA_DIR = Path(os.environ.get("SCRAPE_LIBRARY_DIR", "data/scrape_library"))
TEMPLATES_PATH = DATA_DIR / "templates.json"
JOBS_PATH = DATA_DIR / "jobs.json"
RUNS_DIR = DATA_DIR / "runs"

SCHEDULE_TYPES = {"manual", "interval", "daily"}
FETCHERS = {"fetcher", "stealthy", "dynamic"}


DEFAULT_TEMPLATES = [
    {
        "id": "example-domain",
        "name": "Example Domain",
        "description": "Basic smoke-test template for verifying Scrapling extraction.",
        "url": "https://example.com",
        "fetcher": "fetcher",
        "selectors": [
            {"name": "heading", "selector": "h1", "type": "css", "text": True},
            {"name": "link_url", "selector": "a", "type": "css", "attribute": "href"},
        ],
        "options": {"timeout": 30},
        "tags": ["smoke-test"],
    },
    {
        "id": "healthspace-prince-george-food-list",
        "name": "HealthSpace Prince George Food List",
        "description": "Scrapes visible rows from the Northern Health Prince George food facility list.",
        "url": (
            "https://www.healthspace.ca/Clients/NHA/NHA_Website.nsf/Food-List-ByName"
            "?OpenView&RestrictToCategory=FD4BF9F2DD74F5A2FC5B1DE44C0A8E31&Count=30"
        ),
        "fetcher": "stealthy",
        "selectors": [
            {"name": "rows", "selector": "table tr", "type": "css", "text": True},
            {"name": "detail_links", "selector": "table a", "type": "css", "attribute": "href"},
        ],
        "options": {"timeout": 45},
        "tags": ["healthspace", "restaurants", "prince-george"],
    },
    {
        "id": "healthspace-active-water-notices",
        "name": "HealthSpace Active Water Notices",
        "description": "Scrapes visible rows from the active drinking-water notices page.",
        "url": "https://www.healthspace.ca/Clients/NHA/NHA_Website.nsf/Water-Drinking-Notices-List",
        "fetcher": "stealthy",
        "selectors": [
            {"name": "rows", "selector": "table tr", "type": "css", "text": True},
            {"name": "links", "selector": "table a", "type": "css", "attribute": "href"},
        ],
        "options": {"timeout": 45},
        "tags": ["healthspace", "water"],
    },
]


def utcnow() -> datetime:
    return datetime.utcnow()


def iso_now() -> str:
    return utcnow().replace(microsecond=0).isoformat() + "Z"


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    if not TEMPLATES_PATH.exists():
        write_json(TEMPLATES_PATH, DEFAULT_TEMPLATES)
    if not JOBS_PATH.exists():
        write_json(JOBS_PATH, [])


def read_json(path: Path, default: Any) -> Any:
    ensure_storage_dirs_only()
    if not path.exists():
        return deepcopy(default)
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp_path.replace(path)


def ensure_storage_dirs_only() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    return "-".join(part for part in cleaned.split("-") if part)[:80] or "scrape"


def make_id(prefix: str) -> str:
    stamp = utcnow().strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{os.urandom(3).hex()}"


def list_templates() -> list[dict[str, Any]]:
    ensure_storage()
    return read_json(TEMPLATES_PATH, DEFAULT_TEMPLATES)


def get_template(template_id: str) -> dict[str, Any] | None:
    for template in list_templates():
        if template.get("id") == template_id:
            return template
    return None


def save_template(input_data: dict[str, Any]) -> dict[str, Any]:
    ensure_storage()
    templates = list_templates()
    template = normalize_template(input_data)
    existing_index = next((i for i, item in enumerate(templates) if item.get("id") == template["id"]), None)
    if existing_index is None:
        template["created_at"] = iso_now()
        templates.append(template)
    else:
        previous = templates[existing_index]
        template["created_at"] = previous.get("created_at") or iso_now()
        templates[existing_index] = template
    template["updated_at"] = iso_now()
    write_json(TEMPLATES_PATH, templates)
    return template


def delete_template(template_id: str) -> bool:
    templates = list_templates()
    next_templates = [template for template in templates if template.get("id") != template_id]
    if len(next_templates) == len(templates):
        return False
    write_json(TEMPLATES_PATH, next_templates)
    return True


def normalize_template(input_data: dict[str, Any]) -> dict[str, Any]:
    name = str(input_data.get("name") or "").strip()
    if not name:
        raise ValueError("Template name is required")
    url = str(input_data.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise ValueError("Template URL must start with http:// or https://")
    selectors = input_data.get("selectors")
    if not isinstance(selectors, list) or not selectors:
        raise ValueError("At least one selector is required")

    fetcher = str(input_data.get("fetcher") or "fetcher").lower()
    if fetcher not in FETCHERS:
        raise ValueError(f"Fetcher must be one of: {', '.join(sorted(FETCHERS))}")

    return {
        "id": str(input_data.get("id") or slugify(name)).strip(),
        "name": name,
        "description": str(input_data.get("description") or "").strip(),
        "url": url,
        "fetcher": fetcher,
        "selectors": [normalize_selector(selector) for selector in selectors],
        "options": dict(input_data.get("options") or {}),
        "tags": list(input_data.get("tags") or []),
        "output_path": input_data.get("output_path") or None,
    }


def normalize_selector(selector: dict[str, Any]) -> dict[str, Any]:
    name = str(selector.get("name") or "").strip()
    css_selector = str(selector.get("selector") or "").strip()
    if not name or not css_selector:
        raise ValueError("Selector name and selector are required")
    selector_type = str(selector.get("type") or "css").lower()
    if selector_type not in {"css", "xpath"}:
        raise ValueError("Selector type must be css or xpath")
    return {
        "name": name,
        "selector": css_selector,
        "type": selector_type,
        "attribute": selector.get("attribute") or None,
        "text": bool(selector.get("text", not selector.get("attribute"))),
        "multiple": bool(selector.get("multiple", True)),
    }


def list_jobs() -> list[dict[str, Any]]:
    ensure_storage()
    return read_json(JOBS_PATH, [])


def get_job(job_id: str) -> dict[str, Any] | None:
    for job in list_jobs():
        if job.get("id") == job_id:
            return job
    return None


def save_job(input_data: dict[str, Any]) -> dict[str, Any]:
    ensure_storage()
    jobs = list_jobs()
    job = normalize_job(input_data)
    existing_index = next((i for i, item in enumerate(jobs) if item.get("id") == job["id"]), None)

    if existing_index is None:
        job["created_at"] = iso_now()
        job["last_run_id"] = None
        jobs.append(job)
    else:
        previous = jobs[existing_index]
        job["created_at"] = previous.get("created_at") or iso_now()
        job["last_run_id"] = previous.get("last_run_id")
        jobs[existing_index] = job

    job["updated_at"] = iso_now()
    job["next_run_at"] = compute_next_run(job)
    write_json(JOBS_PATH, jobs)
    return job


def delete_job(job_id: str) -> bool:
    jobs = list_jobs()
    next_jobs = [job for job in jobs if job.get("id") != job_id]
    if len(next_jobs) == len(jobs):
        return False
    write_json(JOBS_PATH, next_jobs)
    return True


def normalize_job(input_data: dict[str, Any]) -> dict[str, Any]:
    template_id = str(input_data.get("template_id") or input_data.get("templateId") or "").strip()
    if not get_template(template_id):
        raise ValueError(f"Unknown template: {template_id}")

    name = str(input_data.get("name") or template_id).strip()
    schedule_type = str(input_data.get("schedule_type") or input_data.get("scheduleType") or "manual").lower()
    if schedule_type not in SCHEDULE_TYPES:
        raise ValueError(f"Schedule type must be one of: {', '.join(sorted(SCHEDULE_TYPES))}")

    interval_minutes = input_data.get("interval_minutes", input_data.get("intervalMinutes"))
    if schedule_type == "interval":
        interval_minutes = max(1, int(interval_minutes or 60))
    else:
        interval_minutes = None

    daily_time = input_data.get("daily_time") or input_data.get("dailyTime")
    if schedule_type == "daily":
        daily_time = str(daily_time or "02:00")
        if not valid_daily_time(daily_time):
            raise ValueError("daily_time must use HH:MM")
    else:
        daily_time = None

    return {
        "id": str(input_data.get("id") or make_id("job")).strip(),
        "name": name,
        "template_id": template_id,
        "enabled": bool(input_data.get("enabled", schedule_type != "manual")),
        "schedule_type": schedule_type,
        "interval_minutes": interval_minutes,
        "daily_time": daily_time,
        "overrides": dict(input_data.get("overrides") or {}),
    }


def valid_daily_time(value: str) -> bool:
    try:
        hour, minute = value.split(":", 1)
        return 0 <= int(hour) <= 23 and 0 <= int(minute) <= 59
    except Exception:
        return False


def compute_next_run(job: dict[str, Any], after: datetime | None = None) -> str | None:
    if not job.get("enabled") or job.get("schedule_type") == "manual":
        return None

    base = after or utcnow()
    if job.get("schedule_type") == "interval":
        return (base + timedelta(minutes=int(job.get("interval_minutes") or 60))).replace(microsecond=0).isoformat() + "Z"

    if job.get("schedule_type") == "daily":
        hour, minute = [int(part) for part in str(job.get("daily_time") or "02:00").split(":", 1)]
        candidate = base.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base:
            candidate += timedelta(days=1)
        return candidate.isoformat() + "Z"

    return None


def run_template(template_id: str, overrides: dict[str, Any] | None = None, job_id: str | None = None) -> dict[str, Any]:
    template = get_template(template_id)
    if not template:
        raise ValueError(f"Unknown template: {template_id}")

    config = deepcopy(template)
    overrides = overrides or {}
    config.update({key: value for key, value in overrides.items() if value is not None})
    if overrides.get("options"):
        config["options"] = {**template.get("options", {}), **overrides["options"]}

    run = {
        "id": make_id("run"),
        "job_id": job_id,
        "template_id": template_id,
        "template_name": template.get("name"),
        "url": config.get("url"),
        "fetcher": config.get("fetcher"),
        "started_at": iso_now(),
        "finished_at": None,
        "status": "running",
        "error": None,
        "result": None,
    }

    try:
        result = scrape_url(config)
        run["status"] = "success"
        run["result"] = result
        output_path = config.get("output_path")
        if output_path:
            write_json(Path(output_path), result)
            run["output_path"] = output_path
    except Exception as exc:
        run["status"] = "error"
        run["error"] = str(exc)
        run["traceback"] = traceback.format_exc(limit=5)
    finally:
        run["finished_at"] = iso_now()
        save_run(run)
        if job_id:
            update_job_after_run(job_id, run["id"])

    return run


def scrape_url(config: dict[str, Any]) -> dict[str, Any]:
    fetcher_name = str(config.get("fetcher") or "fetcher").lower()
    url = config["url"]
    options = config.get("options") or {}
    selectors = [normalize_selector(selector) for selector in config.get("selectors") or []]

    page = fetch_page(url, fetcher_name, options)
    extracted = {}
    for selector in selectors:
        extracted[selector["name"]] = extract_selector(page, selector, url)

    return {
        "url": url,
        "fetched_at": iso_now(),
        "fetcher": fetcher_name,
        "data": extracted,
    }


def fetch_page(url: str, fetcher_name: str, options: dict[str, Any]) -> Any:
    timeout = int(options.get("timeout") or 30)

    if Fetcher:
        fetcher_cls = {
            "fetcher": Fetcher,
            "stealthy": StealthyFetcher or Fetcher,
            "dynamic": DynamicFetcher or Fetcher,
        }.get(fetcher_name, Fetcher)
        if hasattr(fetcher_cls, "get"):
            request_kwargs = {"timeout": timeout}
            return fetcher_cls.get(url, **request_kwargs)
        if hasattr(fetcher_cls, "fetch"):
            request_kwargs = {"timeout": timeout * 1000}
            return fetcher_cls.fetch(url, **request_kwargs)
        raise RuntimeError(f"Scrapling fetcher {fetcher_name} does not support get or fetch")

    if not requests:
        raise RuntimeError("Install scrapling[fetchers] or requests to run scrape templates")

    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_selector(page: Any, selector: dict[str, Any], base_url: str) -> list[str]:
    raw_selector = selector["selector"]
    if selector["type"] == "xpath":
        nodes = page.xpath(raw_selector) if hasattr(page, "xpath") else []
    elif hasattr(page, "css"):
        nodes = page.css(raw_selector)
    else:
        nodes = page.select(raw_selector)

    values = []
    for node in nodes:
        attribute = selector.get("attribute")
        if attribute:
            value = get_attribute(node, attribute)
            if attribute in {"href", "src"} and value:
                value = urljoin(base_url, value)
        else:
            value = get_text(node)
        if value:
            values.append(value)
        if not selector.get("multiple", True):
            break
    return values


def get_attribute(node: Any, attribute: str) -> str | None:
    try:
        value = node.attrib.get(attribute)
    except Exception:
        value = None
    if value is None:
        try:
            value = node.get(attribute)
        except Exception:
            value = None
    return str(value).strip() if value is not None else None


def get_text(node: Any) -> str:
    try:
        return node.get_all_text().strip()
    except Exception:
        pass
    try:
        return node.get_text(" ", strip=True)
    except Exception:
        return str(node).strip()


def save_run(run: dict[str, Any]) -> None:
    ensure_storage()
    write_json(RUNS_DIR / f"{run['id']}.json", run)


def list_runs(job_id: str | None = None, template_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    ensure_storage()
    runs = []
    for path in RUNS_DIR.glob("run-*.json"):
        try:
            run = read_json(path, {})
        except Exception:
            continue
        if job_id and run.get("job_id") != job_id:
            continue
        if template_id and run.get("template_id") != template_id:
            continue
        runs.append(run)
    runs.sort(key=lambda item: item.get("started_at") or "", reverse=True)
    return runs[: max(1, min(limit, 500))]


def get_run(run_id: str) -> dict[str, Any] | None:
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    return read_json(path, {})


def update_job_after_run(job_id: str, run_id: str) -> None:
    jobs = list_jobs()
    for job in jobs:
        if job.get("id") == job_id:
            job["last_run_id"] = run_id
            job["last_run_at"] = iso_now()
            job["next_run_at"] = compute_next_run(job)
            job["updated_at"] = iso_now()
            break
    write_json(JOBS_PATH, jobs)


_scheduler_lock = threading.Lock()
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()


def start_scheduler(poll_seconds: int = 60) -> bool:
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return False
        _scheduler_stop.clear()
        _scheduler_thread = threading.Thread(
            target=scheduler_loop,
            args=(poll_seconds,),
            name="scrape-library-scheduler",
            daemon=True,
        )
        _scheduler_thread.start()
        return True


def stop_scheduler() -> None:
    _scheduler_stop.set()


def scheduler_status() -> dict[str, Any]:
    return {
        "running": bool(_scheduler_thread and _scheduler_thread.is_alive()),
        "poll_seconds": int(os.environ.get("SCRAPE_SCHEDULER_POLL_SECONDS", "60")),
    }


def scheduler_loop(poll_seconds: int) -> None:
    ensure_storage()
    while not _scheduler_stop.is_set():
        run_due_jobs()
        _scheduler_stop.wait(poll_seconds)


def run_due_jobs() -> list[dict[str, Any]]:
    now = utcnow()
    due_jobs = []
    for job in list_jobs():
        next_run = parse_iso(job.get("next_run_at"))
        if job.get("enabled") and next_run and next_run <= now:
            due_jobs.append(job)

    runs = []
    for job in due_jobs:
        runs.append(run_template(job["template_id"], overrides=job.get("overrides") or {}, job_id=job["id"]))
    return runs
