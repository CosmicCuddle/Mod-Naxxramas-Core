"""NT1 offhand-preservation research regression gates (source-only, no Apply).

Synthetic AzerothCore offhand decisions here are MODELLED from the operator's
pinned fork; this module does not import/build that fork and cannot certify
behaviour with live hooks, items, pets, mail, or custom modules.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
NT1 = (ROOT / "src" / "Systems" / "BotTalentImport.cpp").read_text(
    encoding="utf-8"
)
COMPLETION = (ROOT / "src" / "Systems" / "BotTalentCompletion.cpp").read_text(
    encoding="utf-8"
)
LIMITS = (ROOT / "src" / "Systems" / "BotTalentExpansionLimits.cpp").read_text(
    encoding="utf-8"
)
CONF = (ROOT / "conf" / "mod_naxxramas_core.conf.dist").read_text(
    encoding="utf-8"
)


def section(text, start, end):
    first = text.index(start)
    last = text.index(end, first + len(start))
    return text[first:last]


READINESS = section(NT1, "    bool CheckApplyReadiness(", "    bool ApplyValidated(")
APPLY = section(NT1, "    bool ApplyValidated(", "    bool ReadArguments(")
AUDIT = section(
    NT1, "    void PrintAltBotCrossClassSafetyAudit(",
    "    // Must run inside ImportScope."
)
RESET_HOOK = section(
    COMPLETION, "    void OnPlayerTalentsReset(",
    "    void OnPlayerLearnTalents("
)


def model_core_offhand_decision(
    offhand_type,
    mainhand_subclass="other",
    can_dual_wield=False,
    can_titan_grip=False,
    is_two_hand_used=False,
    force=False,
):
    """Synthetic model of exact pinned core's AutoUnequipOffhandIfNeed branch.

    RETAIN means only 'no core relocation from the stated inputs'; never a
    permission to reset, proof of stable inputs, or proof against hooks.
    """
    if offhand_type is None:
        return "NO_OFFHAND"
    if offhand_type in {"offhand_weapon", "weapon"} and not can_dual_wield:
        force = True
    if mainhand_subclass in {"polearm", "staff", "fishing_pole"}:
        force = True
    if not force and (
        can_titan_grip
        or (offhand_type != "two_hand_weapon" and not is_two_hand_used)
    ):
        return "RETAIN_IN_CORE_MODEL_ONLY"
    return "CORE_RELOCATION_TRIGGER"


class OffhandSourceContractTests(unittest.TestCase):
    def test_held_in_offhand_with_one_hand_weapon_has_no_static_trigger(self):
        # Observed Arndor example: main inventory type 21, off inventory type 23.
        # The synthetic preconditions must NOT be presented as runtime proof.
        self.assertEqual(
            model_core_offhand_decision(
                "holdable", mainhand_subclass="one_hand_mace",
                can_dual_wield=False, can_titan_grip=False,
                is_two_hand_used=False
            ),
            "RETAIN_IN_CORE_MODEL_ONLY",
        )

    def test_shield_with_one_hand_weapon_has_no_static_trigger(self):
        self.assertEqual(
            model_core_offhand_decision("shield"),
            "RETAIN_IN_CORE_MODEL_ONLY",
        )

    def test_staff_or_polearm_forces_nonweapon_offhand_relocation(self):
        for subclass in ("staff", "polearm", "fishing_pole"):
            with self.subTest(subclass=subclass):
                self.assertEqual(
                    model_core_offhand_decision(
                        "holdable", mainhand_subclass=subclass
                    ), "CORE_RELOCATION_TRIGGER"
                )

    def test_offhand_weapon_without_dual_wield_forces_relocation(self):
        for subtype in ("weapon", "offhand_weapon"):
            self.assertEqual(
                model_core_offhand_decision(subtype, can_dual_wield=False),
                "CORE_RELOCATION_TRIGGER",
            )

    def test_lost_dual_wield_changes_core_decision(self):
        self.assertEqual(
            model_core_offhand_decision("offhand_weapon", can_dual_wield=True),
            "RETAIN_IN_CORE_MODEL_ONLY",
        )
        self.assertEqual(
            model_core_offhand_decision("offhand_weapon", can_dual_wield=False),
            "CORE_RELOCATION_TRIGGER",
        )

    def test_two_handed_and_force_paths_remain_risky(self):
        self.assertEqual(
            model_core_offhand_decision("two_hand_weapon"),
            "CORE_RELOCATION_TRIGGER",
        )
        self.assertEqual(
            model_core_offhand_decision("holdable", is_two_hand_used=True),
            "CORE_RELOCATION_TRIGGER",
        )
        self.assertEqual(
            model_core_offhand_decision("holdable", force=True),
            "CORE_RELOCATION_TRIGGER",
        )

    def test_absent_offhand_is_not_preservation_certification(self):
        self.assertEqual(model_core_offhand_decision(None), "NO_OFFHAND")

    def test_all_occupied_alt_bot_offhands_still_fail_closed(self):
        self.assertIn("if (!randomBot)", READINESS)
        self.assertIn("INVENTORY_SLOT_BAG_0, EQUIPMENT_SLOT_OFFHAND", READINESS)
        self.assertIn("Alt Bot NT1 Apply blocked: an offhand item is", READINESS)
        self.assertIn("Talent reset could move or MAIL it", READINESS)
        self.assertLess(
            READINESS.index("EQUIPMENT_SLOT_OFFHAND"),
            READINESS.index("bot->GetPet() != nullptr"),
        )

    def test_active_pet_guard_and_read_only_mode_remain(self):
        self.assertIn("bot->GetPet() != nullptr", READINESS)
        self.assertIn("Alt Bot NT1 Apply blocked: the bot has an active", READINESS)
        self.assertIn("IsReadOnlyAccessMode()", APPLY)
        self.assertLess(
            APPLY.index("if (IsReadOnlyAccessMode())"),
            APPLY.index("bot->resetTalents(true)"),
        )

    def test_one_preflight_and_both_possible_resets_still_present(self):
        self.assertLess(
            APPLY.index("CheckApplyReadiness(issuer, bot, requested, error, &snapshot,"),
            APPLY.index("bot->resetTalents(true)"),
        )
        self.assertEqual(APPLY.count("bot->resetTalents(true);"), 2)
        self.assertLess(
            APPLY.index("if (LearnValidated(bot, requested, error))"),
            APPLY.rindex("bot->resetTalents(true);"),
        )

    def test_importer_does_not_automatically_change_gear(self):
        code = re.sub(r"//[^\n]*", "", APPLY)
        for function in (
            "AutoGear", "DestroyEquippedGear", "EquipNewItem",
            "MoveItemFromInventory", "StoreItem", "AutoUnequipOffhandIfNeed",
            "MailDraft", "DestroyItem", "RemoveItem"
        ):
            self.assertNotRegex(code, r"\b" + function + r"\s*\(")

    def test_read_only_risk_report_never_grants_an_exception(self):
        self.assertIn("INVTYPE_WEAPONOFFHAND", AUDIT)
        self.assertIn("INVTYPE_WEAPON", AUDIT)
        self.assertIn("INVTYPE_2HWEAPON", AUDIT)
        self.assertIn("no current CORE relocation", AUDIT)
        self.assertIn("STILL BLOCKED; hooks and post-reset state unverified", AUDIT)
        self.assertIn("NO spec switch performed", AUDIT)
        self.assertNotRegex(
            re.sub(r"//[^\n]*", "", AUDIT),
            r"\b(?:resetTalents|AutoUnequipOffhandIfNeed|SaveToDB|"
            r"DirectExecute|EquipNewItem|LearnTalent)\s*\(",
        )

    def test_talent_completion_import_hook_clears_pending_not_gear(self):
        self.assertIn("NaxxramasBotTalentImport::IsImportOperation(bot)", RESET_HOOK)
        self.assertIn("N::Pending.erase(key)", RESET_HOOK)
        self.assertIn("N::Intents.erase(key)", RESET_HOOK)
        before_normal = RESET_HOOK.split("        if (!bot || !noCost ||", 1)[0]
        self.assertIn("return;", before_normal)
        for name in (
            "AutoGear", "DestroyEquippedGear", "AutoUnequipOffhandIfNeed",
            "EquipNewItem", "DestroyItem", "RemoveItem"
        ):
            self.assertNotRegex(RESET_HOOK, r"\b" + name + r"\s*\(")

    def test_talent_completion_prelearn_hook_stays_scoped(self):
        self.assertIn("NaxxramasBotTalentImport::IsImportOperation(bot)", COMPLETION)
        self.assertIn("PLAYERHOOK_ON_TALENTS_RESET", COMPLETION)
        self.assertIn("PLAYERHOOK_CAN_LEARN_TALENT", LIMITS)
        self.assertIn("NaxxramasBotTalentImport::IsImportOffCentreCapstone", LIMITS)

    def test_importer_has_no_unreviewed_zero_point_fast_path(self):
        # A zero-point exception must be a separate, reviewed change.
        self.assertIn("ImportScope const scope(bot);", APPLY)
        self.assertIn("bot->resetTalents(true);", APPLY)
        self.assertNotIn("ALREADY_MATCHES", APPLY)
        self.assertNotIn("ZERO_TALENT_SAFE_APPLY", APPLY)

    def test_live_access_and_issuer_checks_are_unchanged(self):
        self.assertIn("CanApplyToAltBot(issuer, error)", READINESS)
        self.assertIn("CheckPlayerProgressionEra(issuer, requested.Progression, error)", READINESS)
        self.assertIn("sRandomPlayerbotMgr.IsRandomBot(bot)", READINESS)
        self.assertIn("NaxxramasCore.BotTalentImport.AccessMode = 0", CONF)
        self.assertIn('{"safetypreview", HandleSafetyPreview', NT1)
        self.assertIn('{"repairpreview", HandleRepairPreview', NT1)


if __name__ == "__main__":
    unittest.main()
