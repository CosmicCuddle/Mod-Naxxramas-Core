"""Read-only source contracts for the Alt Bot talent/gear boundary.

These do not prove that AzerothCore resetTalents, its hooks, other modules or
asynchronous Playerbots tasks preserve equipment. Never interpret them as
permission to drop offhand/pet blocks or execute Apply on earned characters.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Systems/BotTalentImport.cpp").read_text("utf-8")
COMPLETION = (ROOT / "src/Systems/BotTalentCompletion.cpp").read_text("utf-8")
CONFIG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text("utf-8")
BOUNDARY = (
    ROOT / "docs/NT1-GRIMFEATHER-GEAR-RESET-API-DECISION-2026-10-14.md"
).read_text("utf-8")

READINESS = SOURCE.split("    bool CheckApplyReadiness(", 1)[1].split(
    "    bool ApplyValidated(", 1
)[0]
APPLY = SOURCE.split("    bool ApplyValidated(", 1)[1].split(
    "    bool ReadArguments(", 1
)[0]


def without_comments(s):
    return re.sub(r"//[^\n]*|/\*[\s\S]*?\*/", "", s)


class AltBotEquipmentBoundaryTests(unittest.TestCase):
    def test_nt1_does_not_invoke_any_playerbots_auto_gear_or_factory_refresh(self):
        for action in ("AutoGear(", "InitEquipment(", "PlayerbotFactory(",
                       "DestroyEquippedGear(", "Refresh(", "Randomize("):
            with self.subTest(action=action):
                self.assertNotIn(action, without_comments(APPLY))
        self.assertIn("bool const randomBot = sRandomPlayerbotMgr.IsRandomBot(bot);",
                      APPLY)

    def test_different_build_remains_blocked_before_any_reset_for_offhand(self):
        self.assertIn("if (!randomBot && !verifiedNoOp)", READINESS)
        self.assertIn("EQUIPMENT_SLOT_OFFHAND", READINESS)
        self.assertIn("bot->GetPet() != nullptr", READINESS)
        self.assertLess(READINESS.index("EQUIPMENT_SLOT_OFFHAND"),
                        READINESS.index("return false;\n            }\n\n            if (bot->GetPet"))
        self.assertLess(APPLY.index("CheckApplyReadiness("),
                        APPLY.index("bot->resetTalents(true)"))

    def test_only_exact_verified_noop_skips_the_reset(self):
        self.assertIn("bool const verifiedNoOp = !randomBot", READINESS)
        self.assertIn("HasVerifiedExactActiveBuild(bot, requested)", READINESS)
        self.assertLess(APPLY.index("if (verifiedNoOp)"),
                        APPLY.index("ImportScope const scope(bot)"))
        self.assertLess(APPLY.index("if (verifiedNoOp)"),
                        APPLY.index("bot->resetTalents(true)"))
        self.assertEqual(APPLY.count("bot->resetTalents(true)"), 2)

    def test_existing_completion_hook_does_not_regear(self):
        hook = COMPLETION.split("    void OnPlayerTalentsReset(", 1)[1].split(
            "    void OnPlayerLearnTalents(", 1
        )[0]
        for forbidden in ("AutoGear(", "InitEquipment(", "AutoUnequipOffhandIfNeed(",
                          "PlayerbotFactory(", "EquipItem(", "RemoveItem("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, without_comments(hook))
        self.assertIn("NaxxramasBotTalentImport::IsImportOperation(bot)", hook)

    def test_no_unsafe_gear_override_or_claim_of_existing_fix(self):
        for override in ("AllowGearMutation", "AllowEquipmentChanges",
                         "IgnoreAltBotOffhand"):
            with self.subTest(override=override):
                self.assertNotIn(override, CONFIG)
                self.assertNotIn(override, SOURCE)
        self.assertIn("not sufficient", BOUNDARY)
        self.assertIn("m_usedTalentCount", BOUNDARY)
        self.assertIn("cannot veto the change", BOUNDARY)
        self.assertIn("stop and ask for a separate owner decision", BOUNDARY)


if __name__ == "__main__":
    unittest.main()
