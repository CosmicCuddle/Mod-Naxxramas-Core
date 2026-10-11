"""Static integration contract: read-only NT1L1 + Alt Bot diagnostics + mode 3.

Source-level tests only, NOT a C++ compiler or proof of Worldserver behaviour.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src" / "Systems" / "BotTalentImport.cpp").read_text(encoding="utf-8")
CONFIG = (ROOT / "conf" / "mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")


def section(begin, end):
    a = CPP.index(begin)
    b = CPP.index(end, a + len(begin))
    return CPP[a:b]


class CombinedNT1SourceContracts(unittest.TestCase):
    def test_both_commands_registered_once(self):
        for name in ("preview", "project", "repairpreview", "apply"):
            self.assertEqual(CPP.count('{"' + name + '", Handle'), 1, name)

    def test_nt1l1_projects_only_validated_final_nt1(self):
        block = section("    bool ProjectPriorityCode(", "    // Capture the current active spec before any reset.")
        self.assertIn("ParseCode(projectedCode, bot, plan, error)", block)
        self.assertIn("sourcePoints != fullPoints", block)
        self.assertIn("sourcePoints <= targetPoints", block)

    def test_projection_command_is_read_only(self):
        block = section("    static bool HandleProject(", "    static bool HandleRepairPreview(")
        uncommented = re.sub(r"//[^\n]*", "", block)
        self.assertNotRegex(
            uncommented,
            r"\b(?:LearnTalent|resetTalents|SaveToDB|DirectExecute|"
            r"EquipNewItem|DestroyItem|ApplyValidated|RemoveItem|"
            r"SetActiveSpec)\s*\(",
        )
        self.assertIn("CheckPlayerProgressionEra(issuer, plan.Progression, error)", block)

    def test_repair_diagnostic_retains_altbot_authorization(self):
        block = section("    static bool HandleRepairPreview(", "    static bool HandleApply(")
        self.assertIn("CanApplyToAltBot(issuer, error)", block)
        self.assertIn("sRandomPlayerbotMgr.IsRandomBot(bot)", block)
        self.assertIn("PrintAltBotRepairPreview(handler, issuer, bot, build)", block)

    def test_old_build_snapshot_and_offhand_risk_still_checked(self):
        block = section("    bool CheckApplyReadiness(", "    bool ApplyValidated(")
        for phrase in (
            "EncodeExisting(bot, requested.Progression)",
            "CanApplyToAltBot(issuer, error)",
            "EQUIPMENT_SLOT_OFFHAND",
            "bot->GetPet() != nullptr",
            "CheckPlayerProgressionEra(issuer, requested.Progression, error)",
        ):
            self.assertIn(phrase, block)

    def test_read_only_mode_3_disables_apply_before_reset(self):
        readiness = section("    bool CheckApplyReadiness(", "    bool ApplyValidated(")
        apply = section("    bool ApplyValidated(", "    bool ReadArguments(")
        self.assertIn("if (AccessMode() == 3)", readiness)
        self.assertIn("NT1 READ-ONLY MODE: Apply is disabled", readiness)
        self.assertLess(
            apply.index("CheckApplyReadiness(issuer, bot, requested, error, &snapshot)"),
            apply.index("bot->resetTalents(true)"),
        )
        self.assertLess(
            readiness.index("EncodeExisting(bot, requested.Progression)"),
            readiness.index("if (AccessMode() == 3)"),
        )

    def test_mode_3_does_not_grant_player_permissions(self):
        start = section("    uint32 AccessMode()", "    bool IsGM(")
        self.assertIn("return mode <= 3 ? mode : 0;", start)
        self.assertIn("return AccessMode() == 2;", start)
        self.assertIn("return AccessMode() == 2;", start)

    def test_no_new_destructive_repair_handler(self):
        self.assertNotIn('{"repairapply"', CPP)
        self.assertNotIn('{"repair",', CPP)
        self.assertIn("NT1 ALT REPAIR DISABLED", CPP)

    def test_alt_protected_state_is_not_persisted(self):
        snap = section("    // Read-only volatile observation", "    // Must run inside ImportScope.")
        self.assertIn("GetTalentMap()", snap)
        self.assertIn("GetSpellMap()", snap)
        self.assertIn("EquippedItemGuids", snap)
        self.assertNotRegex(snap, r"\b(?:DirectExecute|SaveToDB|SetGlyph)\s*\(")

    def test_config_defaults_remain_fail_closed(self):
        self.assertIn("NaxxramasCore.BotTalentImport.AccessMode = 0", CONFIG)
        self.assertIn('NaxxramasCore.BotTalentImport.AltBotAllowedPlayers = ""', CONFIG)
        self.assertIn("# 3 = GM accounts ONLY", CONFIG)

    def test_priority_fixture_and_checker_are_both_integrated(self):
        self.assertTrue((ROOT / "scripts" / "check_nt1l1_priority.py").is_file())
        self.assertTrue(
            (ROOT / "tests" / "fixtures" / "nt1l1_vanilla_frost_mage_2026_10_08.json").is_file()
        )

    def test_no_incompatible_individual_progression_header(self):
        self.assertNotIn('#include "IndividualProgression.h"', CPP)


if __name__ == "__main__":
    unittest.main()
