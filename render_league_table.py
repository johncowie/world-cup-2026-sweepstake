#!/usr/bin/env python3
"""Generates an HTML league table of sweepstake win probabilities."""

import json
import glob
import os
from datetime import datetime, timezone

COUNTRY_CODES = {
    "Algeria": "ALG",
    "Argentina": "ARG",
    "Australia": "AUS",
    "Austria": "AUT",
    "Belgium": "BEL",
    "Bosnia and Herzegovina": "BIH",
    "Brazil": "BRA",
    "Canada": "CAN",
    "Cape Verde": "CPV",
    "Colombia": "COL",
    "Croatia": "CRO",
    "Curaçao": "CUW",
    "Czechia": "CZE",
    "Côte d'Ivoire": "CIV",
    "DR Congo": "COD",
    "Ecuador": "ECU",
    "Egypt": "EGY",
    "England": "ENG",
    "France": "FRA",
    "Germany": "GER",
    "Ghana": "GHA",
    "Haiti": "HAI",
    "Iran": "IRN",
    "Iraq": "IRQ",
    "Japan": "JPN",
    "Jordan": "JOR",
    "Mexico": "MEX",
    "Morocco": "MAR",
    "Netherlands": "NED",
    "New Zealand": "NZL",
    "Norway": "NOR",
    "Panama": "PAN",
    "Paraguay": "PAR",
    "Portugal": "POR",
    "Qatar": "QAT",
    "Saudi Arabia": "KSA",
    "Scotland": "SCO",
    "Senegal": "SEN",
    "South Africa": "RSA",
    "South Korea": "KOR",
    "Spain": "ESP",
    "Sweden": "SWE",
    "Switzerland": "SUI",
    "Tunisia": "TUN",
    "Turkey": "TUR",
    "United States": "USA",
    "Uruguay": "URU",
    "Uzbekistan": "UZB",
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


def load_latest_probabilities():
    files = sorted(glob.glob("probabilities_*.json"))
    if not files:
        raise FileNotFoundError("No probabilities_*.json files found. Run fetch_probabilities.py first.")
    latest = files[-1]
    with open(latest) as f:
        data = json.load(f)
    print(f"Using {latest} (fetched at {data['fetched_at']})")
    return data["probabilities"], data["fetched_at"]


def load_sweepstake():
    with open("sweepstake.json") as f:
        return json.load(f)


def build_standings(sweepstake, probabilities):
    standings = []
    for person in sweepstake:
        countries = []
        total = 0.0
        for country_name in person["countries"]:
            code = COUNTRY_CODES.get(country_name)
            prob = probabilities.get(code, 0.0) if code else 0.0
            countries.append({"name": country_name, "code": code, "prob": prob})
            total += prob
        standings.append({"name": person["name"], "countries": countries, "total": total})
    standings.sort(key=lambda x: x["total"], reverse=True)
    return standings


def render_html(standings, fetched_at):
    fetched_dt = datetime.fromisoformat(fetched_at)
    fetched_str = fetched_dt.strftime("%d %b %Y, %H:%M UTC")

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

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>World Cup 2026 Sweepstake</title>
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
    header {{ text-align: center; margin-bottom: 2.5rem; }}
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
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>⚽ World Cup 2026 Sweepstake</h1>
      <p>Win probabilities from <a href="https://dtai.cs.kuleuven.be/sports/worldcup2026/" style="color:#3a6a99">DTAI KU Leuven</a> &mdash; updated {fetched_str}</p>
    </header>
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
    <footer>
      <p>Probabilities sourced from <a href="https://dtai.cs.kuleuven.be/sports/worldcup2026/">dtai.cs.kuleuven.be</a></p>
    </footer>
  </div>
</body>
</html>"""


def main():
    probabilities, fetched_at = load_latest_probabilities()
    sweepstake = load_sweepstake()
    standings = build_standings(sweepstake, probabilities)
    html = render_html(standings, fetched_at)

    outfile = "league_table.html"
    with open(outfile, "w") as f:
        f.write(html)

    print(f"\nLeague table written to {outfile}\n")
    print(f"{'Rank':<5} {'Player':<10} {'Win Chance'}")
    print("-" * 30)
    for i, entry in enumerate(standings, 1):
        print(f"{i:<5} {entry['name']:<10} {entry['total']:.1%}")


if __name__ == "__main__":
    main()