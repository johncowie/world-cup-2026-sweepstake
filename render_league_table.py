#!/usr/bin/env python3
"""Generates an HTML league table of sweepstake win probabilities.

Usage:
    python3 render_league_table.py dtai
    python3 render_league_table.py opta
    python3 render_league_table.py dtai opta
"""

import glob
import json
import os
import sys
from datetime import datetime

VALID_SOURCES = ["dtai", "opta"]

SOURCE_LABELS = {
    "dtai": "DTAI KU Leuven",
    "opta": "Opta Supercomputer",
}

SOURCE_URLS = {
    "dtai": "https://dtai.cs.kuleuven.be/sports/worldcup2026/",
    "opta": "https://theanalyst.com/competition/fifa-world-cup/predictions",
}

# Canonical full name → 3-letter code (used to normalise DTAI data)
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

CODE_TO_COUNTRY = {code: name for name, code in COUNTRY_CODES.items()}

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


PLAYER_COLORS = [
    "#f5c842", "#e8884a", "#4ac8e8", "#a8e84a", "#e84a9a",
    "#844ae8", "#4ae8a8", "#e84a4a", "#4a84e8", "#e8d04a",
    "#4ae8d0", "#e8a84a",
]


def load_latest_for_source(source):
    files = sorted(glob.glob(os.path.join(source, "probabilities_*.json")))
    if not files:
        raise FileNotFoundError(
            f"No probabilities files found in {source}/. "
            f"Run: python3 fetch_probabilities.py {source}"
        )
    latest = files[-1]
    with open(latest) as f:
        data = json.load(f)
    print(f"  {source}: {latest} (fetched at {data['fetched_at']})")

    # Normalise keys to full country names
    raw = data["probabilities"]
    normalised = {}
    for key, prob in raw.items():
        if key in CODE_TO_COUNTRY:
            normalised[CODE_TO_COUNTRY[key]] = prob
        else:
            normalised[key] = prob  # already a full name (Opta)

    return normalised, data["fetched_at"]


def load_and_average(sources):
    all_probs = []
    fetched_ats = []

    for source in sources:
        probs, fetched_at = load_latest_for_source(source)
        all_probs.append(probs)
        fetched_ats.append(fetched_at)

    all_countries = set().union(*[p.keys() for p in all_probs])
    averaged = {
        country: sum(p.get(country, 0.0) for p in all_probs) / len(all_probs)
        for country in all_countries
    }
    return averaged, fetched_ats


def load_all_for_sources(sources):
    """Returns list of (datetime_str, probabilities) for all historical files."""
    entries = []

    for source in sources:
        files = sorted(glob.glob(os.path.join(source, "probabilities_*.json")))
        for filepath in files:
            with open(filepath) as f:
                data = json.load(f)
            raw = data["probabilities"]
            normalised = {}
            for key, prob in raw.items():
                if key in CODE_TO_COUNTRY:
                    normalised[CODE_TO_COUNTRY[key]] = prob
                else:
                    normalised[key] = prob
            fetched_at = datetime.fromisoformat(data["fetched_at"])
            datetime_str = fetched_at.strftime("%Y-%m-%dT%H:%M:%S")
            entries.append((datetime_str, normalised))

    entries.sort(key=lambda x: x[0])
    return entries


def build_historical_series(sweepstake, historical_data):
    """Returns list of {name, data: [{x, y}]} per player, in current standings order."""
    series = []
    for person in sweepstake:
        data_points = []
        for date_str, probs in historical_data:
            total = sum(probs.get(country, 0.0) for country in person["countries"])
            data_points.append({"x": date_str, "y": round(total * 100, 2)})
        series.append({"name": person["name"], "data": data_points})
    return series


def load_sweepstake():
    with open("sweepstake.json") as f:
        return json.load(f)


def build_standings(sweepstake, probabilities):
    standings = []
    for person in sweepstake:
        countries = []
        total = 0.0
        for country_name in person["countries"]:
            prob = probabilities.get(country_name, 0.0)
            code = COUNTRY_CODES.get(country_name)
            countries.append({"name": country_name, "code": code, "prob": prob})
            total += prob
        standings.append({"name": person["name"], "countries": countries, "total": total})
    standings.sort(key=lambda x: x["total"], reverse=True)
    return standings


def render_html(standings, sources, fetched_ats, historical_series):
    if len(sources) == 1:
        source_label = SOURCE_LABELS[sources[0]]
        source_desc = f'<a href="{SOURCE_URLS[sources[0]]}" style="color:#3a6a99">{source_label}</a>'
    else:
        links = [f'<a href="{SOURCE_URLS[s]}" style="color:#3a6a99">{SOURCE_LABELS[s]}</a>' for s in sources]
        source_desc = "Average of " + " &amp; ".join(links)

    latest_fetch = max(fetched_ats)
    fetched_str = datetime.fromisoformat(latest_fetch).strftime("%d %b %Y, %H:%M UTC")

    rows = ""
    for i, entry in enumerate(standings, 1):
        country_pills = ""
        for c in sorted(entry["countries"], key=lambda x: x["prob"], reverse=True):
            flag = FLAG_EMOJIS.get(c["code"], "🏳️")
            country_pills += f'<span class="pill">{flag} {c["name"]} <span class="pill-prob">{c["prob"]:.1%}</span></span>'

        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "")
        rows += f"""
        <tr class="{'top3' if i <= 3 else ''}">
            <td class="rank">{medal or i}</td>
            <td class="person">{entry['name']}</td>
            <td class="countries">{country_pills}</td>
            <td class="total">{entry['total']:.1%}</td>
        </tr>"""

    chart_datasets = json.dumps([
        {
            "label": s["name"],
            "data": s["data"],
            "borderColor": PLAYER_COLORS[i % len(PLAYER_COLORS)],
            "backgroundColor": "transparent",
            "tension": 0.3,
            "pointRadius": 0,
            "pointHoverRadius": 5,
            "borderWidth": 2,
        }
        for i, s in enumerate(historical_series)
    ])

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
    .tabs {{
      display: flex;
      gap: 0.5rem;
      margin-bottom: 1.5rem;
      border-bottom: 1px solid #1e2d45;
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
    td.person {{ font-weight: 700; font-size: 1.05rem; width: 8rem; }}
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
    footer {{ text-align: center; margin-top: 2.5rem; color: #3a4a60; font-size: 0.8rem; }}
    footer a {{ color: #3a6a99; text-decoration: none; }}
    .chart-wrap {{ position: relative; height: 500px; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>⚽ World Cup 2026 Sweepstake</h1>
      <p>Win probabilities from {source_desc} &mdash; updated {fetched_str}</p>
    </header>
    <div class="tabs">
      <button class="tab-btn active" onclick="showTab('table')">League Table</button>
      <button class="tab-btn" onclick="showTab('history')">History</button>
    </div>
    <div id="page-table" class="tab-page active">
      <table>
        <thead>
          <tr>
            <th></th>
            <th>Player</th>
            <th>Countries</th>
            <th style="text-align:right">Win chance</th>
          </tr>
        </thead>
        <tbody>{rows}
        </tbody>
      </table>
    </div>
    <div id="page-history" class="tab-page">
      <div class="chart-wrap">
        <canvas id="historyChart"></canvas>
      </div>
    </div>
  </div>
  <script>
    function showTab(name) {{
      document.querySelectorAll('.tab-page').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById('page-' + name).classList.add('active');
      event.currentTarget.classList.add('active');
    }}

    const datasets = {chart_datasets};
    new Chart(document.getElementById('historyChart'), {{
      type: 'line',
      data: {{ datasets }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        scales: {{
          x: {{
            type: 'time',
            min: '2026-06-11',
            max: '2026-07-19',
            time: {{ unit: 'day', tooltipFormat: 'd MMM yyyy HH:mm' }},
            grid: {{ color: '#1e2d45' }},
            ticks: {{ color: '#7a8499' }},
          }},
          y: {{
            min: 0,
            grid: {{ color: '#1e2d45' }},
            ticks: {{
              color: '#7a8499',
              callback: v => v + '%',
            }},
            title: {{ display: true, text: 'Win probability', color: '#7a8499' }},
          }},
        }},
        plugins: {{
          legend: {{
            position: 'right',
            labels: {{ color: '#e8eaf0', boxWidth: 12 }},
          }},
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
  </script>
</body>
</html>"""


def main():
    args = sys.argv[1:]
    if not args:
        print(f"Usage: {sys.argv[0]} <source> [source ...]")
        print(f"Sources: {', '.join(VALID_SOURCES)}")
        sys.exit(1)

    invalid = [s for s in args if s not in VALID_SOURCES]
    if invalid:
        print(f"Unknown source(s): {', '.join(invalid)}")
        print(f"Valid sources: {', '.join(VALID_SOURCES)}")
        sys.exit(1)

    sources = list(dict.fromkeys(args))  # deduplicate, preserve order

    print("Loading probabilities...")
    probabilities, fetched_ats = load_and_average(sources)

    sweepstake = load_sweepstake()
    standings = build_standings(sweepstake, probabilities)
    historical_data = load_all_for_sources(sources)
    historical_series = build_historical_series(sweepstake, historical_data)
    html = render_html(standings, sources, fetched_ats, historical_series)

    with open("index.html", "w") as f:
        f.write(html)

    print(f"\nLeague table written to index.html\n")
    print(f"{'Rank':<5} {'Player':<10} {'Win Chance'}")
    print("-" * 30)
    for i, entry in enumerate(standings, 1):
        print(f"{i:<5} {entry['name']:<10} {entry['total']:.1%}")


if __name__ == "__main__":
    main()
