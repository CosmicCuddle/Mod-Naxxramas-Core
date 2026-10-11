"""Static regression tests for module-side read-only Alt Bot recovery warnings.

No C++ compiler or game runtime is exercised by this suite.
"""
from pathlib import Path
import re
import unittest

CPP = (Path(__file__).resolve().parents[1] / "src/Systems/BotTalentImport.cpp").read_text(encoding="utf-8")
START = CPP.index("    void PrintAltBotRepairPreview(")
END = CPP.index("    void PrintPreview(", START)
PRINTER = CPP[START:END]
UNCOMMENTED = re.sub(r"//[^\n]*", "", PRINTER)


class RecoveryWarningsSafetyTests(unittest.TestCase):
    def test_offhand_state_is_read_only(self):
        self.assertIn("GetItemByPos(INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND)", PRINTER)
        self.assertIn("Offhand slot occupied", PRINTER)

    def test_dual_spec_identification(self):
        self.assertIn("bot->GetActiveSpec() + 1", PRINTER)
        self.assertIn("bot->GetSpecsCount()", PRINTER)

    def test_does_not_claim_gear_safe_when_offhand_empty(self):
        self.assertIn("Even an empty offhand slot cannot prove", PRINTER)
        self.assertIn("NT1 ALT GUARD: ordinary Apply refuses Alt Bots", PRINTER)
        self.assertIn("full recovery is still unproven", PRINTER)
        self.assertIn("Active pet:", PRINTER)

    def test_backup_explicitly_not_verified(self):
        self.assertIn("NT1 ALT BACKUP REQUIRED", PRINTER)
        self.assertIn("NT1 ALT RECOVERY NOT VERIFIED", PRINTER)

    def test_there_is_still_no_repair_apply(self):
        self.assertNotIn('{"repairapply"', CPP)
        self.assertNotIn('{"repair",', CPP)
        self.assertIn('{"repairpreview", HandleRepairPreview', CPP)

    def test_new_printer_cannot_mutate(self):
        self.assertNotRegex(
            UNCOMMENTED,
            r"\b(?:resetTalents|LearnTalent|SaveToDB|DirectExecute|"
            r"EquipNewItem|DestroyItem|MoveItem|AutoUnequipOffhandIfNeed)\s*\("
        )

    def test_existing_altbot_allowlist_and_preflight_retained(self):
        self.assertIn("CanApplyToAltBot(issuer, error)", CPP)
        self.assertIn("CheckApplyReadiness(issuer, bot, proposed, reason)", PRINTER)
        self.assertIn("NT1 ALT REPAIR DISABLED", PRINTER)

    def test_no_individual_progression_header_conflict(self):
        self.assertNotIn('#include "IndividualProgression.h"', CPP)

    def test_risk_guard_is_inside_shared_apply_readiness(self):
        shared = CPP.split("    bool CheckApplyReadiness(", 1)[1].split(
            "    bool ApplyValidated(", 1
        )[0]
        self.assertIn("if (!randomBot)", shared)
        self.assertIn("EQUIPMENT_SLOT_OFFHAND", shared)
        self.assertIn("bot->GetPet() != nullptr", shared)

    def test_risk_guard_denies_before_apply_can_reset(self):
        shared = CPP.split("    bool CheckApplyReadiness(", 1)[1].split(
            "    bool ApplyValidated(", 1
        )[0]
        self.assertLess(shared.rfind("if (!randomBot)"), shared.rfind("return true;"))
        apply_code = CPP.split("    bool ApplyValidated(", 1)[1].split(
            "    bool ReadArguments(", 1
        )[0]
        self.assertLess(
            apply_code.index("CheckApplyReadiness(issuer, bot, requested, error, &snapshot)"),
            apply_code.index("bot->resetTalents(true)"),
        )

    def test_offhand_and_pet_have_separate_explanations(self):
        shared = CPP.split("    bool CheckApplyReadiness(", 1)[1].split(
            "    bool ApplyValidated(", 1
        )[0]
        self.assertIn("Alt Bot NT1 Apply blocked: an offhand item is", shared)
        self.assertIn("Alt Bot NT1 Apply blocked: the bot has an active", shared)
        self.assertIn("Talent reset could move or MAIL it", shared)
        self.assertIn("Talent reset could dismiss it", shared)

    def test_readiness_guard_contains_no_mutations(self):
        shared = CPP.split("    bool CheckApplyReadiness(", 1)[1].split(
            "    bool ApplyValidated(", 1
        )[0]
        shared = re.sub(r"//[^\\n]*", "", shared)
        self.assertNotRegex(
            shared,
            r"\\b(?:resetTalents|LearnTalent|SaveToDB|DirectExecute|"
            r"EquipNewItem|DestroyItem|StoreItem|RemoveItem|"
            r"AutoUnequipOffhandIfNeed)\\s*\\(",
        )

    def test_guard_does_not_change_altbot_allowlist_or_random_path(self):
        shared = CPP.split("    bool CheckApplyReadiness(", 1)[1].split(
            "    bool ApplyValidated(", 1
        )[0]
        self.assertIn("CanApplyToAltBot(issuer, error)", shared)
        self.assertIn("CanApplyToGroupedRandomBot(issuer, bot, error)", shared)
        self.assertLess(
            shared.index("CanApplyToAltBot(issuer, error)"),
            shared.rfind("if (!randomBot)"),
        )


if __name__ == "__main__":
    unittest.main()
