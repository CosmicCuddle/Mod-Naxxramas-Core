"""Static integration contract: read-only NT1L1 + Alt Bot diagnostics + modes 3/4.

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

    def test_both_read_only_modes_denied_before_reset(self):
        readiness = section("    bool CheckApplyReadiness(", "    bool ApplyValidated(")
        apply = section("    bool ApplyValidated(", "    bool ReadArguments(")
        self.assertIn("if (IsReadOnlyAccessMode())", readiness)
        self.assertIn("NT1 READ-ONLY MODE: Apply is disabled", readiness)
        self.assertLess(
            apply.index("if (IsReadOnlyAccessMode())"),
            apply.index("CheckApplyReadiness(issuer, bot, requested, error, &snapshot)"),
        )
        self.assertLess(
            apply.index("CheckApplyReadiness(issuer, bot, requested, error, &snapshot)"),
            apply.index("bot->resetTalents(true)"),
        )
        self.assertLess(
            readiness.index("EncodeExisting(bot, requested.Progression)"),
            readiness.index("if (IsReadOnlyAccessMode())"),
        )

    def test_mode_3_remains_gm_only_and_mode_4_grants_preview_to_controllers(self):
        start = section("    uint32 AccessMode()", "    bool IsGM(")
        self.assertIn("return mode <= 4 ? mode : 0;", start)
        self.assertIn("return AccessMode() == 2 || AccessMode() == 4;", start)
        self.assertIn("return mode == 3 || mode == 4;", start)
        self.assertNotIn("return AccessMode() >= 2;", start)

    def test_handler_denies_both_read_only_modes_before_validate_request(self):
        handle = section("    static bool HandleApply(", "};\n\nvoid AddBotTalentImportScripts()")
        self.assertIn("NaxxramasBotTalentImport::IsReadOnlyAccessMode()", handle)
        self.assertLess(
            handle.index("NaxxramasBotTalentImport::IsReadOnlyAccessMode()"),
            handle.index("NaxxramasBotTalentImport::ValidateRequest("),
        )
        self.assertIn("Use preview, project, or repairpreview instead.", handle)

    def test_mode_4_non_gm_still_requires_ownership(self):
        validate = section("    bool ValidateRequest(", "    // Diagnostic-only Alt Bot repair preview.")
        project = section("    static bool HandleProject(", "    static bool HandleRepairPreview(")
        readiness = section("    bool CheckApplyReadiness(", "    bool ApplyValidated(")
        for block in (validate, project, readiness):
            self.assertIn("CanControlBot(", block)

    def test_mode_4_alt_repair_details_keep_human_character_allowlist(self):
        repair = section("    static bool HandleRepairPreview(", "    static bool HandleApply(")
        self.assertIn("CanApplyToAltBot(issuer, error)", repair)
        self.assertIn("PlayerbotsMgr::instance().GetPlayerbotAI(issuer)", repair)
        self.assertIn("sRandomPlayerbotMgr.IsRandomBot(bot)", repair)

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
        self.assertIn("# 4 = All players", CONFIG)

    def test_priority_fixture_and_checker_are_both_integrated(self):
        self.assertTrue((ROOT / "scripts" / "check_nt1l1_priority.py").is_file())
        self.assertTrue(
            (ROOT / "tests" / "fixtures" / "nt1l1_vanilla_frost_mage_2026_10_08.json").is_file()
        )

    def test_no_incompatible_individual_progression_header(self):
        self.assertNotIn('#include "IndividualProgression.h"', CPP)


if __name__ == "__main__":
    unittest.main()
