#!/usr/bin/env python3
"""Regression tests for render_league_table.py and fetch_probabilities.py."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import fetch_probabilities
import render_league_table


SWEEPSTAKE = [
    {"name": "Alice", "countries": ["Brazil", "France"]},
    {"name": "Bob",   "countries": ["Spain",  "Germany"]},
]

PROBABILITIES = {
    "Brazil":  0.20,
    "France":  0.15,
    "Spain":   0.30,
    "Germany": 0.10,
}

# Produces: Alice=32%, Bob=37% — Bob leads (combined_probability, not sum)
STANDINGS = render_league_table.build_standings(SWEEPSTAKE, PROBABILITIES)

HISTORICAL = [
    ("2026-06-12T08:00:00", {"winner": PROBABILITIES}),
    ("2026-06-12T20:00:00", {"winner": {**PROBABILITIES, "Brazil": 0.25}}),
]

HISTORICAL_SERIES = render_league_table.build_historical_series(SWEEPSTAKE, HISTORICAL)

ALL_STANDINGS = {"winner": STANDINGS}
ALL_HISTORICAL_SERIES = {"winner": HISTORICAL_SERIES}

HTML = render_league_table.render_html(
    ALL_STANDINGS,
    ALL_HISTORICAL_SERIES,
    sources=["opta"],
    fetched_ats=["2026-06-17T10:00:00+00:00"],
)


class TestRenderedHTML(unittest.TestCase):

    def test_legend_is_custom_html(self):
        # Chart.js built-in legend is hidden; custom HTML legend is used instead
        self.assertIn("legend: { display: false }", HTML)
        self.assertIn('id="chart-legend"', HTML)
        self.assertIn("legend-avatar", HTML)

    def test_datasets_sorted_by_latest_y(self):
        self.assertIn("sortDatasets", HTML)
        self.assertIn("latestY(b) - latestY(a)", HTML)

    def test_tooltip_format_includes_time(self):
        self.assertIn("HH:mm", HTML)

    def test_output_file_is_index_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = os.getcwd()
            os.chdir(tmpdir)
            # Write a sweepstake.json and minimal opta dir (old format, winner only)
            with open("sweepstake.json", "w") as f:
                json.dump(SWEEPSTAKE, f)
            os.makedirs("opta")
            prob_file = os.path.join("opta", "probabilities_20260612T080000Z.json")
            with open(prob_file, "w") as f:
                json.dump({
                    "fetched_at": "2026-06-12T08:00:00+00:00",
                    "source": "https://example.com",
                    "probabilities": {"Brazil": 0.20, "France": 0.15,
                                      "Spain": 0.30, "Germany": 0.10},
                }, f)
            try:
                sys.argv = ["render_league_table.py", "opta"]
                render_league_table.main()
                self.assertTrue(os.path.exists("index.html"))
                self.assertFalse(os.path.exists("league_table.html"))
            finally:
                os.chdir(orig)

    def test_standings_order(self):
        # Bob (Spain+Germany=37%) should rank above Alice (Brazil+France=32%)
        self.assertEqual(STANDINGS[0]["name"], "Bob")
        self.assertEqual(STANDINGS[1]["name"], "Alice")

    def test_two_data_points_per_person(self):
        # One point per historical entry
        for series in HISTORICAL_SERIES:
            self.assertEqual(len(series["data"]), 2)

    def test_intraday_points_use_datetime(self):
        # x values should include time component, not just date
        for series in HISTORICAL_SERIES:
            for point in series["data"]:
                self.assertIn("T", point["x"])

    def test_stage_dropdown_present(self):
        self.assertIn('id="stage-select"', HTML)
        self.assertIn('onchange="setStage(this.value)"', HTML)

    def test_all_stage_options_in_dropdown(self):
        for key, label, _, _ in render_league_table.STAGE_OPTIONS:
            self.assertIn(f'value="{key}"', HTML)
            self.assertIn(label, HTML)

    def test_winner_selected_by_default(self):
        self.assertIn('value="winner" selected', HTML)

    def test_all_stage_tbodies_rendered(self):
        for key, _, _, _ in render_league_table.STAGE_OPTIONS:
            self.assertIn(f'id="tbody-{key}"', HTML)

    def test_non_winner_tbodies_initially_hidden(self):
        for key, _, _, _ in render_league_table.STAGE_OPTIONS:
            if key == "winner":
                # winner tbody should NOT have display:none
                self.assertNotIn(f'id="tbody-winner" style="display:none"', HTML)
            else:
                self.assertIn(f'id="tbody-{key}" style="display:none"', HTML)

    def test_set_stage_function_present(self):
        self.assertIn("function setStage(stageKey)", HTML)

    def test_all_datasets_json_has_all_stages(self):
        # allDatasets JS object should include all stage keys
        for key, _, _, _ in render_league_table.STAGE_OPTIONS:
            self.assertIn(f'"{key}"', HTML)


class TestHistoricalSeriesStageFiltering(unittest.TestCase):

    def test_skips_entries_without_stage_data(self):
        # Entries without the requested stage key contribute no data points
        mixed_history = [
            ("2026-06-12T08:00:00", {"winner": PROBABILITIES}),
            ("2026-06-12T20:00:00", {"winner": PROBABILITIES, "sf": PROBABILITIES}),
        ]
        winner_series = render_league_table.build_historical_series(SWEEPSTAKE, mixed_history, "winner")
        sf_series = render_league_table.build_historical_series(SWEEPSTAKE, mixed_history, "sf")
        for s in winner_series:
            self.assertEqual(len(s["data"]), 2)
        for s in sf_series:
            self.assertEqual(len(s["data"]), 1)

    def test_stage_key_default_is_winner(self):
        series = render_league_table.build_historical_series(SWEEPSTAKE, HISTORICAL)
        for s in series:
            self.assertEqual(len(s["data"]), 2)


class TestCombinedProbability(unittest.TestCase):

    def test_single_team_at_100_percent(self):
        # If one team is guaranteed through, the combined probability should be 100%
        self.assertAlmostEqual(render_league_table.combined_probability([1.0]), 1.0)

    def test_single_team_at_100_with_others(self):
        # A certain team dominates regardless of others
        self.assertAlmostEqual(render_league_table.combined_probability([1.0, 0.5, 0.3]), 1.0)

    def test_two_teams_combined_is_not_sum(self):
        # 1 - (1-0.6)*(1-0.6) = 0.84, not 1.2
        self.assertAlmostEqual(render_league_table.combined_probability([0.6, 0.6]), 0.84)

    def test_empty_returns_zero(self):
        self.assertAlmostEqual(render_league_table.combined_probability([]), 0.0)

    def test_standings_total_uses_combined_probability(self):
        # Alice: 1-(0.8*0.85)=0.32, Bob: 1-(0.7*0.9)=0.37
        alice = next(s for s in STANDINGS if s["name"] == "Alice")
        bob = next(s for s in STANDINGS if s["name"] == "Bob")
        self.assertAlmostEqual(alice["total"], 0.32, places=10)
        self.assertAlmostEqual(bob["total"], 0.37, places=10)

    def test_historical_series_uses_combined_probability(self):
        # Alice at t=0: Brazil=0.20, France=0.15 → 1-(0.80*0.85)=0.32 → 32.0%
        alice_series = next(s for s in HISTORICAL_SERIES if s["name"] == "Alice")
        self.assertAlmostEqual(alice_series["data"][0]["y"], 32.0, places=5)


class TestFetchProbabilities(unittest.TestCase):

    def test_save_skips_when_probabilities_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            probs = {"Brazil": 0.20, "France": 0.15}
            fetch_probabilities.save(tmpdir, probs, "http://example.com", None)
            second = fetch_probabilities.save(tmpdir, probs, "http://example.com", None)
            self.assertIsNone(second)
            self.assertEqual(len(os.listdir(tmpdir)), 1)

    def test_save_writes_when_probabilities_changed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fetch_probabilities.save(tmpdir, {"Brazil": 0.20}, "http://example.com", None)
            second = fetch_probabilities.save(tmpdir, {"Brazil": 0.25}, "http://example.com", None)
            self.assertIsNotNone(second)

    def test_save_writes_when_no_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = fetch_probabilities.save(tmpdir, {"Brazil": 0.20}, "http://example.com", None)
            self.assertIsNotNone(filename)
            self.assertEqual(len(os.listdir(tmpdir)), 1)

    def test_save_includes_stage_probabilities_when_provided(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stage_probs = {"winner": {"Brazil": 0.20}, "sf": {"Brazil": 0.40}}
            filename = fetch_probabilities.save(tmpdir, {"Brazil": 0.20}, "http://example.com", None, stage_probs)
            assert filename is not None
            with open(filename) as f:
                data = json.load(f)
            self.assertIn("stage_probabilities", data)
            self.assertEqual(data["stage_probabilities"]["winner"]["Brazil"], 0.20)
            self.assertEqual(data["stage_probabilities"]["sf"]["Brazil"], 0.40)

    def test_save_deduplicates_on_stage_probabilities_when_provided(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stage_probs = {"winner": {"Brazil": 0.20}, "sf": {"Brazil": 0.40}}
            fetch_probabilities.save(tmpdir, {"Brazil": 0.20}, "http://example.com", None, stage_probs)
            second = fetch_probabilities.save(tmpdir, {"Brazil": 0.20}, "http://example.com", None, stage_probs)
            self.assertIsNone(second)
            self.assertEqual(len(os.listdir(tmpdir)), 1)


if __name__ == "__main__":
    unittest.main()
