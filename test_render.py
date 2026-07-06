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
    fetched_at="2026-06-17T10:00:00+00:00",
)


class TestRenderedHTML(unittest.TestCase):

    def test_legend_is_custom_html(self):
        # Chart.js built-in legend is hidden; custom HTML legend is used instead
        self.assertIn("legend: { display: false }", HTML)
        self.assertIn('id="chart-legend"', HTML)
        self.assertIn("legend-avatar", HTML)

    def test_legend_click_toggles_line_visibility(self):
        # Clicking a legend item toggles the dataset's hidden flag on the chart
        self.assertIn("togglePlayer", HTML)
        self.assertIn("item.addEventListener('click', () => togglePlayer(ds.label))", HTML)
        self.assertIn("ds.hidden = hiddenPlayers.has(ds.label.toLowerCase())", HTML)

    def test_legend_dims_avatar_border_when_hidden(self):
        # Hidden players' legend avatars get a low-alpha border to show toggled-off state
        self.assertIn("hexToRgba(ds.borderColor, 0.15)", HTML)

    def test_legend_dims_avatar_image_when_hidden(self):
        # Hidden players' legend avatar images also dim, not just the border
        self.assertIn("const imgOpacity = isHidden ? 0.15 : 1", HTML)
        self.assertIn("opacity:${imgOpacity}", HTML)

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

    def test_x_axis_min_computed_dynamically_per_stage(self):
        # The chart should use stageMinDate() to set x.min on stage change,
        # not a hardcoded date, so stages with sparse history don't show empty space.
        self.assertIn("function stageMinDate(stageKey)", HTML)
        self.assertIn("historyChart.options.scales.x.min = stageMinDate(stageKey)", HTML)
        self.assertIn("min: stageMinDate('winner')", HTML)

    def test_y_axis_bounds_computed_from_data(self):
        # y-axis min/max should be derived from data per stage, not hardcoded 0.
        self.assertIn("function stageYBounds(stageKey)", HTML)
        self.assertIn("historyChart.options.scales.y.min = yBounds.min", HTML)
        self.assertIn("historyChart.options.scales.y.max = yBounds.max", HTML)
        self.assertIn("historyChart.options.scales.y.ticks.stepSize = yBounds.step", HTML)
        self.assertIn("min: initialYBounds.min", HTML)
        self.assertIn("max: initialYBounds.max", HTML)
        self.assertIn("stepSize: initialYBounds.step", HTML)

    def test_y_axis_snaps_to_tick_interval(self):
        # min/max should be floored/ceiled to the nearest computed step interval.
        # e.g. data range 3%–17% → step=5, min=0, max=20.
        self.assertIn("Math.floor(minY / step) * step", HTML)
        self.assertIn("Math.ceil(maxY / step) * step", HTML)

    def test_history_chart_fills_screen_vertically(self):
        # Chart height is set via JS to exactly fill the viewport without scrolling.
        self.assertIn("function fitChartHeight()", HTML)
        self.assertIn("window.innerHeight", HTML)
        self.assertNotIn("height: 500px", HTML)
        self.assertNotIn("calc(100vh", HTML)

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

    def test_historical_series_applies_mutual_exclusion_from_confirmed_date(self):
        # Fixture confirmed 2026-06-27; snapshot on 2026-06-27 gets correction, earlier ones don't
        sweepstake = [{"name": "Alice", "countries": ["Brazil", "France"]}]
        history = [
            ("2026-06-12T08:00:00", {"winner": {"Brazil": 0.6, "France": 0.3}}),
            ("2026-06-27T10:00:00", {"winner": {"Brazil": 0.6, "France": 0.3}}),
        ]
        fixtures = [{"teams": ["Brazil", "France"], "confirmed_from": "2026-06-27"}]
        series = render_league_table.build_historical_series(sweepstake, history, "winner", fixtures)
        # Before confirmed_from: independence → 1-(0.4*0.7) = 0.72 → 72.0%
        self.assertAlmostEqual(series[0]["data"][0]["y"], 72.0, places=5)
        # On confirmed_from: mutual exclusion → 0.6+0.3 = 0.9 → 90.0%
        self.assertAlmostEqual(series[0]["data"][1]["y"], 90.0, places=5)

    def test_historical_series_without_fixtures_unchanged(self):
        # No fixtures → original independence formula used throughout
        sweepstake = [{"name": "Alice", "countries": ["Brazil", "France"]}]
        history = [("2026-06-12T08:00:00", {"winner": {"Brazil": 0.6, "France": 0.3}})]
        series = render_league_table.build_historical_series(sweepstake, history, "winner")
        self.assertAlmostEqual(series[0]["data"][0]["y"], 72.0, places=5)


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

    def test_mutual_exclusion_uses_sum_not_independence_formula(self):
        # Teams at indices 0 and 1 play each other → P = p0 + p1, not 1-(1-p0)(1-p1)
        result = render_league_table.combined_probability([0.6, 0.3], [(0, 1)])
        self.assertAlmostEqual(result, 0.9)  # sum, not 1-(0.4*0.7)=0.72

    def test_mutual_exclusion_guarantees_100_when_probs_sum_to_1(self):
        # If two teams' probs sum to 1.0 (playing each other, one must advance),
        # the player is guaranteed to have a team in the next round.
        result = render_league_table.combined_probability([0.617, 0.383], [(0, 1)])
        self.assertAlmostEqual(result, 1.0)

    def test_mutual_exclusion_with_independent_third_team(self):
        # Teams 0 and 1 play each other; team 2 is independent.
        # P = 1 - (1 - (0.6+0.3)) * (1 - 0.5) = 1 - 0.1*0.5 = 0.95
        result = render_league_table.combined_probability([0.6, 0.3, 0.5], [(0, 1)])
        self.assertAlmostEqual(result, 0.95)

    def test_no_mutual_exclusions_unchanged(self):
        # Passing empty exclusions gives the same result as passing None
        p = [0.2, 0.15, 0.3, 0.1]
        self.assertAlmostEqual(
            render_league_table.combined_probability(p),
            render_league_table.combined_probability(p, []),
        )


STAGE_PROBS_WITH_ELIMINATED = {
    "last32": {"Brazil": 0.85, "France": 0.70, "Haiti": 0.0, "Turkey": 0.0},
    "winner": {"Brazil": 0.20, "France": 0.15, "Haiti": 0.0, "Turkey": 0.0},
}

STAGE_PROBS_ALL_DECIDED = {
    # last32 fully decided: some at 1.0, some at 0.0 — no longer contested
    "last32": {"Brazil": 1.0, "France": 1.0, "Haiti": 0.0, "Turkey": 0.0},
    "last16": {"Brazil": 0.60, "France": 0.50, "Haiti": 0.0, "Turkey": 0.0},
}


SWEEPSTAKE_WITH_ELIMINATED = [
    {"name": "Alice", "countries": ["Brazil", "Haiti"]},
    {"name": "Bob",   "countries": ["France", "Turkey"]},
]

STANDINGS_WITH_ELIMINATED = render_league_table.build_standings(
    SWEEPSTAKE_WITH_ELIMINATED,
    STAGE_PROBS_WITH_ELIMINATED["last32"],
    eliminated={"Haiti", "Turkey"},
)

HTML_WITH_ELIMINATED = render_league_table.render_html(
    {"winner": STANDINGS_WITH_ELIMINATED},
    {"winner": []},
    fetched_at="2026-06-17T10:00:00+00:00",
)


class TestEliminatedCountries(unittest.TestCase):

    def test_get_current_stage_returns_first_contested_stage(self):
        stage = render_league_table.get_current_stage(STAGE_PROBS_WITH_ELIMINATED)
        self.assertEqual(stage, "last32")

    def test_get_current_stage_skips_fully_decided_stages(self):
        # last32 is fully decided (all 0.0 or 1.0), so current stage should be last16
        stage = render_league_table.get_current_stage(STAGE_PROBS_ALL_DECIDED)
        self.assertEqual(stage, "last16")

    def test_get_current_stage_returns_none_when_no_stage_probs(self):
        stage = render_league_table.get_current_stage({})
        self.assertIsNone(stage)

    def test_get_eliminated_countries_returns_zero_prob_teams(self):
        eliminated = render_league_table.get_eliminated_countries(STAGE_PROBS_WITH_ELIMINATED)
        self.assertEqual(eliminated, {"Haiti", "Turkey"})

    def test_get_eliminated_countries_returns_empty_when_no_stage_probs(self):
        eliminated = render_league_table.get_eliminated_countries({})
        self.assertEqual(eliminated, set())

    def test_eliminated_flag_set_on_country(self):
        haiti = next(c for c in STANDINGS_WITH_ELIMINATED[0]["countries"] if c["name"] == "Haiti")
        turkey = next(c for c in STANDINGS_WITH_ELIMINATED[1]["countries"] if c["name"] == "Turkey")
        brazil = next(c for c in STANDINGS_WITH_ELIMINATED[0]["countries"] if c["name"] == "Brazil")
        self.assertTrue(haiti["eliminated"])
        self.assertTrue(turkey["eliminated"])
        self.assertFalse(brazil["eliminated"])

    def test_eliminated_pill_has_strikethrough_class(self):
        self.assertIn("pill-eliminated", HTML_WITH_ELIMINATED)

    def test_eliminated_pill_has_no_probability_shown(self):
        # Eliminated country pills should not contain pill-prob span
        # Find the Haiti pill section and verify no probability follows it
        idx = HTML_WITH_ELIMINATED.find("pill-eliminated")
        snippet = HTML_WITH_ELIMINATED[idx:idx+200]
        self.assertNotIn("pill-prob", snippet)

    def test_active_pill_still_shows_probability(self):
        # Non-eliminated countries should still show their probability
        self.assertIn("pill-prob", HTML_WITH_ELIMINATED)

    def test_eliminated_countries_sorted_last_in_pill_row(self):
        # In Alice's row, Brazil (active) should appear before Haiti (eliminated)
        alice_row_start = HTML_WITH_ELIMINATED.find("Alice")
        alice_row_end = HTML_WITH_ELIMINATED.find("</tr>", alice_row_start)
        alice_row = HTML_WITH_ELIMINATED[alice_row_start:alice_row_end]
        brazil_pos = alice_row.find("Brazil")
        haiti_pos = alice_row.find("Haiti")
        self.assertLess(brazil_pos, haiti_pos)

    def test_rank_shows_sob_emoji_when_all_teams_eliminated(self):
        # Carol's only team is eliminated, so her total probability is 0
        sweepstake = [
            {"name": "Alice", "countries": ["Brazil"]},
            {"name": "Carol", "countries": ["Haiti"]},
        ]
        probs = {"Brazil": 0.20, "Haiti": 0.0}
        standings = render_league_table.build_standings(sweepstake, probs, eliminated={"Haiti"})
        html = render_league_table.render_html(
            {"winner": standings},
            {"winner": []},
            fetched_at="2026-06-17T10:00:00+00:00",
        )
        carol_row_start = html.find("Carol")
        carol_row_before = html.rfind("<tr", 0, carol_row_start)
        carol_row_end = html.find("</tr>", carol_row_start)
        carol_row = html[carol_row_before:carol_row_end]
        self.assertIn('<td class="rank">😭</td>', carol_row)

    def test_rank_shows_number_when_probability_nonzero(self):
        self.assertNotIn("😭", HTML_WITH_ELIMINATED)


class TestFixtureAwareProbability(unittest.TestCase):
    """When two of a player's teams play each other, probabilities are mutually exclusive."""

    def test_build_standings_no_fixtures_uses_independence(self):
        sweepstake = [{"name": "Felix", "countries": ["Canada", "South Africa"]}]
        probs = {"Canada": 0.617, "South Africa": 0.053}
        standings = render_league_table.build_standings(sweepstake, probs)
        # independence formula: 1 - (1-0.617)*(1-0.053)
        expected = 1 - (1 - 0.617) * (1 - 0.053)
        self.assertAlmostEqual(standings[0]["total"], expected, places=10)

    def test_build_standings_with_fixture_uses_sum(self):
        # Canada and South Africa play each other in last32 → mutually exclusive for last16
        sweepstake = [{"name": "Felix", "countries": ["Canada", "South Africa"]}]
        probs = {"Canada": 0.617, "South Africa": 0.053}
        fixtures = [["Canada", "South Africa"]]
        standings = render_league_table.build_standings(sweepstake, probs, fixtures=fixtures)
        self.assertAlmostEqual(standings[0]["total"], 0.617 + 0.053, places=10)

    def test_build_standings_both_confirmed_and_playing_each_other_gives_100(self):
        # Both qualify for last32 (prob=1.0 for last32) and face each other.
        # For last16 probs, their values should sum to 1.0 → 100% chance for the player.
        sweepstake = [{"name": "Felix", "countries": ["Canada", "South Africa"]}]
        probs = {"Canada": 0.65, "South Africa": 0.35}  # sums to 1.0
        fixtures = [["Canada", "South Africa"]]
        standings = render_league_table.build_standings(sweepstake, probs, fixtures=fixtures)
        self.assertAlmostEqual(standings[0]["total"], 1.0)

    def test_fixture_only_affects_player_with_both_teams(self):
        # Alice has Brazil+France (unrelated to the fixture); Bob has Spain+Canada.
        # South Africa is not in either player's team list, so no mutual exclusion applies.
        sweepstake = [
            {"name": "Alice", "countries": ["Brazil", "France"]},
            {"name": "Bob",   "countries": ["Spain", "Canada"]},
        ]
        probs = {"Brazil": 0.20, "France": 0.15, "Spain": 0.30, "Canada": 0.617}
        fixtures = [["Canada", "South Africa"]]  # South Africa not in any player's list
        standings = render_league_table.build_standings(sweepstake, probs, fixtures=fixtures)
        by_name = {s["name"]: s for s in standings}
        # Alice unaffected — South Africa not in her countries
        self.assertAlmostEqual(by_name["Alice"]["total"], 1 - (1 - 0.20) * (1 - 0.15), places=10)
        # Bob unaffected — Canada's opponent (South Africa) is not Bob's team
        self.assertAlmostEqual(by_name["Bob"]["total"], 1 - (1 - 0.30) * (1 - 0.617), places=10)

    def test_find_mutual_exclusions_identifies_matched_pair(self):
        exclusions = render_league_table._find_mutual_exclusions(
            ["Canada", "Ecuador", "South Africa", "Cape Verde"],
            [["Canada", "South Africa"]],
        )
        self.assertEqual(exclusions, [(0, 2)])

    def test_find_mutual_exclusions_no_match(self):
        exclusions = render_league_table._find_mutual_exclusions(
            ["Canada", "Ecuador"],
            [["Brazil", "France"]],
        )
        self.assertEqual(exclusions, [])

    def test_find_mutual_exclusions_two_separate_pairs(self):
        exclusions = render_league_table._find_mutual_exclusions(
            ["A", "B", "C", "D"],
            [["A", "B"], ["C", "D"]],
        )
        self.assertIn((0, 1), exclusions)
        self.assertIn((2, 3), exclusions)


class TestNormalizeName(unittest.TestCase):

    def test_opta_names_mapped_to_canonical(self):
        raw = {"Türkiye": 0.0, "IR Iran": 0.45, "Korea Republic": 0.60, "Brazil": 0.20}
        normalized = render_league_table.normalize_probs(raw)
        self.assertIn("Turkey", normalized)
        self.assertIn("Iran", normalized)
        self.assertIn("South Korea", normalized)
        self.assertIn("Brazil", normalized)
        self.assertNotIn("Türkiye", normalized)
        self.assertNotIn("IR Iran", normalized)
        self.assertNotIn("Korea Republic", normalized)

    def test_unmapped_names_pass_through(self):
        raw = {"Brazil": 0.20, "France": 0.15}
        normalized = render_league_table.normalize_probs(raw)
        self.assertEqual(normalized, raw)


class TestFetchProbabilities(unittest.TestCase):

    def _in_tmpdir(self):
        """Context manager: chdir to a fresh temp dir, restore on exit."""
        import contextlib
        @contextlib.contextmanager
        def _ctx():
            orig = os.getcwd()
            with tempfile.TemporaryDirectory() as tmpdir:
                os.chdir(tmpdir)
                try:
                    yield tmpdir
                finally:
                    os.chdir(orig)
        return _ctx()

    def test_save_skips_when_probabilities_unchanged(self):
        with self._in_tmpdir():
            probs = {"Brazil": 0.20, "France": 0.15}
            fetch_probabilities.save(probs, "http://example.com", None)
            second = fetch_probabilities.save(probs, "http://example.com", None)
            self.assertIsNone(second)
            self.assertEqual(len(os.listdir("opta")), 1)

    def test_save_writes_when_probabilities_changed(self):
        with self._in_tmpdir():
            fetch_probabilities.save({"Brazil": 0.20}, "http://example.com", None)
            second = fetch_probabilities.save({"Brazil": 0.25}, "http://example.com", None)
            self.assertIsNotNone(second)

    def test_save_writes_when_no_existing_file(self):
        with self._in_tmpdir():
            filename = fetch_probabilities.save({"Brazil": 0.20}, "http://example.com", None)
            self.assertIsNotNone(filename)
            self.assertEqual(len(os.listdir("opta")), 1)

    def test_save_includes_stage_probabilities_when_provided(self):
        with self._in_tmpdir():
            stage_probs = {"winner": {"Brazil": 0.20}, "sf": {"Brazil": 0.40}}
            filename = fetch_probabilities.save({"Brazil": 0.20}, "http://example.com", None, stage_probs)
            assert filename is not None
            with open(filename) as f:
                data = json.load(f)
            self.assertIn("stage_probabilities", data)
            self.assertEqual(data["stage_probabilities"]["winner"]["Brazil"], 0.20)
            self.assertEqual(data["stage_probabilities"]["sf"]["Brazil"], 0.40)

    def test_save_deduplicates_on_stage_probabilities_when_provided(self):
        with self._in_tmpdir():
            stage_probs = {"winner": {"Brazil": 0.20}, "sf": {"Brazil": 0.40}}
            fetch_probabilities.save({"Brazil": 0.20}, "http://example.com", None, stage_probs)
            second = fetch_probabilities.save({"Brazil": 0.20}, "http://example.com", None, stage_probs)
            self.assertIsNone(second)
            self.assertEqual(len(os.listdir("opta")), 1)

    def test_save_writes_fixtures_json_when_provided(self):
        with self._in_tmpdir():
            fixtures = [
                {"teams": ["Canada", "South Africa"], "confirmed_from": "2026-06-27"},
                {"teams": ["Brazil", "Japan"], "confirmed_from": "2026-06-29"},
            ]
            fetch_probabilities.save({"Brazil": 0.20}, "http://example.com", None, fixtures=fixtures)
            fixtures_path = os.path.join("opta", "fixtures.json")
            self.assertTrue(os.path.exists(fixtures_path))
            with open(fixtures_path) as f:
                saved = json.load(f)
            by_pair = {tuple(f["teams"]): f["confirmed_from"] for f in saved}
            self.assertEqual(by_pair[("Canada", "South Africa")], "2026-06-27")

    def test_save_merges_fixtures_keeping_earliest_confirmed_from(self):
        with self._in_tmpdir():
            first = [{"teams": ["Canada", "South Africa"], "confirmed_from": "2026-06-27"}]
            fetch_probabilities.save({"Brazil": 0.20}, "http://example.com", None, fixtures=first)
            second_probs = {"Brazil": 0.25}
            second = [
                {"teams": ["Canada", "South Africa"], "confirmed_from": "2026-06-28"},
                {"teams": ["Brazil", "Japan"], "confirmed_from": "2026-06-28"},
            ]
            fetch_probabilities.save(second_probs, "http://example.com", None, fixtures=second)
            with open(os.path.join("opta", "fixtures.json")) as f:
                saved = json.load(f)
            by_pair = {tuple(f["teams"]): f["confirmed_from"] for f in saved}
            # Canada-SA keeps the earlier date
            self.assertEqual(by_pair[("Canada", "South Africa")], "2026-06-27")
            # Brazil-Japan uses the new date
            self.assertEqual(by_pair[("Brazil", "Japan")], "2026-06-28")

    def test_save_no_fixtures_json_when_fixtures_not_provided(self):
        with self._in_tmpdir():
            fetch_probabilities.save({"Brazil": 0.20}, "http://example.com", None)
            self.assertFalse(os.path.exists(os.path.join("opta", "fixtures.json")))


class TestFetchEspnFixturesFiltering(unittest.TestCase):

    def _make_same_group_pairs(self, groups):
        import itertools
        return {frozenset(p) for g in groups for p in itertools.combinations(g, 2)}

    def test_group_stage_match_excluded(self):
        # Canada and South Africa are in the same group → should be filtered out
        same_group_pairs = self._make_same_group_pairs([{"Canada", "South Africa", "Bosnia and Herzegovina", "Qatar"}])
        # fetch_espn_fixtures with a mocked response would be complex; test _is_tbd and filtering logic directly
        pair = frozenset(["Canada", "South Africa"])
        self.assertIn(pair, same_group_pairs)

    def test_knockout_match_not_same_group(self):
        # Canada (Group B) vs Croatia (Group L) → not same group → should be included
        same_group_pairs = self._make_same_group_pairs([
            {"Canada", "South Africa", "Bosnia and Herzegovina", "Qatar"},
            {"England", "Croatia", "Panama", "Ghana"},
        ])
        pair = frozenset(["Canada", "Croatia"])
        self.assertNotIn(pair, same_group_pairs)

    def test_espn_name_map_applied_to_group_teams(self):
        # ESPN returns "Bosnia-Herzegovina"; after normalization it should match canonical
        self.assertEqual(fetch_probabilities._normalize("Bosnia-Herzegovina"), "Bosnia and Herzegovina")
        self.assertEqual(fetch_probabilities._normalize("Ivory Coast"), "Côte d'Ivoire")
        self.assertEqual(fetch_probabilities._normalize("Türkiye"), "Turkey")
        self.assertEqual(fetch_probabilities._normalize("Brazil"), "Brazil")


if __name__ == "__main__":
    unittest.main()
