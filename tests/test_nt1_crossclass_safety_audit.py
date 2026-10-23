"""Cross-class NT1 read-only risk report source tests.

These tests cover ten class messages and conservative core offhand branches.
They do NOT compile AzerothCore, predict talent-hook side effects or authorise Apply.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src" / "Systems" / "BotTalentImport.cpp").read_text(encoding="utf-8")
CONF = (ROOT / "conf" / "mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")


def section(start: str, end: str) -> str:
    first = CPP.index(start)
    last = CPP.index(end, first + len(start))
    return CPP[first:last]


AUDIT = section(
    "    void PrintAltBotCrossClassSafetyAudit(",
    "    // Must run inside ImportScope.",
)
REPAIR = section("    void PrintAltBotRepairPreview(", "    void PrintPreview(")
READINESS = section("    bool CheckApplyReadiness(", "    bool ApplyValidated(")
APPLY = section("    bool ApplyValidated(", "    bool ReadArguments(")
HANDLE = section("    static bool HandleRepairPreview(", "    static bool HandleApply(")


def core_branch_model(
    off_type: str | None,
    main_subclass: str | None,
    main_two_handed: bool,
    dual_wield: bool,
    known_dual_spell: bool,
    titan_grip: bool,
) -> str:
    """Synthetic summary of the report's conservative branches, NOT the game."""
    if off_type is None:
        return "EMPTY"
    main_forces = main_subclass in {"staff", "polearm", "fishing-pole"}
    dual_risk = off_type in {"offhand-weapon", "weapon"} and (
        not dual_wield or not known_dual_spell
    )
    # AzerothCore clears Titan's Grip BEFORE the offhand recheck.
    titan_risk = off_type == "two-hand" or main_two_handed
    if main_forces or dual_risk or titan_risk:
        return "CORE_RELOCATION_RISK"
    if off_type in {"offhand-weapon", "weapon"}:
        return "WEAPON_ABILITY_DEPENDENT"
    return "NO_CURRENT_CORE_TRIGGER_NOT_PERMISSION"


class CrossClassReadOnlyRiskTests(unittest.TestCase):
    def test_all_ten_classes_present_once(self):
        for name in (
            "CLASS_WARRIOR",
            "CLASS_PALADIN",
            "CLASS_HUNTER",
            "CLASS_ROGUE",
            "CLASS_PRIEST",
            "CLASS_DEATH_KNIGHT",
            "CLASS_SHAMAN",
            "CLASS_MAGE",
            "CLASS_WARLOCK",
            "CLASS_DRUID",
        ):
            self.assertEqual(AUDIT.count("case " + name + ":"), 1, name)

    def test_read_only_classifier_has_no_mutating_calls(self):
        uncommented = re.sub(r"//[^\n]*", "", AUDIT)
        dangerous = re.compile(
            r"\b(?:resetTalents|ActivateSpec|SetActiveSpec|"
            r"AutoUnequipOffhandIfNeed|LearnTalent|SaveToDB|DirectExecute|"
            r"RemovePet|EquipNewItem|MoveItemFromInventory|"
            r"StoreItem|RemoveItem|SetGlyph)\s*\("
        )
        self.assertIsNone(dangerous.search(uncommented))

    def test_source_reads_both_weapon_slots_without_moving_items(self):
        self.assertIn("EQUIPMENT_SLOT_MAINHAND", AUDIT)
        self.assertIn("EQUIPMENT_SLOT_OFFHAND", AUDIT)
        self.assertIn("bot->GetItemByPos(", AUDIT)
        self.assertIn("main->GetTemplate()", AUDIT)
        self.assertIn("off->GetTemplate()", AUDIT)
        self.assertIn("main->GetEntry()", AUDIT)
        self.assertIn("off->GetEntry()", AUDIT)

    def test_does_not_dereference_unknown_item_template(self):
        self.assertIn("if (!off)", AUDIT)
        self.assertIn("else if (!offType || (main && !mainType))", AUDIT)
        self.assertIn("KEEP BLOCKED", AUDIT)

    def test_real_core_weapon_flags_and_subclasses_checked(self):
        for phrase in (
            "INVTYPE_WEAPONOFFHAND",
            "INVTYPE_WEAPON",
            "INVTYPE_2HWEAPON",
            "ITEM_SUBCLASS_WEAPON_STAFF",
            "ITEM_SUBCLASS_WEAPON_POLEARM",
            "ITEM_SUBCLASS_WEAPON_FISHING_POLE",
            "bot->CanDualWield()",
            "bot->CanTitanGrip()",
            "mainType->InventoryType == INVTYPE_2HWEAPON",
            "bot->HasSpell(674)",
        ):
            self.assertIn(phrase, AUDIT)

    def test_weapon_capabilities_are_not_declared_safe_even_if_currently_present(self):
        self.assertIn("WEAPON-ABILITY DEPENDENT", AUDIT)
        self.assertIn("current abilities are not a guarantee", AUDIT)
        self.assertIn("NO CURRENT CORE RELOCATION", AUDIT.upper())

    def test_class_risk_messages_are_advisory_not_verified(self):
        self.assertIn("Class-specific risk reminders, NOT a prediction", AUDIT)
        self.assertIn("Check both specs", AUDIT)
        self.assertIn("Unknown class: unsupported risks", AUDIT)

    def test_pet_inactive_glyphs_and_external_hooks_disclosed(self):
        self.assertIn("bot->GetPet()", AUDIT)
        self.assertIn("Unslotted/stabled pet and guardian data UNKNOWN", AUDIT)
        self.assertIn("INACTIVE glyphs/actions not inspected", AUDIT)
        self.assertIn("BotTalentCompletion.Enabled", AUDIT)
        self.assertIn("Other Playerbots talent changes", AUDIT)
        self.assertIn("NO spec switch performed", AUDIT)

    def test_printed_only_after_alt_owner_and_allowlist_validation(self):
        self.assertIn("CanApplyToAltBot(issuer, error)", HANDLE)
        self.assertIn("sRandomPlayerbotMgr.IsRandomBot(bot)", HANDLE)
        self.assertIn("PrintAltBotRepairPreview(handler, issuer, bot, build)", HANDLE)
        self.assertIn("PrintAltBotCrossClassSafetyAudit(handler, bot)", REPAIR)

    def test_offhand_and_pet_guards_not_bypassed(self):
        self.assertIn("Alt Bot NT1 Apply blocked: an offhand item is", READINESS)
        self.assertIn("Alt Bot NT1 Apply blocked: the bot has an active", READINESS)
        self.assertIn("EQUIPMENT_SLOT_OFFHAND", READINESS)
        self.assertIn("bot->GetPet() != nullptr", READINESS)
        self.assertIn("CheckApplyReadiness(issuer, bot, requested, error, &snapshot,", APPLY)

    def test_read_only_access_modes_still_block_apply(self):
        self.assertIn("return mode == 3 || mode == 4;", CPP)
        self.assertIn("if (IsReadOnlyAccessMode())", APPLY)
        self.assertIn("if (IsReadOnlyAccessMode())", READINESS)
        self.assertIn("NaxxramasBotTalentImport::IsReadOnlyAccessMode()", CPP)
        self.assertIn("NaxxramasCore.BotTalentImport.AccessMode = 0", CONF)

    def test_synthetic_caster_orb_onehand_has_no_known_core_trigger(self):
        self.assertEqual(
            core_branch_model("holdable", "mace", False, False, False, False),
            "NO_CURRENT_CORE_TRIGGER_NOT_PERMISSION",
        )

    def test_synthetic_shield_onehand_has_no_known_core_trigger(self):
        self.assertEqual(
            core_branch_model("shield", "sword", False, True, True, False),
            "NO_CURRENT_CORE_TRIGGER_NOT_PERMISSION",
        )

    def test_synthetic_staff_with_orb_is_risky(self):
        self.assertEqual(
            core_branch_model("holdable", "staff", True, False, False, False),
            "CORE_RELOCATION_RISK",
        )

    def test_synthetic_shaman_dual_wield_loss_is_risky(self):
        self.assertEqual(
            core_branch_model("offhand-weapon", "mace", False, True, False, False),
            "CORE_RELOCATION_RISK",
        )

    def test_synthetic_dual_wield_weapon_is_not_automatically_safe(self):
        self.assertEqual(
            core_branch_model("offhand-weapon", "sword", False, True, True, False),
            "WEAPON_ABILITY_DEPENDENT",
        )

    def test_synthetic_twohand_main_even_with_current_titans_grip_is_risky(self):
        self.assertEqual(
            core_branch_model("holdable", "sword", True, True, True, True),
            "CORE_RELOCATION_RISK",
        )

    def test_synthetic_twohand_offhand_is_risky(self):
        self.assertEqual(
            core_branch_model("two-hand", "sword", False, True, True, True),
            "CORE_RELOCATION_RISK",
        )

    def test_synthetic_no_offhand_does_not_authorise_reset(self):
        self.assertEqual(
            core_branch_model(None, "mace", False, False, False, False),
            "EMPTY",
        )
        self.assertIn("NOT proof the talent reset is safe", AUDIT)

    def test_no_new_destructive_repair(self):
        self.assertNotIn('{"repairapply"', CPP)
        self.assertIn("NT1 ALT REPAIR DISABLED", REPAIR)
        self.assertIn("NT1 ALT SAFETY VERDICT: INSPECTION ONLY", AUDIT)

    def test_main_code_does_not_include_conflicting_ip_header(self):
        self.assertNotIn('#include "IndividualProgression.h"', CPP)


    def test_unknown_template_reports_item_ids_no_dereference(self):
        self.assertIn("UNKNOWN item template (main item {}", AUDIT)
        self.assertIn("main ? main->GetEntry() : 0, off->GetEntry()", AUDIT)
        self.assertIn("!offType || (main && !mainType)", AUDIT)
        self.assertIn("KEEP BLOCKED; cannot assess relocation.", AUDIT)

    def test_unknown_class_has_safe_non_null_chat_label(self):
        self.assertIn('className ? className : "unknown"', AUDIT)
        self.assertIn("Unknown class: unsupported risks; keep blocked", AUDIT)

    def test_synthetic_missing_mainhand_does_not_grant_permission(self):
        self.assertEqual(
            core_branch_model("holdable", None, False, False, False, False),
            "NO_CURRENT_CORE_TRIGGER_NOT_PERMISSION",
        )
        self.assertEqual(
            core_branch_model("offhand-weapon", None, False, False, False, False),
            "CORE_RELOCATION_RISK",
        )


if __name__ == "__main__":
    unittest.main()
