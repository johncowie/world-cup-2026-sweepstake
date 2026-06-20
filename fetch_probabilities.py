#!/usr/bin/env python3
"""Fetches World Cup 2026 win probabilities from Opta and saves as a timestamped JSON file.

Usage:
    python3 fetch_probabilities.py
"""

import json
import os
import urllib.request
from datetime import datetime, timezone

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


def _latest_probabilities():
    files = sorted(f for f in os.listdir("opta") if f.startswith("probabilities_") and f.endswith(".json"))
    if not files:
        return None
    with open(os.path.join("opta", files[-1])) as f:
        data = json.load(f)
    return data.get("stage_probabilities") or data.get("probabilities", {})


def save(probabilities, source_url, model_updated_at, stage_probabilities=None):
    os.makedirs("opta", exist_ok=True)

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
    filename = save(probabilities, source_url, model_updated_at, stage_probabilities)

    if filename is None:
        print("\nProbabilities unchanged — no new file written")
        return

    print(f"\nSaved {len(probabilities)} teams to {filename}")
    for team, prob in list(probabilities.items())[:10]:
        print(f"  {team}: {prob:.1%}")
    if len(probabilities) > 10:
        print(f"  ... and {len(probabilities) - 10} more")


if __name__ == "__main__":
    main()
