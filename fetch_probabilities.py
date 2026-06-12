#!/usr/bin/env python3
"""Fetches World Cup 2026 win probabilities from a named source and saves as a timestamped JSON file.

Usage:
    python3 fetch_probabilities.py dtai
    python3 fetch_probabilities.py opta
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

# --- DTAI ---

DTAI_URL = "https://dtai.cs.kuleuven.be/sports/worldcup2026/data/data.json"


def fetch_dtai():
    with urllib.request.urlopen(DTAI_URL) as resp:
        data = json.loads(resp.read().decode())

    probabilities = {}
    for team in data:
        name = team.get("name")
        prob_win = team.get("prob_win")
        if name and prob_win is not None:
            p = prob_win.get("p") if isinstance(prob_win, dict) else None
            probabilities[name] = p if p is not None else 0.0

    probabilities = dict(sorted(probabilities.items(), key=lambda x: x[1], reverse=True))
    return probabilities, DTAI_URL, None


# --- Opta ---

OPTA_TOURNAMENT_CALENDAR_ID = "873cbl9cd9butm4air0mugxzo"
OPTA_SESSION_URL = "https://theanalyst.com/wp-json/sdapi/v1/session"
OPTA_SIMULATIONS_URL = (
    f"https://theanalyst.com/wp-json/sdapi/v1/soccerdata/"
    f"seasonandtournamentsimulations?tmcl={OPTA_TOURNAMENT_CALENDAR_ID}"
)
OPTA_SOURCE_URL = "https://theanalyst.com/competition/fifa-world-cup/predictions"
OPTA_WIN_TYPE_ID = "2"


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
    final_stage = next((s for s in stages if s["name"] == "Final"), None)
    if not final_stage:
        raise ValueError("Could not find 'Final' stage in Opta simulations data")

    last_updated = None
    probabilities = {}
    for contestant in final_stage["contestants"]["contestant"]:
        name = contestant["name"]
        for prediction in contestant.get("predictions", []):
            if last_updated is None:
                last_updated = prediction.get("lastUpdated")
            for pred in prediction.get("predicted", []):
                if pred.get("typeId") == OPTA_WIN_TYPE_ID:
                    probabilities[name] = float(pred["value"].rstrip("%")) / 100.0

    probabilities = dict(sorted(probabilities.items(), key=lambda x: x[1], reverse=True))
    return probabilities, OPTA_SOURCE_URL, last_updated


# --- Common ---

SOURCES = {"dtai": fetch_dtai, "opta": fetch_opta}


def save(source, probabilities, source_url, model_updated_at):
    os.makedirs(source, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": source_url,
        "probabilities": probabilities,
    }
    if model_updated_at:
        output["model_updated_at"] = model_updated_at

    filename = os.path.join(source, f"probabilities_{timestamp}.json")
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    return filename


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SOURCES:
        print(f"Usage: {sys.argv[0]} <source>")
        print(f"Sources: {', '.join(SOURCES)}")
        sys.exit(1)

    source = sys.argv[1]
    print(f"Fetching from {source}...")

    probabilities, source_url, model_updated_at = SOURCES[source]()
    filename = save(source, probabilities, source_url, model_updated_at)

    print(f"\nSaved {len(probabilities)} teams to {filename}")
    for team, prob in list(probabilities.items())[:10]:
        print(f"  {team}: {prob:.1%}")
    if len(probabilities) > 10:
        print(f"  ... and {len(probabilities) - 10} more")


if __name__ == "__main__":
    main()
