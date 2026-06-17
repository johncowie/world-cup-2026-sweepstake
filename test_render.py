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

# Produces: Alice=35%, Bob=40% — Bob leads
STANDINGS = render_league_table.build_standings(SWEEPSTAKE, PROBABILITIES)

HISTORICAL = [
    ("2026-06-12T08:00:00", PROBABILITIES),
    ("2026-06-12T20:00:00", {**PROBABILITIES, "Brazil": 0.25}),
]

HISTORICAL_SERIES = render_league_table.build_historical_series(SWEEPSTAKE, HISTORICAL)

HTML = render_league_table.render_html(
    STANDINGS,
    sources=["opta"],
    fetched_ats=["2026-06-17T10:00:00+00:00"],
    historical_series=HISTORICAL_SERIES,
)


class TestRenderedHTML(unittest.TestCase):

    def test_legend_is_custom_html(self):
        # Chart.js built-in legend is hidden; custom HTML legend is used instead
        self.assertIn("legend: { display: false }", HTML)
        self.assertIn('id="chart-legend"', HTML)
        self.assertIn("legend-avatar", HTML)

    def test_datasets_sorted_by_latest_y(self):
        self.assertIn("sortedDatasets", HTML)
        self.assertIn("latestY(b) - latestY(a)", HTML)

    def test_tooltip_format_includes_time(self):
        self.assertIn("HH:mm", HTML)

    def test_output_file_is_index_html(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            orig = os.getcwd()
            os.chdir(tmpdir)
            # Write a sweepstake.json and minimal opta dir
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
        # Bob (Spain+Germany=40%) should rank above Alice (Brazil+France=35%)
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


if __name__ == "__main__":
    unittest.main()
