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

    def test_every_changed_alt_build_rejects_before_any_core_reset(self):
        # No special exemption for Priest caster offhands, empty offhand,
        # class/role change, higher GM privilege or a missing active pet.
        guard = READINESS.split("if (!randomBot && !verifiedNoOp)", 1)[1].split(
            "// Both mode 3", 1
        )[0]
        self.assertIn("EQUIPMENT_SLOT_OFFHAND", guard)
        self.assertIn("bot->GetPet() != nullptr", guard)
        self.assertIn("Alt Bot NT1 different-build Apply blocked:", guard)
        self.assertIn("cannot guarantee zero equipment", guard)
        self.assertIn("No talents or equipment changed.", guard)
        self.assertGreaterEqual(guard.count("return false;"), 3)
        self.assertNotIn("bot->resetTalents(", guard)
        self.assertNotIn("bot->LearnTalent(", guard)
        self.assertNotIn("CharacterDatabase.", guard)
        self.assertNotIn("ImportScope", without_comments(guard))
        self.assertLess(READINESS.index("Alt Bot NT1 different-build Apply blocked:"),
                        READINESS.index("// Both mode 3"))
        self.assertLess(APPLY.index("CheckApplyReadiness("),
                        APPLY.index("ImportScope const scope(bot)"))

    def test_random_bot_preserves_original_different_build_path(self):
        # The new preflight stop is nested under !randomBot. A random
        # Playerbot still uses its existing ordinary reset/recovery branch.
        self.assertIn("if (!randomBot && !verifiedNoOp)", READINESS)
        self.assertIn("bool const randomBot = sRandomPlayerbotMgr.IsRandomBot(bot);",
                      APPLY)
        self.assertEqual(APPLY.count("bot->resetTalents(true)"), 2)
        self.assertIn("if (!randomBot)", APPLY)

    def test_apply_has_independent_altbot_reset_kill_switch(self):
        # The preflight check alone is not sufficient if future code
        # inadvertently adds a different path through ApplyValidated.
        no_op_end = APPLY.index("if (verifiedNoOp)")
        classification = APPLY.index(
            "bool const randomBot = sRandomPlayerbotMgr.IsRandomBot(bot);")
        gate_start = APPLY.index("if (!randomBot)", classification)
        gate_end = APPLY.index("return false;", gate_start)
        scope = APPLY.index("ImportScope const scope(bot)")
        first_reset = APPLY.index("bot->resetTalents(true)")
        self.assertLess(no_op_end, classification)
        self.assertLess(classification, gate_start)
        self.assertLess(gate_start, gate_end)
        self.assertLess(gate_end, scope)
        self.assertLess(gate_end, first_reset)
        gate = without_comments(APPLY[gate_start:gate_end + len("return false;")])
        self.assertIn("Alt Bot NT1 changed-build Apply blocked:", gate)
        self.assertIn("No talents or equipment changed.", gate)
        for forbidden in ("resetTalents(", "LearnTalent(", "SaveToDB(",
                          "ImportScope", "EquipItem(", "StoreItem(",
                          "AutoGear(", "CharacterDatabase."):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, gate)

    def test_random_bot_resets_are_after_the_independent_gate(self):
        # Keep the same two existing reset paths for Random Bots.
        # This contract is source-level; gameplay still needs testing.
        classification = APPLY.index("bool const randomBot =")
        self.assertLess(APPLY.index("if (!randomBot)", classification),
                        APPLY.index("bot->resetTalents(true)"))
        self.assertEqual(APPLY.count("bot->resetTalents(true)"), 2)
        self.assertIn("if (!randomBot)", APPLY)

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
        self.assertIn("keep different-build Apply blocked before mutation", BOUNDARY)
        self.assertIn("all implementation changes MUST stay inside", BOUNDARY)
        self.assertIn("never modify AzerothCore", BOUNDARY)
        # No proposed upstream/core patch fallback may be a release option.
        self.assertNotIn("before drafting any minimal optional Grimfeather core patch",
                         BOUNDARY)

    def test_published_contract_has_absolute_module_only_rule(self):
        policy = (ROOT / "docs/NT1-ALT-BOT-ZERO-GEAR-MUTATION-CONTRACT.md"
                  ).read_text("utf-8")
        plan = (ROOT / "docs/NT1-ZERO-GEAR-MUTATION-IMPLEMENTATION-PLAN-2026-10-13.md"
                ).read_text("utf-8")
        roadmap = (ROOT / "ROADMAP.md").read_text("utf-8")
        for document in (policy, plan, roadmap):
            with self.subTest(doc=document[:60]):
                self.assertIn("mod-naxxramas-core", document)
                self.assertIn("Playerbots", document)
                self.assertIn("AzerothCore", document)
        self.assertIn("safely refuse it before any mutation", policy)
        self.assertIn("no future AzerothCore/core fork patch", plan)
        self.assertIn("Never modify AzerothCore", roadmap)


if __name__ == "__main__":
    unittest.main()
