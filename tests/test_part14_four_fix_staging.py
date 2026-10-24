"""Part 14 isolated staging checks; not a Worldserver or gameplay test."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def read(name):
    return (ROOT / name).read_text(encoding="utf-8")

C = read("src/Systems/BotRaidConsumables.cpp")
CFG = read("conf/mod_naxxramas_core.conf.dist")
W = read("src/Systems/MeetingStoneProgression.cpp")
G = read("src/Systems/BotGolemaggReachGuard.cpp")
L = read("src/NaxxramasCore_loader.cpp")

class FourFixStaging(unittest.TestCase):
    def test_fire_protection_is_once_at_120_seconds(self):
        self.assertIn("NaxxramasOneShotTimer Timer{120 * IN_MILLISECONDS};", C)
        self.assertNotIn("NaxxramasOneShotTimer Timer{90 * IN_MILLISECONDS};", C)
        self.assertIn("No repeat at 240 seconds.", CFG)
        self.assertIn("NaxxramasCore.BotConsumables.MC.GreaterFireProtection.OneShotEnabled = 0", CFG)

    def test_shaman_quest_totems_never_top_up(self):
        for name in ("EARTH", "FIRE", "WATER", "AIR"):
            self.assertNotIn("topUp(ITEM_" + name + "_TOTEM", C)
        for name in ("ANKH, 5", "SHINY_FISH_SCALES, 20", "FISH_OIL, 20"):
            self.assertIn("topUp(ITEM_" + name + ")", C)

    def test_warlock_portal_is_exact_special_case(self):
        self.assertIn("WARLOCK_RITUAL_PORTAL_GO_ENTRY = 194097", W)
        self.assertIn("WARLOCK_RITUAL_PORTAL_SPELL_ID = 61993", W)
        self.assertIn("if (IsWarlockRitualPortal(go))", W)
        self.assertIn("AddMeetingStoneProgressionScripts();", L)

    def test_golemagg_guard_is_off_and_single_name_only(self):
        self.assertIn("NaxxramasCore.Playerbots.GolemaggMeleeGuard.Enabled = 0", CFG)
        self.assertIn('NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotName = ""', CFG)
        self.assertNotIn("NaxxramasCore.Playerbots.GolemaggMeleeGuard.AllowedBotNames", CFG)
        self.assertIn("ActionExecutionListener", G)
        self.assertIn("AddBotGolemaggReachGuardScripts();", L)

if __name__ == "__main__":
    unittest.main()
