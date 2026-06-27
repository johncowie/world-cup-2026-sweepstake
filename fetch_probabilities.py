#!/usr/bin/env python3
"""Fetches World Cup 2026 win probabilities from Opta and saves as a timestamped JSON file.

Usage:
    python3 fetch_probabilities.py
"""

import itertools
import json
import os
import urllib.request
from datetime import date, datetime, timedelta, timezone

# --- Opta ---

OPTA_TOURNAMENT_CALENDAR_ID = "873cbl9cd9butm4air0mugxzo"
OPTA_SESSION_URL = "https://theanalyst.com/wp-json/sdapi/v1/session"
OPTA_SIMULATIONS_URL = (
    f"https://theanalyst.com/wp-json/sdapi/v1/soccerdata/"
    f"seasonandtournamentsimulations?tmcl={OPTA_TOURNAMENT_CALENDAR_ID}"
)
OPTA_SOURCE_URL = "https://theanalyst.com/competition/fifa-world-cup/predictions"

# (opta_stage_name, type_id, our_key)
OPTA_STAGE_KEYS = [
    ("16th Finals", "1", "last32"),
    ("8th Finals", "1", "last16"),
    ("Quarter-finals", "1", "qf"),
    ("Semi-finals", "1", "sf"),
    ("Final", "1", "final"),
    ("Final", "2", "winner"),
]


def _opta_get_session_cookie():
    req = urllib.request.Request(OPTA_SESSION_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        cookies = resp.info().get_all("Set-Cookie") or []
    for cookie in cookies:
        name_value = cookie.split(";")[0].strip()
        if name_value.startswith("STYXKEY_sdapi_session="):
            return name_value
    raise RuntimeError("Could not obtain session cookie from theanalyst.com")


def fetch_opta():
    print("  Fetching session cookie...")
    session_cookie = _opta_get_session_cookie()

    print("  Fetching simulations...")
    req = urllib.request.Request(
        OPTA_SIMULATIONS_URL,
        headers={"User-Agent": "Mozilla/5.0", "Cookie": session_cookie},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())

    stages = data["stages"]["stage"]
    stage_by_name = {s["name"]: s for s in stages}

    last_updated = None
    stage_probabilities = {}

    for stage_name, type_id, key in OPTA_STAGE_KEYS:
        stage = stage_by_name.get(stage_name)
        if not stage:
            continue
        probs = {}
        for contestant in stage["contestants"]["contestant"]:
            name = contestant["name"]
            for prediction in contestant.get("predictions", []):
                if last_updated is None:
                    last_updated = prediction.get("lastUpdated")
                for pred in prediction.get("predicted", []):
                    if pred.get("typeId") == type_id:
                        probs[name] = float(pred["value"].rstrip("%")) / 100.0
        stage_probabilities[key] = dict(sorted(probs.items(), key=lambda x: x[1], reverse=True))

    winner_probs = stage_probabilities.get("winner", {})
    return winner_probs, stage_probabilities, OPTA_SOURCE_URL, last_updated


# --- ESPN Fixtures ---

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={date}"
)

ESPN_NAME_MAP = {
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Congo DR": "DR Congo",
    "Ivory Coast": "Côte d'Ivoire",
    "Türkiye": "Turkey",
}

ESPN_STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/standings"

# Full tournament window: group stage through final
ESPN_TOURNAMENT_START = date(2026, 6, 11)
ESPN_TOURNAMENT_END   = date(2026, 7, 19)

_TBD_MARKERS = ("Group", "Round of", "Quarterfinal", "Semifinal", "Third Place")


def _is_tbd(name):
    return any(name.startswith(m) for m in _TBD_MARKERS)


def _normalize(name):
    return ESPN_NAME_MAP.get(name, name)


def fetch_espn_groups():
    """Return a set of frozensets, each containing the canonical names of teams in one group."""
    req = urllib.request.Request(ESPN_STANDINGS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    groups = set()
    for child in data.get("children", []):
        entries = child.get("standings", {}).get("entries", [])
        teams = frozenset(_normalize(e["team"]["displayName"]) for e in entries)
        if teams:
            groups.add(teams)
    return groups


def fetch_espn_fixtures(same_group_pairs, confirmed_from=None):
    """Return a list of {"teams": [teamA, teamB], "confirmed_from": date_str} dicts.

    confirmed_from defaults to today. Scans the full tournament window, excluding
    TBD pairs and same-group (group-stage) matches.
    """
    if confirmed_from is None:
        confirmed_from = date.today().isoformat()
    seen = set()
    fixtures = []
    current = ESPN_TOURNAMENT_START
    while current <= ESPN_TOURNAMENT_END:
        url = ESPN_SCOREBOARD_URL.format(date=current.strftime("%Y%m%d"))
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            for event in data.get("events", []):
                comp = event.get("competitions", [{}])[0]
                teams = [
                    _normalize(c["team"]["displayName"])
                    for c in comp.get("competitors", [])
                ]
                if len(teams) == 2 and not any(_is_tbd(t) for t in teams):
                    pair = frozenset(teams)
                    if pair not in seen and pair not in same_group_pairs:
                        seen.add(pair)
                        fixtures.append({"teams": sorted(teams), "confirmed_from": confirmed_from})
        except Exception:
            pass
        current += timedelta(days=1)
    return fixtures


def merge_fixtures(existing, new_fixtures):
    """Merge new fixtures into existing, keeping the earliest confirmed_from per pair."""
    by_pair = {tuple(f["teams"]): f["confirmed_from"] for f in existing}
    for f in new_fixtures:
        key = tuple(f["teams"])
        if key not in by_pair or f["confirmed_from"] < by_pair[key]:
            by_pair[key] = f["confirmed_from"]
    return [{"teams": list(pair), "confirmed_from": cf} for pair, cf in sorted(by_pair.items())]


def _latest_probabilities():
    files = sorted(f for f in os.listdir("opta") if f.startswith("probabilities_") and f.endswith(".json"))
    if not files:
        return None
    with open(os.path.join("opta", files[-1])) as f:
        data = json.load(f)
    return data.get("stage_probabilities") or data.get("probabilities", {})


def save(probabilities, source_url, model_updated_at, stage_probabilities=None, fixtures=None):
    os.makedirs("opta", exist_ok=True)

    if fixtures is not None:
        fixtures_path = os.path.join("opta", "fixtures.json")
        existing_fixtures = []
        if os.path.exists(fixtures_path):
            with open(fixtures_path) as f:
                raw = json.load(f)
            # Migrate old flat-list format (list of lists) to new dict format
            if raw and isinstance(raw[0], list):
                raw = []
            existing_fixtures = raw
        merged = merge_fixtures(existing_fixtures, fixtures)
        with open(fixtures_path, "w") as f:
            json.dump(merged, f, indent=2)

    existing = _latest_probabilities()
    comparable = stage_probabilities if stage_probabilities is not None else probabilities
    if existing is not None and existing == comparable:
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": source_url,
        "probabilities": probabilities,
    }
    if stage_probabilities is not None:
        output["stage_probabilities"] = stage_probabilities
    if model_updated_at:
        output["model_updated_at"] = model_updated_at

    filename = os.path.join("opta", f"probabilities_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)

    return filename


def main():
    print("Fetching from Opta...")
    probabilities, stage_probabilities, source_url, model_updated_at = fetch_opta()

    print("Fetching fixtures from ESPN...")
    groups = fetch_espn_groups()
    same_group_pairs = {frozenset(pair) for group in groups for pair in itertools.combinations(group, 2)}
    fixtures = fetch_espn_fixtures(same_group_pairs)
    print(f"  {len(fixtures)} confirmed knockout fixture(s)")

    filename = save(probabilities, source_url, model_updated_at, stage_probabilities, fixtures)

    if filename is None:
        print("\nProbabilities unchanged — fixtures updated if changed")
        return

    print(f"\nSaved {len(probabilities)} teams to {filename}")
    for team, prob in list(probabilities.items())[:10]:
        print(f"  {team}: {prob:.1%}")
    if len(probabilities) > 10:
        print(f"  ... and {len(probabilities) - 10} more")


if __name__ == "__main__":
    main()
