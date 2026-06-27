#!/usr/bin/env python3
"""Generates an HTML league table of sweepstake win probabilities.

Usage:
    python3 render_league_table.py
"""

import base64
import glob
import json
import os
from datetime import datetime

SOURCE_LABEL = "Opta Supercomputer"
SOURCE_URL = "https://theanalyst.com/competition/fifa-world-cup/predictions"

# Ordered list of (stage_key, dropdown_label, table_col_label, chart_y_label)
STAGE_OPTIONS = [
    ("winner", "Winner",           "Win chance",          "Win probability"),
    ("final",  "Reach Final",      "Reach Final",         "Final probability"),
    ("sf",     "Reach Semi-finals","Reach Semi-finals",   "Semi-final probability"),
    ("qf",     "Reach Quarter-finals", "Reach Quarter-finals", "Quarter-final probability"),
    ("last16", "Reach Last 16",    "Reach Last 16",       "Last 16 probability"),
    ("last32", "Reach Last 32",    "Reach Last 32",       "Last 32 probability"),
]

# Canonical full name → 3-letter code (used for flag emoji display)
COUNTRY_CODES = {
    "Algeria": "ALG", "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT",
    "Belgium": "BEL", "Bosnia and Herzegovina": "BIH", "Brazil": "BRA", "Canada": "CAN",
    "Cape Verde": "CPV", "Colombia": "COL", "Croatia": "CRO", "Curaçao": "CUW",
    "Czechia": "CZE", "Côte d'Ivoire": "CIV", "DR Congo": "COD", "Ecuador": "ECU",
    "Egypt": "EGY", "England": "ENG", "France": "FRA", "Germany": "GER",
    "Ghana": "GHA", "Haiti": "HAI", "Iran": "IRN", "Iraq": "IRQ", "Japan": "JPN",
    "Jordan": "JOR", "Mexico": "MEX", "Morocco": "MAR", "Netherlands": "NED",
    "New Zealand": "NZL", "Norway": "NOR", "Panama": "PAN", "Paraguay": "PAR",
    "Portugal": "POR", "Qatar": "QAT", "Saudi Arabia": "KSA", "Scotland": "SCO",
    "Senegal": "SEN", "South Africa": "RSA", "South Korea": "KOR", "Spain": "ESP",
    "Sweden": "SWE", "Switzerland": "SUI", "Tunisia": "TUN", "Turkey": "TUR",
    "United States": "USA", "Uruguay": "URU", "Uzbekistan": "UZB",
}

FLAG_EMOJIS = {
    "ALG": "🇩🇿", "ARG": "🇦🇷", "AUS": "🇦🇺", "AUT": "🇦🇹", "BEL": "🇧🇪",
    "BIH": "🇧🇦", "BRA": "🇧🇷", "CAN": "🇨🇦", "CPV": "🇨🇻", "COL": "🇨🇴",
    "CRO": "🇭🇷", "CUW": "🇨🇼", "CZE": "🇨🇿", "CIV": "🇨🇮", "COD": "🇨🇩",
    "ECU": "🇪🇨", "EGY": "🇪🇬", "ENG": "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "FRA": "🇫🇷", "GER": "🇩🇪",
    "GHA": "🇬🇭", "HAI": "🇭🇹", "IRN": "🇮🇷", "IRQ": "🇮🇶", "JPN": "🇯🇵",
    "JOR": "🇯🇴", "MEX": "🇲🇽", "MAR": "🇲🇦", "NED": "🇳🇱", "NZL": "🇳🇿",
    "NOR": "🇳🇴", "PAN": "🇵🇦", "PAR": "🇵🇾", "POR": "🇵🇹", "QAT": "🇶🇦",
    "KSA": "🇸🇦", "SCO": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "SEN": "🇸🇳", "RSA": "🇿🇦", "KOR": "🇰🇷",
    "ESP": "🇪🇸", "SWE": "🇸🇪", "SUI": "🇨🇭", "TUN": "🇹🇳", "TUR": "🇹🇷",
    "USA": "🇺🇸", "URU": "🇺🇾", "UZB": "🇺🇿",
}


# Opta API uses different names for some countries than the sweepstake.json canonical names
OPTA_NAME_MAP = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Cabo Verde": "Cape Verde",
    "Congo DR": "DR Congo",
    "IR Iran": "Iran",
    "Korea Republic": "South Korea",
    "Türkiye": "Turkey",
}


def normalize_probs(probs):
    """Rename opta country keys to canonical sweepstake names."""
    return {OPTA_NAME_MAP.get(k, k): v for k, v in probs.items()}


def get_current_stage(stage_probs):
    """Returns the key of the earliest stage currently being contested.

    A stage is contested if some teams are at 0.0 (eliminated) and some are
    strictly between 0.0 and 1.0 (outcome still undecided).
    """
    for stage in ["last32", "last16", "qf", "sf", "final", "winner"]:
        probs = stage_probs.get(stage, {})
        if not probs:
            continue
        values = list(probs.values())
        if any(v == 0.0 for v in values) and any(0.0 < v < 1.0 for v in values):
            return stage
    return None


def get_eliminated_countries(stage_probs):
    """Returns the set of canonical country names definitively eliminated from the current stage."""
    current_stage = get_current_stage(stage_probs)
    if current_stage is None:
        return set()
    return {name for name, prob in stage_probs.get(current_stage, {}).items() if prob == 0.0}


PLAYER_COLORS = [
    "#f5c842", "#e8884a", "#4ac8e8", "#a8e84a", "#e84a9a",
    "#844ae8", "#4ae8a8", "#e84a4a", "#4a84e8", "#e8d04a",
    "#4ae8d0", "#e8a84a",
]


def load_latest():
    files = sorted(glob.glob(os.path.join("opta", "probabilities_*.json")))
    if not files:
        raise FileNotFoundError(
            "No probabilities files found in opta/. "
            "Run: python3 fetch_probabilities.py"
        )
    latest = files[-1]
    with open(latest) as f:
        data = json.load(f)
    print(f"  {latest} (fetched at {data['fetched_at']})")

    raw_stage = data.get("stage_probabilities")
    if raw_stage:
        stage_probs = {k: normalize_probs(v) for k, v in raw_stage.items()}
    else:
        stage_probs = {"winner": normalize_probs(data["probabilities"])}

    fixtures_path = os.path.join("opta", "fixtures.json")
    fixtures = []
    if os.path.exists(fixtures_path):
        with open(fixtures_path) as f:
            fixtures = json.load(f)
        print(f"  fixtures.json ({len(fixtures)} confirmed fixture(s))")

    return stage_probs, data["fetched_at"], fixtures


def load_all_history():
    """Returns list of (datetime_str, stage_probs_dict) for all historical opta files."""
    entries = []
    files = sorted(glob.glob(os.path.join("opta", "probabilities_*.json")))
    for filepath in files:
        with open(filepath) as f:
            data = json.load(f)

        raw_stage = data.get("stage_probabilities")
        if raw_stage:
            stage_probs = {k: normalize_probs(v) for k, v in raw_stage.items()}
        else:
            stage_probs = {"winner": normalize_probs(data["probabilities"])}

        fetched_at = datetime.fromisoformat(data["fetched_at"])
        datetime_str = fetched_at.strftime("%Y-%m-%dT%H:%M:%S")
        entries.append((datetime_str, stage_probs))

    return entries


def combined_probability(individual_probs, mutual_exclusions=None):
    """P(at least one succeeds).

    mutual_exclusions: list of (i, j) index pairs where teams i and j play
    each other (mutually exclusive). Their combined contribution is p_i + p_j
    rather than the independence formula, so 1 - (1-p_i)(1-p_j).
    """
    if not mutual_exclusions:
        result = 1.0
        for p in individual_probs:
            result *= (1.0 - p)
        return 1.0 - result

    used = set()
    virtual_probs = []
    for i, j in mutual_exclusions:
        virtual_probs.append(min(1.0, individual_probs[i] + individual_probs[j]))
        used.add(i)
        used.add(j)
    for k, p in enumerate(individual_probs):
        if k not in used:
            virtual_probs.append(p)

    result = 1.0
    for p in virtual_probs:
        result *= (1.0 - p)
    return 1.0 - result


def build_historical_series(sweepstake, historical_data, stage_key="winner"):
    """Returns list of {name, data: [{x, y}]} per player, skipping entries without stage data."""
    series = []
    for person in sweepstake:
        data_points = []
        for date_str, stage_probs in historical_data:
            probs = stage_probs.get(stage_key)
            if not probs:
                continue
            individual = [probs.get(country, 0.0) for country in person["countries"]]
            total = combined_probability(individual)
            data_points.append({"x": date_str, "y": round(total * 100, 2)})
        series.append({"name": person["name"], "data": data_points})
    return series


def load_avatars():
    """Returns {name_lower: data_uri} for each JPEG in avatars/."""
    result = {}
    avatar_dir = "avatars"
    if not os.path.isdir(avatar_dir):
        return result
    for fname in sorted(os.listdir(avatar_dir)):
        if fname.lower().endswith(".jpg") or fname.lower().endswith(".jpeg"):
            name = os.path.splitext(fname)[0].lower()
            with open(os.path.join(avatar_dir, fname), "rb") as f:
                data = base64.b64encode(f.read()).decode()
            result[name] = f"data:image/jpeg;base64,{data}"
    return result


def initials_svg(name, color):
    """Returns a data-URI SVG circle with the player's initials."""
    parts = name.split()
    initials = "".join(p[0].upper() for p in parts[:2])
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120">'
        f'<circle cx="60" cy="60" r="60" fill="{color}33"/>'
        f'<text x="60" y="76" text-anchor="middle" fill="{color}" '
        f'font-size="44" font-weight="bold" '
        f'font-family="-apple-system,BlinkMacSystemFont,sans-serif">{initials}</text>'
        f'</svg>'
    )
    b64 = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{b64}"


def load_sweepstake():
    with open("sweepstake.json") as f:
        return json.load(f)


def _find_mutual_exclusions(country_names, fixtures):
    """Return list of (i, j) index pairs for countries from the same player that play each other."""
    fixture_sets = [frozenset(pair) for pair in fixtures]
    exclusions = []
    for pair_set in fixture_sets:
        matched = [i for i, name in enumerate(country_names) if name in pair_set]
        if len(matched) == 2:
            exclusions.append(tuple(matched))
    return exclusions


def build_standings(sweepstake, probabilities, eliminated=None, fixtures=None):
    """
    fixtures: list of [teamA, teamB] pairs playing each other this round.
    When two of a player's countries meet, their combined probability is
    p_A + p_B (mutually exclusive) rather than the independence formula.
    """
    if eliminated is None:
        eliminated = set()
    standings = []
    for person in sweepstake:
        countries = []
        for country_name in person["countries"]:
            prob = probabilities.get(country_name, 0.0)
            code = COUNTRY_CODES.get(country_name)
            is_eliminated = country_name in eliminated
            countries.append({"name": country_name, "code": code, "prob": prob, "eliminated": is_eliminated})
        probs = [c["prob"] for c in countries]
        names = [c["name"] for c in countries]
        exclusions = _find_mutual_exclusions(names, fixtures or [])
        total = combined_probability(probs, exclusions or None)
        standings.append({"name": person["name"], "countries": countries, "total": total})
    standings.sort(key=lambda x: x["total"], reverse=True)
    return standings


def render_html(all_standings, all_historical_series, fetched_at, avatars=None):
    source_desc = f'<a href="{SOURCE_URL}" style="color:#3a6a99">{SOURCE_LABEL}</a>'

    if avatars is None:
        avatars = {}

    latest_fetch = fetched_at
    fetched_str = datetime.fromisoformat(latest_fetch).strftime("%d %b %Y, %H:%M UTC")

    # Color assignment from winner historical series (sweepstake order = consistent across stages)
    base_series = all_historical_series.get("winner") or next(iter(all_historical_series.values()), [])
    player_color = {
        s["name"]: PLAYER_COLORS[i % len(PLAYER_COLORS)]
        for i, s in enumerate(base_series)
    }

    def avatar_src(name):
        return avatars.get(name.lower()) or initials_svg(name, player_color.get(name, "#7a8499"))

    avatar_json = json.dumps({
        s["name"].lower(): avatar_src(s["name"])
        for s in base_series
    })

    # Build table rows for each stage
    all_tbody_html = ""
    for stage_key, _, _, _ in STAGE_OPTIONS:
        standings = all_standings.get(stage_key, [])
        rows = ""
        for i, entry in enumerate(standings, 1):
            country_pills = ""
            for c in sorted(entry["countries"], key=lambda x: (x.get("eliminated", False), -x["prob"])):
                flag = FLAG_EMOJIS.get(c["code"], "🏳️")
                if c.get("eliminated"):
                    country_pills += f'<span class="pill pill-eliminated">{flag} {c["name"]}</span>'
                else:
                    country_pills += f'<span class="pill">{flag} {c["name"]} <span class="pill-prob">{c["prob"]:.1%}</span></span>'
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "")
            av = avatar_src(entry["name"])
            rows += f"""
        <tr class="{'top3' if i <= 3 else ''}">
            <td class="rank">{medal or i}</td>
            <td class="person"><div class="person-cell"><img class="avatar" src="{av}" alt="{entry['name']}"><span>{entry['name']}</span></div></td>
            <td class="countries">{country_pills}</td>
            <td class="total">{entry['total']:.1%}</td>
        </tr>"""
        display = "" if stage_key == "winner" else ' style="display:none"'
        all_tbody_html += f'<tbody id="tbody-{stage_key}"{display}>{rows}\n        </tbody>'

    # Build all chart datasets per stage
    all_chart_datasets = {}
    for stage_key, _, _, _ in STAGE_OPTIONS:
        historical_series = all_historical_series.get(stage_key, [])
        all_chart_datasets[stage_key] = [
            {
                "label": s["name"],
                "data": s["data"],
                "borderColor": player_color.get(s["name"], PLAYER_COLORS[0]),
                "backgroundColor": "transparent",
                "tension": 0.3,
                "pointRadius": 0,
                "pointHoverRadius": 5,
                "borderWidth": 2,
            }
            for s in historical_series
        ]

    all_datasets_json = json.dumps(all_chart_datasets)

    # Stage metadata for JS
    stage_col_labels = {key: col for key, _, col, _ in STAGE_OPTIONS}
    stage_chart_labels = {key: chart for key, _, _, chart in STAGE_OPTIONS}
    stage_col_labels_json = json.dumps(stage_col_labels)
    stage_chart_labels_json = json.dumps(stage_chart_labels)

    # Dropdown options HTML
    options_html = "\n".join(
        f'        <option value="{key}"{" selected" if key == "winner" else ""}>{label}</option>'
        for key, label, _, _ in STAGE_OPTIONS
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>World Cup 2026 Sweepstake</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0a1628;
      color: #e8eaf0;
      min-height: 100vh;
      padding: 2rem 1rem;
    }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    header {{ text-align: center; margin-bottom: 2rem; }}
    header h1 {{
      font-size: 2rem;
      font-weight: 800;
      background: linear-gradient(135deg, #f5c842, #e8884a);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 0.4rem;
    }}
    header p {{ color: #7a8499; font-size: 0.85rem; }}
    .controls {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      border-bottom: 1px solid #1e2d45;
      margin-bottom: 1.5rem;
    }}
    .tabs {{
      display: flex;
      gap: 0.5rem;
      padding-bottom: 0;
    }}
    .tab-btn {{
      background: none;
      border: none;
      color: #7a8499;
      font-size: 0.95rem;
      font-weight: 600;
      padding: 0.6rem 1.2rem;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      margin-bottom: -1px;
      transition: color 0.15s, border-color 0.15s;
    }}
    .tab-btn:hover {{ color: #e8eaf0; }}
    .tab-btn.active {{
      color: #f5c842;
      border-bottom-color: #f5c842;
    }}
    .stage-filter {{
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding-bottom: 0.6rem;
    }}
    .stage-filter label {{
      color: #7a8499;
      font-size: 0.85rem;
    }}
    .stage-filter select {{
      background: #1a2d47;
      color: #e8eaf0;
      border: 1px solid #1e2d45;
      border-radius: 6px;
      padding: 0.3rem 0.7rem;
      font-size: 0.85rem;
      cursor: pointer;
    }}
    .stage-filter select:focus {{
      outline: none;
      border-color: #f5c842;
    }}
    .tab-page {{ display: none; }}
    .tab-page.active {{ display: block; }}
    table {{ width: 100%; border-collapse: collapse; }}
    thead th {{
      text-align: left;
      padding: 0.75rem 1rem;
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #7a8499;
      border-bottom: 1px solid #1e2d45;
    }}
    tbody tr {{
      border-bottom: 1px solid #111e30;
      transition: background 0.15s;
    }}
    tbody tr:hover {{ background: #111e30; }}
    tbody tr.top3 {{ background: #0e1e35; }}
    tbody tr.top3:hover {{ background: #142540; }}
    td {{ padding: 1rem; vertical-align: middle; }}
    td.rank {{ font-size: 1.3rem; width: 3rem; text-align: center; color: #7a8499; font-weight: 700; }}
    td.person {{ font-weight: 700; font-size: 1.05rem; width: 10rem; }}
    .person-cell {{ display: flex; align-items: center; gap: 0.55rem; }}
    .avatar {{ width: 36px; height: 36px; border-radius: 50%; object-fit: cover; flex-shrink: 0; }}
    td.countries {{ line-height: 1.8; }}
    td.total {{
      font-size: 1.4rem;
      font-weight: 800;
      text-align: right;
      white-space: nowrap;
      color: #f5c842;
      width: 6rem;
    }}
    tr.top3 td.total {{ color: #f5c842; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
      background: #1a2d47;
      border-radius: 999px;
      padding: 0.2rem 0.6rem;
      font-size: 0.82rem;
      margin: 0.15rem 0.2rem 0.15rem 0;
      white-space: nowrap;
    }}
    .pill-prob {{ color: #7a8499; font-size: 0.75rem; }}
    .pill-eliminated {{ opacity: 0.35; text-decoration: line-through; text-decoration-color: #7a8499; }}
    footer {{ text-align: center; margin-top: 2.5rem; color: #3a4a60; font-size: 0.8rem; }}
    footer a {{ color: #3a6a99; text-decoration: none; }}
    .history-wrap {{ display: flex; gap: 1.2rem; align-items: flex-start; }}
    .chart-wrap {{ flex: 1; position: relative; min-width: 0; }}
    .chart-legend {{ flex-shrink: 0; display: flex; flex-direction: column; gap: 0.35rem; padding-top: 0.25rem; }}
    .legend-item {{ display: flex; align-items: center; gap: 0.45rem; font-size: 0.82rem; color: #e8eaf0; }}
    .legend-avatar {{ width: 28px; height: 28px; border-radius: 50%; object-fit: cover; border: 2.5px solid; flex-shrink: 0; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>⚽ World Cup 2026 Sweepstake</h1>
      <p>Probabilities from {source_desc} &mdash; updated {fetched_str}</p>
    </header>
    <div class="controls">
      <div class="tabs">
        <button class="tab-btn active" onclick="showTab('table', event)">League Table</button>
        <button class="tab-btn" onclick="showTab('history', event)">History</button>
      </div>
      <div class="stage-filter">
        <label for="stage-select">Stage:</label>
        <select id="stage-select" onchange="setStage(this.value)">
{options_html}
        </select>
      </div>
    </div>
    <div id="page-table" class="tab-page active">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Player</th>
            <th>Countries</th>
            <th style="text-align:right" id="prob-col-header">Win chance</th>
          </tr>
        </thead>
        {all_tbody_html}
      </table>
    </div>
    <div id="page-history" class="tab-page">
      <div class="history-wrap">
        <div class="chart-wrap">
          <canvas id="historyChart"></canvas>
        </div>
        <div class="chart-legend" id="chart-legend"></div>
      </div>
    </div>
  </div>
  <script>
    const allDatasets = {all_datasets_json};
    const stageColLabels = {stage_col_labels_json};
    const stageChartLabels = {stage_chart_labels_json};
    const avatarData = {avatar_json};

    function fitChartHeight() {{
      const wrap = document.querySelector('.chart-wrap');
      if (!wrap) return;
      const top = wrap.getBoundingClientRect().top + window.scrollY;
      const bodyPadBottom = parseFloat(getComputedStyle(document.body).paddingBottom);
      wrap.style.height = (window.innerHeight - top - bodyPadBottom) + 'px';
      if (window.historyChart) window.historyChart.resize();
    }}

    function showTab(name, event) {{
      document.querySelectorAll('.tab-page').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById('page-' + name).classList.add('active');
      event.currentTarget.classList.add('active');
      if (name === 'history') fitChartHeight();
    }}

    window.addEventListener('resize', () => {{
      if (document.getElementById('page-history').classList.contains('active')) fitChartHeight();
    }});

    function sortDatasets(datasets) {{
      return [...datasets].sort((a, b) => {{
        const latestY = ds => ds.data.length ? ds.data[ds.data.length - 1].y : 0;
        return latestY(b) - latestY(a);
      }});
    }}

    function buildLegend(sortedDatasets) {{
      const legendEl = document.getElementById('chart-legend');
      legendEl.innerHTML = '';
      sortedDatasets.forEach(ds => {{
        const src = avatarData[ds.label.toLowerCase()] || '';
        const item = document.createElement('div');
        item.className = 'legend-item';
        item.innerHTML = `<img class="legend-avatar" src="${{src}}" style="border-color:${{ds.borderColor}}" alt="${{ds.label}}"><span>${{ds.label}}</span>`;
        legendEl.appendChild(item);
      }});
    }}

    function stageMinDate(stageKey) {{
      const datasets = allDatasets[stageKey] || [];
      let min = null;
      for (const ds of datasets) {{
        for (const pt of ds.data) {{
          if (min === null || pt.x < min) min = pt.x;
        }}
      }}
      return min;
    }}

    function stageYBounds(stageKey) {{
      const datasets = allDatasets[stageKey] || [];
      let minY = Infinity, maxY = -Infinity;
      for (const ds of datasets) {{
        for (const pt of ds.data) {{
          if (pt.y < minY) minY = pt.y;
          if (pt.y > maxY) maxY = pt.y;
        }}
      }}
      if (minY === Infinity) return {{ min: 0, max: 100, step: 10 }};
      const range = maxY - minY || 1;
      const rough = range / 4;
      const mag = Math.pow(10, Math.floor(Math.log10(rough)));
      const norm = rough / mag;
      let step;
      if (norm <= 1) step = 1;
      else if (norm <= 2) step = 2;
      else if (norm <= 5) step = 5;
      else step = 10;
      step *= mag;
      return {{
        min: Math.max(0, Math.floor(minY / step) * step),
        max: Math.min(100, Math.ceil(maxY / step) * step),
        step,
      }};
    }}

    function setStage(stageKey) {{
      document.querySelectorAll('[id^="tbody-"]').forEach(el => el.style.display = 'none');
      const tbody = document.getElementById('tbody-' + stageKey);
      if (tbody) tbody.style.display = '';
      document.getElementById('prob-col-header').textContent = stageColLabels[stageKey] || stageKey;
      const sortedDatasets = sortDatasets(allDatasets[stageKey] || []);
      const yBounds = stageYBounds(stageKey);
      historyChart.data.datasets = sortedDatasets;
      historyChart.options.scales.y.title.text = stageChartLabels[stageKey] || stageKey;
      historyChart.options.scales.y.min = yBounds.min;
      historyChart.options.scales.y.max = yBounds.max;
      historyChart.options.scales.y.ticks.stepSize = yBounds.step;
      historyChart.options.scales.x.min = stageMinDate(stageKey);
      historyChart.update();
      buildLegend(sortedDatasets);
    }}

    const initialSorted = sortDatasets(allDatasets['winner'] || []);
    const initialYBounds = stageYBounds('winner');
    const historyChart = new Chart(document.getElementById('historyChart'), {{
      type: 'line',
      data: {{ datasets: initialSorted }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        scales: {{
          x: {{
            type: 'time',
            min: stageMinDate('winner'),
            max: '2026-07-19',
            time: {{ unit: 'day', tooltipFormat: 'd MMM yyyy HH:mm' }},
            grid: {{ color: '#1e2d45' }},
            ticks: {{ color: '#7a8499' }},
          }},
          y: {{
            min: initialYBounds.min,
            max: initialYBounds.max,
            grid: {{ color: '#1e2d45' }},
            ticks: {{
              color: '#7a8499',
              stepSize: initialYBounds.step,
              callback: v => v + '%',
            }},
            title: {{ display: true, text: 'Win probability', color: '#7a8499' }},
          }},
        }},
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            backgroundColor: '#0e1e35',
            borderColor: '#1e2d45',
            borderWidth: 1,
            titleColor: '#e8eaf0',
            bodyColor: '#7a8499',
            itemSort: (a, b) => b.parsed.y - a.parsed.y,
            callbacks: {{
              label: ctx => ' ' + ctx.dataset.label + ': ' + ctx.parsed.y.toFixed(1) + '%',
            }},
          }},
        }},
      }},
    }});
    window.historyChart = historyChart;
    buildLegend(initialSorted);
  </script>
</body>
</html>"""


def main():
    print("Loading probabilities...")
    stage_probs, fetched_at, fixtures = load_latest()

    eliminated = get_eliminated_countries(stage_probs)
    if eliminated:
        print(f"  Eliminated: {', '.join(sorted(eliminated))}")

    sweepstake = load_sweepstake()
    historical_data = load_all_history()

    all_standings = {}
    all_historical_series = {}
    for stage_key, _, _, _ in STAGE_OPTIONS:
        if stage_key in stage_probs:
            all_standings[stage_key] = build_standings(
                sweepstake, stage_probs[stage_key], eliminated, fixtures
            )
        all_historical_series[stage_key] = build_historical_series(sweepstake, historical_data, stage_key)

    avatars = load_avatars()
    html = render_html(all_standings, all_historical_series, fetched_at, avatars)

    with open("index.html", "w") as f:
        f.write(html)

    print(f"\nLeague table written to index.html\n")
    winner_standings = all_standings.get("winner", [])
    print(f"{'Rank':<5} {'Player':<10} {'Win Chance'}")
    print("-" * 30)
    for i, entry in enumerate(winner_standings, 1):
        print(f"{i:<5} {entry['name']:<10} {entry['total']:.1%}")


if __name__ == "__main__":
    main()
