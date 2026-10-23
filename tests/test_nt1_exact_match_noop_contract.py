"""Source-order guardrails for the narrow, unreleased EXACT Alt Bot no-op.

The existing C++ comparator is also exercised by a separate compiled C++17
fixture. These source tests cannot establish safety of a DIFFERENT-build
talent reset, other modules, or gameplay runtime; release requires a real
pinned-core compile/link and disposable-bot acceptance.
"""
from pathlib import Path
import re
import unittest

CPP = (
    Path(__file__).resolve().parents[1] /
    "src" / "Systems" / "BotTalentImport.cpp"
).read_text(encoding="utf-8")


def region(start, end):
    a = CPP.index(start)
    b = CPP.index(end, a + len(start))
    return CPP[a:b]


READINESS = region("    bool CheckApplyReadiness(", "    bool ApplyValidated(")
APPLY = region("    bool ApplyValidated(", "    bool ReadArguments(")
EXACT = region("    ActiveTalentMatch InspectActiveTalentMatch(", "    void PrintActiveTalentMatch(")
PREVIEW = region("    void PrintPreview(", "\n}\n\nclass NaxxramasBotTalentImportCommands")
REPAIR = region("    void PrintAltBotRepairPreview(", "    void PrintPreview(")
HANDLE = region("    static bool HandleApply(", "\n};\n\nvoid AddBotTalentImportScripts()")


class ExactAltBotNoOpContract(unittest.TestCase):
    def test_active_full_rank_comparator_is_the_only_exact_oracle(self):
        self.assertIn(
            "return InspectActiveTalentMatch(bot, requested).Status ==", EXACT
        )
        self.assertIn("ActiveTalentMatchStatus::Exact", EXACT)
        self.assertIn("report.ObservedTalents", EXACT)
        self.assertIn("bot->GetFreeTalentPoints()", EXACT)
        self.assertIn("observedPoints + bot->GetFreeTalentPoints()", EXACT)
        self.assertIn("requested.Class != currentClass", EXACT)
        self.assertIn("multiple active ranks for one talent", EXACT)

    def test_only_alt_bot_can_consider_no_op(self):
        self.assertIn("bool const verifiedNoOp = !randomBot && exactNoOpEligible &&", READINESS)
        self.assertIn("HasVerifiedExactActiveBuild(bot, requested)", READINESS)
        self.assertIn("if (!randomBot && !verifiedNoOp)", READINESS)
        self.assertNotIn("sRandomPlayerbotMgr.IsRandomBot", EXACT)

    def test_all_human_allowlist_and_era_checks_precede_no_op(self):
        exact = READINESS.index("bool const verifiedNoOp =")
        for required in (
            "!Enabled()",
            "!issuer || !issuer->GetSession()",
            "CanControlBot(",
            "CanApplyToAltBot(issuer, error)",
            "CheckPlayerProgressionEra(issuer, requested.Progression, error)",
            "requested.Spent < requested.Available",
            "bot->IsInCombat() || !bot->IsAlive()",
            "EncodeExisting(bot, requested.Progression)",
            "ParseCode(previous, bot, snapshot, snapshotError)",
            "mod_naxxramas_bot_talent_import",
        ):
            with self.subTest(required=required):
                self.assertLess(READINESS.index(required), exact)

    def test_indeterminate_never_bypasses_original_guards(self):
        self.assertIn("ActiveTalentMatchStatus::Exact", EXACT)
        self.assertIn("if (!randomBot && !verifiedNoOp)", READINESS)
        self.assertIn("EQUIPMENT_SLOT_OFFHAND", READINESS)
        self.assertIn("bot->GetPet() != nullptr", READINESS)
        self.assertLess(
            READINESS.index("bool const verifiedNoOp ="),
            READINESS.index("if (!randomBot && !verifiedNoOp)"),
        )

    def test_no_op_flag_is_fail_closed_on_early_errors(self):
        self.assertIn("if (exactNoOpEligible)", READINESS)
        self.assertIn("*exactNoOpEligible = false", READINESS)
        self.assertLess(
            READINESS.index("*exactNoOpEligible = false"),
            READINESS.index("if (!Enabled())"),
        )
        self.assertLess(
            READINESS.index("if (IsReadOnlyAccessMode())"),
            READINESS.index("*exactNoOpEligible = verifiedNoOp"),
        )

    def test_mode_3_and_4_never_return_no_op_success(self):
        self.assertLess(
            APPLY.index("if (IsReadOnlyAccessMode())"),
            APPLY.index("CheckApplyReadiness("),
        )
        self.assertLess(
            READINESS.index("if (IsReadOnlyAccessMode())"),
            READINESS.index("*exactNoOpEligible = verifiedNoOp"),
        )

    def test_true_no_op_returns_before_any_mutating_operation(self):
        early = APPLY.index("if (verifiedNoOp)")
        done = APPLY.index("return true;", early)
        reset = APPLY.index("bot->resetTalents(true)")
        self.assertLess(early, done)
        self.assertLess(done, reset)
        for symbol in (
            "ImportScope const scope(bot)",
            "LearnValidated(bot, requested, error)",
            "CharacterDatabase.DirectExecute(",
            "bot->SaveToDB(false, false)",
            "bot->resetTalents(true)",
            "bot->SendTalentsInfoData(false)",
        ):
            with self.subTest(symbol=symbol):
                self.assertGreater(APPLY.index(symbol), done)
        self.assertIn("if (unchanged)", APPLY[early:done])
        self.assertIn("*unchanged = true", APPLY[early:done])

    def test_requested_no_op_state_resets_between_calls(self):
        self.assertIn("if (unchanged)", APPLY)
        self.assertIn("*unchanged = false", APPLY)
        self.assertLess(
            APPLY.index("*unchanged = false"),
            APPLY.index("if (IsReadOnlyAccessMode())"),
        )

    def test_random_bot_retains_original_reset_failure_path(self):
        # A DIFFERENT Alt Bot is stopped twice before this legacy branch.
        classification = APPLY.index("bool const randomBot = sRandomPlayerbotMgr.IsRandomBot(bot);")
        gate = APPLY.index("if (!randomBot)", classification)
        self.assertLess(gate, APPLY.index("ImportScope const scope(bot)"))
        self.assertIn("return false;", APPLY[gate:APPLY.index("ImportScope const scope(bot)")])
        self.assertEqual(APPLY.count("bot->resetTalents(true);"), 2)
        self.assertIn("if (LearnValidated(bot, requested, error))", APPLY)
        self.assertIn("ROLLBACK FAILED:", APPLY)
        self.assertLess(
            APPLY.index("if (verifiedNoOp)"),
            APPLY.index("ImportScope const scope(bot)"),
        )

    def test_no_op_never_reported_as_applied(self):
        self.assertIn("bool unchanged = false", HANDLE)
        self.assertIn("&unchanged", HANDLE)
        self.assertIn("if (unchanged)", HANDLE)
        self.assertIn("NT1 ALREADY MATCHES:", HANDLE)
        self.assertIn("NO CHANGES MADE;", HANDLE)
        self.assertLess(
            HANDLE.index("if (unchanged)"),
            HANDLE.index("NT1 build applied to"),
        )
        branch = HANDLE[HANDLE.index("if (unchanged)"):HANDLE.index("NT1 build applied to")]
        self.assertIn("return true;", branch)

    def test_preview_reports_distinct_no_op_outcome(self):
        self.assertIn("NT1 PREFLIGHT ALREADY MATCHES:", PREVIEW)
        self.assertIn("NT1 ALT REPAIR ALREADY MATCHES:", REPAIR)
        self.assertIn("CheckApplyReadiness(", PREVIEW)
        self.assertIn("CheckApplyReadiness(", REPAIR)

    def test_does_not_add_gear_mutating_primitive(self):
        # Source-level limit: nested Player and script hook effects still need
        # a full call-graph review for any DIFFERENT build.
        for line in (
            "bot->AutoUnequipOffhandIfNeed(",
            "bot->EquipNewItem(",
            "bot->MoveItemFromInventory(",
            "bot->DestroyItem(",
            "bot->SetCanDualWield(",
        ):
            self.assertNotIn(line, APPLY)


if __name__ == "__main__":
    unittest.main()
