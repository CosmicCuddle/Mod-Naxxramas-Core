"""F11 source characterization: no new gameplay policy or production edit.

Models the EXISTING merged Shade CastFires() player census and wave sizes.
It intentionally documents surprising results. A green test is not a
difficulty recommendation or owner-gameplay acceptance.
"""
from dataclasses import dataclass
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SHADE = ROOT / "src/Events/HallowsEndShadeOfTheHorseman.cpp"
SOLO = ROOT / "src/Events/HallowsEndSoloFire.h"
CONFIG = ROOT / "conf/mod_naxxramas_core.conf.dist"


@dataclass(frozen=True)
class FireCase:
    humans: int
    bots: int
    solo_enabled: bool = True
    initial: bool = True
    unlit: int = 10
    total_triggers: int = 12


def current_count(case: FireCase) -> int:
    """Currently only exactly one human + SoloFire opt-in filters bots."""
    assert case.humans >= 0 and case.bots >= 0
    if case.solo_enabled and case.humans == 1:
        return case.humans
    return case.humans + case.bots


def current_cast_fires(case: FireCase):
    """Literal integer-wave/rate arithmetic from merged CastFires source."""
    visible = current_count(case)
    if case.unlit == 0 or visible == 0:
        return False, 0, 0
    # Noninitial playerCount is *players.size() - 1*.
    player_count = visible - 1
    if not case.initial:
        player_rate = max(0.0, 0.5 - player_count * 0.25)
        if case.unlit < case.total_triggers * player_rate:
            return False, 0, player_count
    else:
        player_count += 1
    size_count = player_count // 3 + 1
    if case.initial and player_count > 0:
        size_count += player_count % 2
    # RandomResize truncates to the candidates it was given.
    return True, min(case.unlit, size_count), player_count


def research_only_human_census(case: FireCase, api_available: bool):
    """FUTURE input eligibility, not an elected balancing curve."""
    if not api_available:
        return None
    return case.humans


class F11ExistingSourceAndFutureSafety(unittest.TestCase):
    def test_merged_f10_solo_excludes_nearby_bots_when_enabled(self):
        baseline = current_cast_fires(FireCase(1, 0))
        for bots in (1, 3, 15):
            self.assertEqual(current_cast_fires(FireCase(1, bots)), baseline)

    def test_legacy_disabled_configuration_preserves_bot_inflation(self):
        self.assertEqual(current_count(FireCase(1, 4, solo_enabled=False)), 5)
        self.assertNotEqual(current_cast_fires(FireCase(1, 4, solo_enabled=False)),
                            current_cast_fires(FireCase(1, 0, solo_enabled=False)))

    def test_current_two_human_case_counts_bots(self):
        self.assertEqual(current_count(FireCase(2, 3)), 5)
        self.assertNotEqual(current_cast_fires(FireCase(2, 3)),
                            current_cast_fires(FireCase(2, 0)))

    def test_current_three_human_case_counts_bots(self):
        self.assertEqual(current_count(FireCase(3, 3)), 6)

    def test_bots_only_are_not_recognized_as_solo(self):
        self.assertEqual(current_count(FireCase(0, 3)), 3)

    def test_zero_entities_do_not_ignite(self):
        self.assertEqual(current_cast_fires(FireCase(0, 0)), (False, 0, 0))

    def test_no_unlit_triggers_do_not_ignite(self):
        self.assertEqual(current_cast_fires(FireCase(3, 1, unlit=0)), (False, 0, 0))

    def test_initial_native_counts_are_not_monotonic(self):
        # 1 human -> 2 initial targets; 2 humans -> 1; 3 -> 3; 4 -> 2
        actual = [current_cast_fires(FireCase(n, 0))[1] for n in range(1, 5)]
        self.assertEqual(actual, [2, 1, 3, 2])
        self.assertTrue(actual[1] < actual[0])
        self.assertTrue(actual[3] < actual[2])

    def test_later_wave_rate_gate_uses_unlit_not_burning(self):
        self.assertFalse(current_cast_fires(FireCase(1, 0, initial=False,
                                                   unlit=5, total_triggers=12))[0])
        self.assertTrue(current_cast_fires(FireCase(1, 0, initial=False,
                                                  unlit=6, total_triggers=12))[0])

    def test_later_wave_threshold_reaches_zero_at_three_counted(self):
        self.assertEqual(current_cast_fires(FireCase(3, 0, initial=False,
                                                  unlit=1, total_triggers=12)), (True, 1, 2))

    def test_count_drops_around_player_exit_in_current_source(self):
        with_two = current_cast_fires(FireCase(2, 0))[1]
        with_one = current_cast_fires(FireCase(1, 0))[1]
        self.assertEqual((with_two, with_one), (1, 2))
        # A sudden smaller party currently can receive a larger initial wave.

    def test_future_policy_will_need_real_player_id_api(self):
        self.assertIsNone(research_only_human_census(FireCase(1, 5), False))
        self.assertEqual(research_only_human_census(FireCase(1, 5), True), 1)
        self.assertEqual(research_only_human_census(FireCase(3, 5), True), 3)

    def test_no_new_formula_or_runtime_setting_has_been_selected(self):
        # Characterization is deliberately not a feature implementation.
        self.assertFalse(callable(globals().get("future_" + "scaled_wave")))

    def test_current_checkout_matches_source_assumptions(self):
        if not all(x.is_file() for x in (SHADE, SOLO, CONFIG)):
            self.skipTest("run under full Mod-Naxxramas-Core checkout")
        src = SHADE.read_text(encoding="utf-8")
        helper = SOLO.read_text(encoding="utf-8")
        config = CONFIG.read_text(encoding="utf-8")
        for marker in (
            "if (SoloFirePathActive(players))",
            "players.remove_if([](Player* player)",
            "playerCount * 0.25f",
            "(playerCount / 3) + 1",
            "playerCount % 2",
            "events.Repeat(30s)",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, src)
        self.assertIn("FireCastRequestReachesIgnition", helper)
        for key in (
            "NaxxramasCore.HallowsEnd.SoloFire.Enabled = 0",
            "NaxxramasCore.HallowsEnd.SoloFire.OneBucket = 0",
            "NaxxramasCore.HallowsEnd.SoloFire.DisableSpread = 0",
        ):
            self.assertIn(key, config)


if __name__ == "__main__":
    unittest.main()
