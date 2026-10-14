"""Source guardrails for the owner's proposed zero-gear-mutation invariant.

Passing these tests DOES NOT establish gear-inert different-build Apply.
The pinned core's resetTalents still calls AutoUnequipOffhandIfNeed, which
can move and even mail equipment. This contract prevents accidental
loosening of the current fail-closed restrictions during further R&D.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CPP = (ROOT / "src/Systems/BotTalentImport.cpp").read_text(encoding="utf-8")
CONFIG = (ROOT / "conf/mod_naxxramas_core.conf.dist").read_text(encoding="utf-8")
POLICY = (ROOT / "docs/NT1-ALT-BOT-ZERO-GEAR-MUTATION-CONTRACT.md").read_text(
    encoding="utf-8"
)
PLAN = (
    ROOT / "docs/NT1-ZERO-GEAR-MUTATION-IMPLEMENTATION-PLAN-2026-10-13.md"
).read_text(encoding="utf-8")

READINESS = CPP.split("    bool CheckApplyReadiness(", 1)[1].split(
    "    bool ApplyValidated(", 1
)[0]
APPLY = CPP.split("    bool ApplyValidated(", 1)[1].split(
    "    bool ReadArguments(", 1
)[0]


class ZeroGearMutationPolicyGuardrails(unittest.TestCase):
    def test_human_character_allowlist_remains_fail_closed(self):
        self.assertIn(
            'NaxxramasCore.BotTalentImport.AltBotAllowedPlayers = ""', CONFIG
        )
        self.assertIn(
            '"NaxxramasCore.BotTalentImport.AltBotAllowedPlayers", ""', CPP
        )
        self.assertIn("NormalizeAllowedCharacterName", CPP)
        self.assertIn("!CanApplyToAltBot(issuer, error)", READINESS)
        self.assertLess(
            READINESS.index("!CanApplyToAltBot(issuer, error)"),
            READINESS.index("EQUIPMENT_SLOT_OFFHAND"),
        )

    def test_read_only_access_modes_cannot_apply(self):
        self.assertIn("if (IsReadOnlyAccessMode())", APPLY)
        self.assertLess(
            APPLY.index("if (IsReadOnlyAccessMode())"),
            APPLY.index("bot->resetTalents(true)"),
        )
        self.assertIn("BotTalentImport.AccessMode = 0", CONFIG)

    def test_occupied_offhand_blocks_before_reset(self):
        self.assertIn("EQUIPMENT_SLOT_OFFHAND", READINESS)
        self.assertIn(
            "Alt Bot NT1 Apply blocked: an offhand item is", READINESS
        )
        self.assertIn("No talents or equipment changed.", READINESS)
        self.assertIn(
            "if (!CheckApplyReadiness(issuer, bot, requested, error, &snapshot,",
            APPLY,
        )
        self.assertLess(
            APPLY.index("CheckApplyReadiness("),
            APPLY.index("bot->resetTalents(true)"),
        )

    def test_active_pet_stays_independently_blocked(self):
        self.assertIn("bot->GetPet() != nullptr", READINESS)
        self.assertIn(
            "Alt Bot NT1 Apply blocked: the bot has an active", READINESS
        )

    def test_no_explicit_equipment_mutator_added_to_apply(self):
        # This protects NT1's own function body, not nested core/hook effects.
        # A source-line string check can never replace whole-call-graph proof.
        without_comments = re.sub(
            r"//[^\n]*|/\*[\s\S]*?\*/", "", APPLY
        )
        forbidden = (
            "EquipItem", "EquipNewItem", "DestroyItem", "RemoveItem",
            "StoreItem", "MoveItemFromInventory", "MailDraft",
            "AutoUnequipOffhandIfNeed", "SwapItem", "PlayerbotFactory",
            "UpdateEquipment", "SetCanTitanGrip", "SetCanDualWield",
        )
        for symbol in forbidden:
            with self.subTest(symbol=symbol):
                self.assertNotRegex(
                    without_comments,
                    rf"\b{symbol}\s*\(",
                )

    def test_exact_match_only_adds_early_return_before_resets(self):
        self.assertIn("InspectActiveTalentMatch(", CPP)
        self.assertIn("HasVerifiedExactActiveBuild(bot, requested)", READINESS)
        self.assertIn("if (!randomBot && !verifiedNoOp)", READINESS)
        self.assertNotIn("PrintActiveTalentMatch(", APPLY)
        self.assertLess(
            APPLY.index("if (verifiedNoOp)"),
            APPLY.index("ImportScope const scope(bot)"),
        )
        self.assertLess(
            APPLY.index("if (verifiedNoOp)"),
            APPLY.index("bot->resetTalents(true)"),
        )
        # The different-build fallback remains non-transactional.
        self.assertEqual(
            APPLY.count("bot->resetTalents(true)"), 2
        )

    def test_policy_cannot_be_overridden_by_a_gear_config_toggle(self):
        for raw in (CONFIG, CPP):
            self.assertNotIn(
                "NaxxramasCore.BotTalentImport.AllowGearMutation", raw
            )
            self.assertNotIn(
                "NaxxramasCore.BotTalentImport.AllowEquipmentChanges", raw
            )
        self.assertIn("No exceptions", POLICY)
        self.assertIn("without a disabling configuration setting", PLAN)
        self.assertIn("no functioning gear-inert different-build talent-changing implementation exists", PLAN.lower())


if __name__ == "__main__":
    unittest.main()
