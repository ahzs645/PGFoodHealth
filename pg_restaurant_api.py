#!/usr/bin/env python3
"""
Simple Flask API for Prince George Restaurant Inspection Data
Serves the scraped HealthSpace data as a REST API
"""

from flask import Flask, jsonify, request, render_template_string
import json
import os
from datetime import datetime
import scrape_library
from healthspace_pg_restaurants import HealthSpaceAPI

app = Flask(__name__)

SCRAPES_UI_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PGFoodHealth Scrapes</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --line: #d9dee6;
      --text: #17202a;
      --muted: #5b6675;
      --accent: #1769aa;
      --accent-strong: #0f4f83;
      --ok: #0b7f4f;
      --error: #aa2f2f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    header {
      padding: 20px 24px 12px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1, h2, h3 { margin: 0; letter-spacing: 0; }
    h1 { font-size: 22px; }
    h2 { font-size: 16px; margin-bottom: 12px; }
    h3 { font-size: 14px; margin-bottom: 6px; }
    main {
      display: grid;
      grid-template-columns: minmax(320px, 440px) 1fr;
      gap: 16px;
      padding: 16px;
      max-width: 1440px;
      margin: 0 auto;
    }
    section, aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }
    label {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin: 10px 0 4px;
    }
    input, select, textarea, button {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: #fff;
      color: var(--text);
    }
    button {
      border-color: var(--accent);
      background: var(--accent);
      color: white;
      cursor: pointer;
      font-weight: 600;
    }
    button.secondary {
      background: white;
      color: var(--accent-strong);
    }
    button:disabled { opacity: .6; cursor: wait; }
    .row { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 14px; }
    .muted { color: var(--muted); }
    .status { margin-top: 10px; min-height: 20px; color: var(--muted); }
    .status.ok { color: var(--ok); }
    .status.error { color: var(--error); }
    .stack { display: grid; gap: 12px; }
    .item {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fff;
    }
    .item-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 4px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      border-radius: 999px;
      padding: 2px 8px;
      background: #eef3f8;
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
    }
    .pill.ok { background: #e8f5ee; color: var(--ok); }
    .pill.error { background: #f8eaea; color: var(--error); }
    pre {
      overflow: auto;
      max-height: 220px;
      background: #101820;
      color: #eef6ff;
      padding: 10px;
      border-radius: 6px;
      font-size: 12px;
    }
    .tabs { display: flex; gap: 8px; margin-bottom: 12px; }
    .tabs button { width: auto; padding: 7px 10px; }
    .tabs button[aria-selected="false"] { background: white; color: var(--accent-strong); }
    .hidden { display: none; }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
      .row, .actions { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>PGFoodHealth Scrapes</h1>
    <div class="muted">Create city-scoped HealthSpace scrape templates, schedule them, and inspect run history.</div>
  </header>
  <main>
    <aside>
      <h2>HealthSpace Options</h2>
      <form id="healthspace-form">
        <label for="dataset">Dataset</label>
        <select id="dataset" name="dataset">
          <option value="food">Food establishments</option>
          <option value="water_notices">Active water notices</option>
        </select>

        <label for="city">City scope</label>
        <select id="city" name="city"></select>

        <div class="row">
          <div>
            <label for="count">Rows per page</label>
            <input id="count" name="count" type="number" min="1" max="200" value="30">
          </div>
          <div>
            <label for="fetcher">Fetcher</label>
            <select id="fetcher" name="fetcher">
              <option value="stealthy">Stealthy</option>
              <option value="fetcher">Fetcher</option>
              <option value="dynamic">Dynamic</option>
            </select>
          </div>
        </div>

        <label for="template-name">Template name</label>
        <input id="template-name" name="name" placeholder="HealthSpace Prince George Food List">

        <label for="output-path">Optional output JSON path</label>
        <input id="output-path" name="output_path" placeholder="data/scrape_library/exports/prince_george_food.json">

        <label for="schedule-type">Schedule</label>
        <select id="schedule-type" name="schedule_type">
          <option value="manual">Manual only</option>
          <option value="interval">Interval</option>
          <option value="daily">Daily</option>
        </select>

        <div class="row">
          <div>
            <label for="interval-minutes">Interval minutes</label>
            <input id="interval-minutes" name="interval_minutes" type="number" min="1" value="1440">
          </div>
          <div>
            <label for="daily-time">Daily time</label>
            <input id="daily-time" name="daily_time" type="time" value="02:00">
          </div>
        </div>

        <div class="actions">
          <button type="submit">Save Template</button>
          <button type="button" class="secondary" id="save-run">Save + Run</button>
        </div>
        <div id="form-status" class="status"></div>
      </form>
    </aside>

    <section>
      <div class="tabs">
        <button type="button" data-tab="templates" aria-selected="true">Templates</button>
        <button type="button" data-tab="jobs" aria-selected="false">Schedules</button>
        <button type="button" data-tab="runs" aria-selected="false">Runs</button>
      </div>
      <div id="templates-panel" class="stack"></div>
      <div id="jobs-panel" class="stack hidden"></div>
      <div id="runs-panel" class="stack hidden"></div>
    </section>
  </main>

  <script>
    const state = { templates: [], jobs: [], runs: [], options: null };
    const $ = (id) => document.getElementById(id);

    function setStatus(text, type = "") {
      const el = $("form-status");
      el.textContent = text;
      el.className = `status ${type}`;
    }

    function defaultTemplateName() {
      const dataset = $("dataset").value;
      const city = $("city").value || "Prince George";
      return dataset === "food"
        ? `HealthSpace ${city} Food List`
        : "HealthSpace Active Water Notices";
    }

    function syncTemplateName() {
      if (!$("template-name").value.trim()) $("template-name").value = defaultTemplateName();
    }

    async function api(path, options = {}) {
      const response = await fetch(path, {
        headers: { "content-type": "application/json", ...(options.headers || {}) },
        ...options,
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `Request failed: ${response.status}`);
      return body;
    }

    function formPayload() {
      const scheduleType = $("schedule-type").value;
      return {
        dataset: $("dataset").value,
        city: $("city").value,
        count: Number($("count").value || 30),
        fetcher: $("fetcher").value,
        name: $("template-name").value.trim() || defaultTemplateName(),
        output_path: $("output-path").value.trim() || null,
        create_job: scheduleType !== "manual",
        schedule_type: scheduleType,
        interval_minutes: Number($("interval-minutes").value || 1440),
        daily_time: $("daily-time").value || "02:00",
      };
    }

    async function saveTemplate(runAfter = false) {
      setStatus("Saving...");
      const body = await api("/scrapes/healthspace-template", {
        method: "POST",
        body: JSON.stringify(formPayload()),
      });
      if (runAfter) {
        setStatus("Running scrape...");
        await api(`/scrapes/templates/${body.template.id}/run`, { method: "POST", body: "{}" });
      }
      await refresh();
      setStatus(runAfter ? "Template saved and scrape completed." : "Template saved.", "ok");
    }

    function renderTemplates() {
      $("templates-panel").innerHTML = state.templates.map((template) => `
        <article class="item">
          <div class="item-title">
            <h3>${escapeHtml(template.name)}</h3>
            <span class="pill">${escapeHtml(template.fetcher || "fetcher")}</span>
          </div>
          <div class="muted">${escapeHtml(template.description || "")}</div>
          <div class="muted">${escapeHtml(template.url || "")}</div>
          <div class="actions">
            <button type="button" onclick="runTemplate('${template.id}')">Run Now</button>
            <button type="button" class="secondary" onclick="loadTemplate('${template.id}')">Load Options</button>
          </div>
        </article>
      `).join("") || "<div class='muted'>No templates yet.</div>";
    }

    function renderJobs() {
      $("jobs-panel").innerHTML = state.jobs.map((job) => `
        <article class="item">
          <div class="item-title">
            <h3>${escapeHtml(job.name)}</h3>
            <span class="pill">${job.enabled ? "enabled" : "disabled"}</span>
          </div>
          <div class="muted">Template: ${escapeHtml(job.template_id)}</div>
          <div class="muted">Schedule: ${escapeHtml(formatSchedule(job))}</div>
          <div class="muted">Next run: ${escapeHtml(job.next_run_at || "not scheduled")}</div>
          <div class="actions">
            <button type="button" onclick="runJob('${job.id}')">Run Job</button>
            <button type="button" class="secondary" onclick="deleteJob('${job.id}')">Delete</button>
          </div>
        </article>
      `).join("") || "<div class='muted'>No scheduled jobs yet.</div>";
    }

    function renderRuns() {
      $("runs-panel").innerHTML = state.runs.map((run) => {
        const data = run.result && run.result.data ? run.result.data : {};
        return `
          <article class="item">
            <div class="item-title">
              <h3>${escapeHtml(run.template_name || run.template_id || run.id)}</h3>
              <span class="pill ${run.status === "success" ? "ok" : "error"}">${escapeHtml(run.status)}</span>
            </div>
            <div class="muted">${escapeHtml(run.started_at || "")}</div>
            ${run.error ? `<div class="status error">${escapeHtml(run.error)}</div>` : ""}
            <pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>
          </article>
        `;
      }).join("") || "<div class='muted'>No runs yet.</div>";
    }

    function formatSchedule(job) {
      if (job.schedule_type === "interval") return `Every ${job.interval_minutes || 60} minutes`;
      if (job.schedule_type === "daily") return `Daily at ${job.daily_time || "02:00"}`;
      return "Manual";
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      })[ch]);
    }

    async function runTemplate(id) {
      setStatus("Running scrape...");
      await api(`/scrapes/templates/${id}/run`, { method: "POST", body: "{}" });
      await refresh();
      setStatus("Scrape completed.", "ok");
    }

    async function runJob(id) {
      setStatus("Running scheduled job...");
      await api(`/scrapes/jobs/${id}/run`, { method: "POST", body: "{}" });
      await refresh();
      setStatus("Job completed.", "ok");
    }

    async function deleteJob(id) {
      await api(`/scrapes/jobs/${id}`, { method: "DELETE" });
      await refresh();
      setStatus("Schedule deleted.", "ok");
    }

    function loadTemplate(id) {
      const template = state.templates.find((item) => item.id === id);
      if (!template) return;
      $("template-name").value = template.name || "";
      $("fetcher").value = template.fetcher || "stealthy";
      $("output-path").value = template.output_path || "";
      setStatus("Template loaded. Adjust options and save to create a new version.", "ok");
    }

    async function refresh() {
      const [templates, jobs, runs] = await Promise.all([
        api("/scrapes/templates"),
        api("/scrapes/jobs"),
        api("/scrapes/runs?limit=10"),
      ]);
      state.templates = templates.templates || [];
      state.jobs = jobs.jobs || [];
      state.runs = runs.runs || [];
      renderTemplates();
      renderJobs();
      renderRuns();
    }

    async function boot() {
      state.options = await api("/scrapes/options");
      $("city").innerHTML = state.options.cities.map((city) =>
        `<option value="${escapeHtml(city.name)}" ${city.name === "Prince George" ? "selected" : ""}>${escapeHtml(city.name)}</option>`
      ).join("");
      syncTemplateName();
      await refresh();
    }

    document.querySelectorAll(".tabs button").forEach((button) => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tabs button").forEach((item) => item.setAttribute("aria-selected", "false"));
        button.setAttribute("aria-selected", "true");
        ["templates", "jobs", "runs"].forEach((tab) => {
          $(`${tab}-panel`).classList.toggle("hidden", tab !== button.dataset.tab);
        });
      });
    });

    $("dataset").addEventListener("change", () => {
      $("city").disabled = $("dataset").value !== "food";
      $("template-name").value = "";
      syncTemplateName();
    });
    $("city").addEventListener("change", () => { $("template-name").value = ""; syncTemplateName(); });
    $("healthspace-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      try { await saveTemplate(false); } catch (error) { setStatus(error.message, "error"); }
    });
    $("save-run").addEventListener("click", async () => {
      try { await saveTemplate(true); } catch (error) { setStatus(error.message, "error"); }
    });

    boot().catch((error) => setStatus(error.message, "error"));
  </script>
</body>
</html>
"""

# Load restaurant data
def load_data():
    """Load restaurant data from JSON file"""
    if os.path.exists('pg_restaurants.json'):
        with open('pg_restaurants.json', 'r') as f:
            return json.load(f)
    return []

@app.route('/')
def home():
    """API documentation"""
    return jsonify({
        'name': 'Prince George Restaurant Inspection API',
        'version': '2.0',
        'endpoints': {
            '/restaurants': 'Get all restaurants',
            '/restaurants/<name>': 'Search restaurants by name (fuzzy match)',
            '/restaurants/hazard/<rating>': 'Filter by hazard rating (Low/Moderate/Unknown)',
            '/restaurants/stats': 'Get statistics about the dataset',
            '/restaurants/refresh': 'Trigger a refresh of the data (POST)',
            '/restaurants/refresh-deep': 'Trigger deep refresh with inspections & violations (POST)',
            '/restaurant/<name>': 'Get single restaurant with full inspection history',
            '/inspections': 'Get all inspections across all restaurants',
            '/inspections/recent': 'Get most recent inspections',
            '/violations': 'Get all violations across all restaurants',
            '/violations/stats': 'Get violation statistics',
            '/search/live?q=<query>': 'Search live HealthSpace site (not cached)',
            '/search/live?q=<query>&details=true': 'Search live with full inspection details',
            '/restaurant/<name>/fetch': 'Fetch fresh data for a restaurant from live site',
            '/cities': 'List all cities in Northern Health',
            '/cities/<city>/restaurants': 'Get restaurants for a specific city (live fetch)',
            '/scrapes/templates': 'List or create reusable Scrapling scrape templates',
            '/scrapes/jobs': 'List or create scheduled scrape jobs',
            '/scrapes/jobs/<id>/run': 'Run a scrape job now',
            '/scrapes/runs': 'List scrape run history',
            '/scrapes/scheduler': 'View or control the scrape scheduler'
        },
        'data_source': 'Northern Health Authority HealthSpace',
        'last_updated': get_last_updated()
    })

@app.route('/scrapes')
def scrapes_ui():
    """Small browser interface for scrape templates, schedules, and runs."""
    return render_template_string(SCRAPES_UI_HTML)

@app.route('/scrapes/options')
def scrape_options():
    """Options used by the scrape interface."""
    cities = [
        {'name': name, 'category_id': category_id}
        for name, category_id in sorted(HealthSpaceAPI.CITIES.items())
    ]
    return jsonify({
        'cities': cities,
        'default_city': HealthSpaceAPI.DEFAULT_CITY,
        'datasets': [
            {'id': 'food', 'name': 'Food establishments', 'city_scoped': True},
            {'id': 'water_notices', 'name': 'Active water notices', 'city_scoped': False},
        ],
        'fetchers': sorted(scrape_library.FETCHERS),
        'schedule_types': sorted(scrape_library.SCHEDULE_TYPES),
    })

@app.route('/scrapes/healthspace-template', methods=['POST'])
def create_healthspace_template():
    """Create a HealthSpace scrape template from interface options."""
    body = request.get_json(force=True) or {}
    dataset = body.get('dataset') or 'food'
    fetcher = body.get('fetcher') or 'stealthy'
    output_path = body.get('output_path') or None

    if dataset == 'food':
        city = body.get('city') or HealthSpaceAPI.DEFAULT_CITY
        category_id = HealthSpaceAPI.CITIES.get(city)
        if not category_id:
            return jsonify({'error': f'Unknown city: {city}'}), 400
        count = max(1, min(int(body.get('count') or 30), 200))
        url = (
            'https://www.healthspace.ca/Clients/NHA/NHA_Website.nsf/Food-List-ByName'
            f'?OpenView&RestrictToCategory={category_id}&Count={count}'
        )
        template_name = body.get('name') or f'HealthSpace {city} Food List'
        template_id = body.get('id') or f"healthspace-food-{scrape_library.slugify(city)}"
        selectors = [
            {'name': 'rows', 'selector': 'table tr', 'type': 'css', 'text': True},
            {'name': 'detail_links', 'selector': 'table a', 'type': 'css', 'attribute': 'href'},
        ]
        tags = ['healthspace', 'restaurants', scrape_library.slugify(city)]
        description = f'Scrapes visible food-establishment rows for {city}.'
    elif dataset == 'water_notices':
        url = 'https://www.healthspace.ca/Clients/NHA/NHA_Website.nsf/Water-Drinking-Notices-List'
        template_name = body.get('name') or 'HealthSpace Active Water Notices'
        template_id = body.get('id') or 'healthspace-active-water-notices'
        selectors = [
            {'name': 'rows', 'selector': 'table tr', 'type': 'css', 'text': True},
            {'name': 'links', 'selector': 'table a', 'type': 'css', 'attribute': 'href'},
        ]
        tags = ['healthspace', 'water']
        description = 'Scrapes visible rows from active drinking-water notices.'
    else:
        return jsonify({'error': 'dataset must be food or water_notices'}), 400

    try:
        template = scrape_library.save_template({
            'id': template_id,
            'name': template_name,
            'description': description,
            'url': url,
            'fetcher': fetcher,
            'selectors': selectors,
            'options': {'timeout': int(body.get('timeout') or 45)},
            'tags': tags,
            'output_path': output_path,
        })

        job = None
        if body.get('create_job'):
            job = scrape_library.save_job({
                'id': body.get('job_id') or f"{template['id']}-schedule",
                'name': body.get('job_name') or f"{template['name']} schedule",
                'template_id': template['id'],
                'enabled': bool(body.get('enabled', True)),
                'schedule_type': body.get('schedule_type') or 'interval',
                'interval_minutes': body.get('interval_minutes'),
                'daily_time': body.get('daily_time'),
            })

        return jsonify({'template': template, 'job': job}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/restaurants')
def get_restaurants():
    """Get all restaurants with optional filtering"""
    data = load_data()

    # Optional query parameters
    hazard = request.args.get('hazard')
    search = request.args.get('search')
    limit = request.args.get('limit', type=int)

    # Filter by hazard rating
    if hazard:
        data = [r for r in data if r.get('hazard_rating', '').lower() == hazard.lower()]

    # Search by name or address
    if search:
        search = search.lower()
        data = [r for r in data if
                search in r.get('name', '').lower() or
                search in r.get('address', '').lower()]

    # Limit results
    if limit:
        data = data[:limit]

    return jsonify({
        'count': len(data),
        'restaurants': data
    })

@app.route('/restaurants/name/<name>')
def search_by_name(name):
    """Search restaurants by name (partial match)"""
    data = load_data()
    name = name.lower()

    results = [r for r in data if name in r.get('name', '').lower()]

    return jsonify({
        'query': name,
        'count': len(results),
        'restaurants': results
    })

@app.route('/restaurants/hazard/<rating>')
def filter_by_hazard(rating):
    """Filter restaurants by hazard rating"""
    data = load_data()
    rating = rating.lower()

    results = [r for r in data if r.get('hazard_rating', '').lower() == rating]

    return jsonify({
        'hazard_rating': rating,
        'count': len(results),
        'restaurants': results
    })

@app.route('/restaurants/stats')
def get_stats():
    """Get statistics about the restaurant data"""
    data = load_data()

    # Count by hazard rating
    hazard_counts = {}
    for restaurant in data:
        rating = restaurant.get('hazard_rating', 'Unknown')
        hazard_counts[rating] = hazard_counts.get(rating, 0) + 1

    return jsonify({
        'total_restaurants': len(data),
        'hazard_ratings': hazard_counts,
        'last_updated': get_last_updated()
    })

@app.route('/restaurants/refresh', methods=['POST'])
def refresh_data():
    """Trigger a refresh of the restaurant data"""
    import subprocess

    try:
        # Run the scraper script
        result = subprocess.run(
            ['python3', 'healthspace_pg_restaurants.py'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': 'Data refreshed successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to refresh data',
                'error': result.stderr
            }), 500

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/restaurants/refresh-deep', methods=['POST'])
def refresh_data_deep():
    """Trigger a deep refresh that fetches all inspection details and violations"""
    import subprocess

    # Get optional parameters
    max_restaurants = request.args.get('max_restaurants', type=int)

    try:
        # Build command with optional limits
        cmd = ['python3', '-c', '''
import sys
sys.path.insert(0, ".")
from healthspace_pg_restaurants import HealthSpaceAPI
api = HealthSpaceAPI()
data = api.get_all_restaurants_with_details(max_restaurants={max_restaurants}, max_inspections_per_restaurant=None)
if data:
    api.save_to_json(data, "pg_restaurants.json")
    print(f"Saved {{len(data)}} restaurants with full details")
else:
    print("Failed to fetch data")
    sys.exit(1)
'''.format(max_restaurants=max_restaurants if max_restaurants else 'None')]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for deep refresh
        )

        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': 'Deep refresh completed - data includes inspections and violations',
                'timestamp': datetime.now().isoformat(),
                'output': result.stdout
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to refresh data',
                'error': result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'status': 'error',
            'message': 'Deep refresh timed out (1 hour limit)'
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/restaurant/<name>')
def get_restaurant(name):
    """Get a single restaurant with full inspection history"""
    data = load_data()
    name_lower = name.lower()

    # Find exact or closest match
    exact_match = None
    partial_matches = []

    for r in data:
        r_name = r.get('name', '').lower()
        if r_name == name_lower:
            exact_match = r
            break
        elif name_lower in r_name:
            partial_matches.append(r)

    if exact_match:
        return jsonify({
            'found': True,
            'restaurant': exact_match
        })
    elif partial_matches:
        if len(partial_matches) == 1:
            return jsonify({
                'found': True,
                'restaurant': partial_matches[0]
            })
        else:
            return jsonify({
                'found': False,
                'message': f'Multiple matches found for "{name}"',
                'matches': [r.get('name') for r in partial_matches]
            })
    else:
        return jsonify({
            'found': False,
            'message': f'No restaurant found matching "{name}"'
        }), 404

@app.route('/inspections')
def get_all_inspections():
    """Get all inspections across all restaurants"""
    data = load_data()

    # Query parameters
    inspection_type = request.args.get('type')  # e.g., "Routine"
    hazard = request.args.get('hazard')
    has_violations = request.args.get('has_violations')
    limit = request.args.get('limit', type=int)

    all_inspections = []

    for restaurant in data:
        inspections = restaurant.get('inspections', [])
        for insp in inspections:
            # Add restaurant info to each inspection
            inspection_data = {
                'restaurant_name': restaurant.get('name'),
                'restaurant_address': restaurant.get('address'),
                **insp
            }
            all_inspections.append(inspection_data)

    # Filter by inspection type
    if inspection_type:
        all_inspections = [i for i in all_inspections
                          if inspection_type.lower() in i.get('type', '').lower() or
                          inspection_type.lower() in i.get('inspection_type', '').lower()]

    # Filter by hazard rating
    if hazard:
        all_inspections = [i for i in all_inspections
                          if hazard.lower() == i.get('hazard_rating', '').lower()]

    # Filter by has violations
    if has_violations:
        has_viol = has_violations.lower() == 'true'
        all_inspections = [i for i in all_inspections
                          if (len(i.get('violations', [])) > 0) == has_viol]

    # Sort by date (most recent first)
    def parse_date(insp):
        date_str = insp.get('inspection_date') or insp.get('date', '')
        try:
            # Try different date formats
            for fmt in ['%B %d, %Y', '%d-%b-%Y', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except:
            pass
        return datetime.min

    all_inspections.sort(key=parse_date, reverse=True)

    # Limit results
    if limit:
        all_inspections = all_inspections[:limit]

    return jsonify({
        'count': len(all_inspections),
        'inspections': all_inspections
    })

@app.route('/inspections/recent')
def get_recent_inspections():
    """Get most recent inspections"""
    limit = request.args.get('limit', default=20, type=int)

    data = load_data()
    all_inspections = []

    for restaurant in data:
        inspections = restaurant.get('inspections', [])
        for insp in inspections:
            inspection_data = {
                'restaurant_name': restaurant.get('name'),
                'restaurant_address': restaurant.get('address'),
                **insp
            }
            all_inspections.append(inspection_data)

    # Sort by date (most recent first)
    def parse_date(insp):
        date_str = insp.get('inspection_date') or insp.get('date', '')
        try:
            for fmt in ['%B %d, %Y', '%d-%b-%Y', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except:
            pass
        return datetime.min

    all_inspections.sort(key=parse_date, reverse=True)

    return jsonify({
        'count': min(limit, len(all_inspections)),
        'inspections': all_inspections[:limit]
    })

@app.route('/violations')
def get_all_violations():
    """Get all violations across all restaurants"""
    data = load_data()

    # Query parameters
    code = request.args.get('code')
    critical = request.args.get('critical')
    search = request.args.get('search')
    limit = request.args.get('limit', type=int)

    all_violations = []

    for restaurant in data:
        for insp in restaurant.get('inspections', []):
            for violation in insp.get('violations', []):
                violation_data = {
                    'restaurant_name': restaurant.get('name'),
                    'restaurant_address': restaurant.get('address'),
                    'inspection_date': insp.get('inspection_date') or insp.get('date'),
                    'inspection_type': insp.get('inspection_type') or insp.get('type'),
                    **violation
                }
                all_violations.append(violation_data)

    # Filter by violation code
    if code:
        all_violations = [v for v in all_violations if v.get('code') == code]

    # Filter by critical (check if code indicates critical - codes < 200 are typically critical)
    if critical:
        is_critical = critical.lower() == 'true'
        def is_critical_violation(v):
            try:
                code_num = int(v.get('code', '999'))
                return code_num < 200
            except ValueError:
                return False
        all_violations = [v for v in all_violations
                          if is_critical_violation(v) == is_critical]

    # Search in description/observation
    if search:
        search = search.lower()
        all_violations = [v for v in all_violations
                          if search in v.get('description', '').lower() or
                          search in v.get('observation', '').lower() or
                          search in v.get('corrective_action', '').lower()]

    # Limit results
    if limit:
        all_violations = all_violations[:limit]

    return jsonify({
        'count': len(all_violations),
        'violations': all_violations
    })

@app.route('/search/live')
def search_live():
    """Search the live HealthSpace site for restaurants (not cached data)"""
    query = request.args.get('q')
    fetch_details = request.args.get('details', 'false').lower() == 'true'

    if not query:
        return jsonify({
            'error': 'Missing required parameter: q'
        }), 400

    try:
        from healthspace_pg_restaurants import HealthSpaceAPI
        api = HealthSpaceAPI()

        results = api.search_restaurants(query)

        if results is None:
            return jsonify({
                'error': 'Failed to search HealthSpace site'
            }), 500

        # Optionally fetch full details for each result
        if fetch_details and results:
            for restaurant in results:
                api.get_restaurant_full_details(
                    restaurant,
                    fetch_inspections=True,
                    max_inspections=5  # Limit to last 5 inspections
                )

        return jsonify({
            'query': query,
            'count': len(results),
            'include_details': fetch_details,
            'restaurants': results,
            'source': 'live'
        })

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/restaurant/<name>/fetch')
def fetch_restaurant_live(name):
    """Fetch fresh data for a specific restaurant from the live HealthSpace site"""
    try:
        from healthspace_pg_restaurants import HealthSpaceAPI
        api = HealthSpaceAPI()

        # First search for the restaurant
        results = api.search_restaurants(name)

        if not results:
            return jsonify({
                'found': False,
                'message': f'No restaurant found matching "{name}" on live site'
            }), 404

        # If multiple matches, let user know
        if len(results) > 1:
            exact_match = None
            for r in results:
                if r.get('name', '').lower() == name.lower():
                    exact_match = r
                    break

            if not exact_match:
                return jsonify({
                    'found': False,
                    'message': f'Multiple matches found for "{name}"',
                    'matches': [r.get('name') for r in results]
                })

            results = [exact_match]

        # Fetch full details for the restaurant
        restaurant = results[0]
        api.get_restaurant_full_details(
            restaurant,
            fetch_inspections=True,
            max_inspections=None  # Get all inspections
        )

        return jsonify({
            'found': True,
            'restaurant': restaurant,
            'source': 'live'
        })

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/cities')
def get_cities():
    """Get list of all cities in Northern Health"""
    try:
        from healthspace_pg_restaurants import HealthSpaceAPI
        cities = HealthSpaceAPI.get_cities()
        return jsonify({
            'count': len(cities),
            'cities': cities
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cities/<city>/restaurants')
def get_city_restaurants(city):
    """Fetch restaurants for a specific city from the live HealthSpace site"""
    fetch_details = request.args.get('details', 'false').lower() == 'true'
    max_inspections = request.args.get('max_inspections', type=int, default=3)

    try:
        from healthspace_pg_restaurants import HealthSpaceAPI

        # Check if city is valid
        if city not in HealthSpaceAPI.CITIES:
            # Try case-insensitive match
            city_match = None
            for c in HealthSpaceAPI.CITIES.keys():
                if c.lower() == city.lower():
                    city_match = c
                    break

            if not city_match:
                return jsonify({
                    'error': f'Unknown city: {city}',
                    'available_cities': HealthSpaceAPI.get_cities()
                }), 404

            city = city_match

        api = HealthSpaceAPI(city=city)

        if fetch_details:
            restaurants = api.get_all_restaurants_with_details(
                max_inspections_per_restaurant=max_inspections
            )
        else:
            restaurants = api.get_all_restaurants()

        if restaurants:
            # Add city to each restaurant
            for r in restaurants:
                r['city'] = city

            return jsonify({
                'city': city,
                'count': len(restaurants),
                'include_details': fetch_details,
                'restaurants': restaurants,
                'source': 'live'
            })
        else:
            return jsonify({
                'city': city,
                'count': 0,
                'restaurants': [],
                'message': 'No restaurants found or error fetching data'
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/violations/stats')
def get_violation_stats():
    """Get statistics about violations"""
    data = load_data()

    # Count violations by code
    code_counts = {}
    total_violations = 0
    restaurants_with_violations = set()
    corrected_during_inspection = 0

    for restaurant in data:
        has_violation = False
        for insp in restaurant.get('inspections', []):
            for violation in insp.get('violations', []):
                total_violations += 1
                has_violation = True

                code = violation.get('code', 'Unknown')
                if code not in code_counts:
                    code_counts[code] = {
                        'count': 0,
                        'description': violation.get('description', '')
                    }
                code_counts[code]['count'] += 1

                if violation.get('corrected_during_inspection'):
                    corrected_during_inspection += 1

        if has_violation:
            restaurants_with_violations.add(restaurant.get('name'))

    # Sort by count
    sorted_codes = sorted(code_counts.items(), key=lambda x: x[1]['count'], reverse=True)

    return jsonify({
        'total_violations': total_violations,
        'restaurants_with_violations': len(restaurants_with_violations),
        'corrected_during_inspection': corrected_during_inspection,
        'top_violation_codes': [
            {'code': code, 'count': info['count'], 'description': info['description']}
            for code, info in sorted_codes[:10]
        ],
        'all_violation_codes': {code: info['count'] for code, info in sorted_codes}
    })

@app.route('/scrapes/templates', methods=['GET'])
def list_scrape_templates():
    """List reusable Scrapling scrape templates."""
    return jsonify({
        'count': len(scrape_library.list_templates()),
        'templates': scrape_library.list_templates()
    })

@app.route('/scrapes/templates', methods=['POST'])
def create_scrape_template():
    """Create or replace a reusable Scrapling scrape template."""
    try:
        template = scrape_library.save_template(request.get_json(force=True) or {})
        return jsonify({'template': template}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/scrapes/templates/<template_id>', methods=['GET'])
def get_scrape_template(template_id):
    """Get one scrape template."""
    template = scrape_library.get_template(template_id)
    if not template:
        return jsonify({'error': 'Template not found'}), 404
    return jsonify({'template': template})

@app.route('/scrapes/templates/<template_id>', methods=['DELETE'])
def delete_scrape_template(template_id):
    """Delete one scrape template."""
    if not scrape_library.delete_template(template_id):
        return jsonify({'error': 'Template not found'}), 404
    return jsonify({'ok': True})

@app.route('/scrapes/templates/<template_id>/run', methods=['POST'])
def run_scrape_template(template_id):
    """Run a template immediately without creating a scheduled job."""
    try:
        body = request.get_json(silent=True) or {}
        run = scrape_library.run_template(template_id, overrides=body.get('overrides') or body)
        status = 200 if run.get('status') == 'success' else 500
        return jsonify({'run': run}), status
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/scrapes/jobs', methods=['GET'])
def list_scrape_jobs():
    """List scheduled scrape jobs."""
    return jsonify({
        'count': len(scrape_library.list_jobs()),
        'jobs': scrape_library.list_jobs()
    })

@app.route('/scrapes/jobs', methods=['POST'])
def create_scrape_job():
    """Create or replace a scheduled scrape job."""
    try:
        job = scrape_library.save_job(request.get_json(force=True) or {})
        return jsonify({'job': job}), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

@app.route('/scrapes/jobs/<job_id>', methods=['GET'])
def get_scrape_job(job_id):
    """Get one scheduled scrape job."""
    job = scrape_library.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({'job': job})

@app.route('/scrapes/jobs/<job_id>', methods=['DELETE'])
def delete_scrape_job(job_id):
    """Delete one scheduled scrape job."""
    if not scrape_library.delete_job(job_id):
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({'ok': True})

@app.route('/scrapes/jobs/<job_id>/run', methods=['POST'])
def run_scrape_job(job_id):
    """Run a scheduled scrape job immediately."""
    job = scrape_library.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    run = scrape_library.run_template(
        job['template_id'],
        overrides=job.get('overrides') or {},
        job_id=job['id'],
    )
    status = 200 if run.get('status') == 'success' else 500
    return jsonify({'run': run}), status

@app.route('/scrapes/jobs/<job_id>/runs', methods=['GET'])
def list_scrape_job_runs(job_id):
    """List run history for one scrape job."""
    if not scrape_library.get_job(job_id):
        return jsonify({'error': 'Job not found'}), 404
    limit = request.args.get('limit', default=50, type=int)
    runs = scrape_library.list_runs(job_id=job_id, limit=limit)
    return jsonify({'count': len(runs), 'runs': runs})

@app.route('/scrapes/runs', methods=['GET'])
def list_scrape_runs():
    """List scrape run history."""
    limit = request.args.get('limit', default=50, type=int)
    template_id = request.args.get('template_id')
    job_id = request.args.get('job_id')
    runs = scrape_library.list_runs(job_id=job_id, template_id=template_id, limit=limit)
    return jsonify({'count': len(runs), 'runs': runs})

@app.route('/scrapes/runs/<run_id>', methods=['GET'])
def get_scrape_run(run_id):
    """Get one scrape run."""
    run = scrape_library.get_run(run_id)
    if not run:
        return jsonify({'error': 'Run not found'}), 404
    return jsonify({'run': run})

@app.route('/scrapes/scheduler', methods=['GET', 'POST'])
def scrape_scheduler():
    """View or control the background scrape scheduler."""
    if request.method == 'POST':
        body = request.get_json(silent=True) or {}
        action = body.get('action', 'start')
        if action == 'start':
            poll_seconds = int(body.get('poll_seconds') or os.environ.get('SCRAPE_SCHEDULER_POLL_SECONDS', '60'))
            scrape_library.start_scheduler(poll_seconds=poll_seconds)
        elif action == 'stop':
            scrape_library.stop_scheduler()
        elif action == 'run-due':
            runs = scrape_library.run_due_jobs()
            return jsonify({'scheduler': scrape_library.scheduler_status(), 'runs': runs})
        else:
            return jsonify({'error': 'action must be start, stop, or run-due'}), 400
    return jsonify({'scheduler': scrape_library.scheduler_status()})

def get_last_updated():
    """Get the last updated timestamp from the JSON file"""
    if os.path.exists('pg_restaurants.json'):
        mtime = os.path.getmtime('pg_restaurants.json')
        return datetime.fromtimestamp(mtime).isoformat()
    return None

if __name__ == '__main__':
    port = 5001
    debug = os.environ.get('FLASK_DEBUG', '1') != '0'
    scrape_library.ensure_storage()
    should_start_scheduler = (
        os.environ.get('SCRAPE_LIBRARY_SCHEDULER', '1') != '0'
        and (not debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true')
    )
    if should_start_scheduler:
        scrape_library.start_scheduler(
            poll_seconds=int(os.environ.get('SCRAPE_SCHEDULER_POLL_SECONDS', '60'))
        )
    print("=" * 60)
    print("Prince George Restaurant Inspection API v2.0")
    print("=" * 60)
    print("\nStarting Flask server...")
    print(f"API will be available at: http://localhost:{port}")
    print("\nEndpoints:")
    print("  GET  /                              - API documentation")
    print("  GET  /restaurants                   - Get all restaurants")
    print("  GET  /restaurants?search=pizza      - Search restaurants")
    print("  GET  /restaurants?hazard=low        - Filter by hazard rating")
    print("  GET  /restaurants/name/<name>       - Search by name")
    print("  GET  /restaurants/hazard/<rating>   - Filter by hazard")
    print("  GET  /restaurants/stats             - Get statistics")
    print("  POST /restaurants/refresh           - Refresh data (basic)")
    print("  POST /restaurants/refresh-deep      - Refresh with inspections & violations")
    print("")
    print("  GET  /restaurant/<name>             - Get single restaurant with inspections")
    print("  GET  /inspections                   - Get all inspections")
    print("  GET  /inspections?has_violations=true - Filter inspections")
    print("  GET  /inspections/recent            - Get most recent inspections")
    print("  GET  /violations                    - Get all violations")
    print("  GET  /violations?search=temperature - Search violations")
    print("  GET  /violations/stats              - Get violation statistics")
    print("")
    print("  Live Data (fetches from HealthSpace directly):")
    print("  GET  /search/live?q=pizza           - Search live site")
    print("  GET  /search/live?q=pizza&details=true - With full details")
    print("  GET  /restaurant/<name>/fetch       - Fetch fresh restaurant data")
    print("\n" + "=" * 60 + "\n")

    app.run(debug=debug, host='0.0.0.0', port=port)
