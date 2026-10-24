"""P0 four-fix + B10 thread-safety combined REVIEW-ONLY source contract.

This does not prove a native build, Worldserver runtime or owner Playerbots
compatibility. Never infer approval to merge, enable defaults or deploy.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "src/Systems/BotRaidConsumables.cpp").read_text()
CFG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text()
LOADER = (ROOT / "src/NaxxramasCore_loader.cpp").read_text()
MEETING = (ROOT / "src/Systems/MeetingStoneProgression.cpp").read_text()
GOLEMAGG = (ROOT / "src/Systems/BotGolemaggReachGuard.cpp").read_text()


class CombinedP0B10SourceContract(unittest.TestCase):
    def test_120_second_one_shot_stays_exactly_once(self):
        self.assertEqual(
            SRC.count("NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS};"), 1
        )
        self.assertNotIn("NaxxramasOneShotTimer Timer{90 * IN_MILLISECONDS};", SRC)
        self.assertIn("NO retries at 125s/240s", SRC)

    def test_crossmap_gfpp_gate_does_not_move_deadline_or_deref_first(self):
        start = SRC.index("void ProcessOneShotFireProtections(")
        section = SRC[start:SRC.index("void CheckTrackedAuras(", start)]
        gate = "(IsCrossMapAuraSafetyEnabled() &&"
        self.assertIn("pending.Timer.ConsumeIfDue(diff)", section)
        self.assertIn(gate, section)
        self.assertLess(section.index("pending.Timer.ConsumeIfDue(diff)"),
                        section.index(gate))
        self.assertLess(section.index(gate), section.index("!bot->IsInWorld()"))

    def test_thread_safety_state_and_queue_survive_integration(self):
        self.assertIn("struct RaidConsumableTracker final : DataMap::Base", SRC)
        self.assertIn("NaxxramasCrossMapAura::RemovalQueue CrossMapAuraRemovals;", SRC)
        self.assertIn("EraseRaidConsumableTracker(player);", SRC)
        self.assertNotIn("RaidConsumableTrackers.erase(", SRC)

    def test_default_off_safety_and_separate_exact_bot_guard(self):
        for key in (
            "NaxxramasCore.BotConsumables.CrossMapAuraSafety = 0",
            "NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled = 0",
            "NaxxramasCore.Playerbots.GolemaggMeleeGuard.Enabled = 0",
            'NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName = ""',
        ):
            with self.subTest(key=key):
                self.assertIn(key, CFG)
        self.assertIn("one optional 120-second GFPP refresh", CFG)
        self.assertNotIn("one optional 90-second GFPP refresh", CFG)

    def test_four_fix_guard_and_warlock_components_stay_registered(self):
        for symbol in (
            "AddBotRaidConsumablesScripts();",
            "AddMeetingStoneProgressionScripts();",
            "AddBotGolemaggReachGuardScripts();",
        ):
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, LOADER)
        self.assertIn("NaxxramasCore", MEETING)
        self.assertIn("Golemagg", GOLEMAGG)

    def test_world_thread_hook_is_preserved_without_implicit_enable(self):
        self.assertIn("NaxxramasCoreBotRaidConsumablesWorld", SRC)
        self.assertIn("NaxxramasCore.BotConsumables.CrossMapAuraSafety", SRC)
        self.assertIn("std::atomic<bool> CrossMapAuraSafetyEnabled{ false };", SRC)


if __name__ == "__main__":
    unittest.main()
