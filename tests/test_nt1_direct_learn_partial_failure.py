"""Source-contract negative tests; no talent, gear, database or server writes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_nt1_direct_learn_partial_failure import (  # noqa: E402
    SourceContractError, check_direct_learn_risk, model_sequential_learn,
    git_blob_oid, verify_pinned_player_cpp_blob, PINNED_PLAYER_CPP_BLOBS,
)

CORE_FIXTURE = """
void Player::LearnTalent(uint32 talentId, uint32 talentRank, bool command /*= false*/)
{
    uint32 CurTalentPoints = GetFreeTalentPoints();
    if (!sScriptMgr->OnPlayerCanLearnTalent(this, talentInfo, talentRank))
        return;
    TalentTabEntry const* talentTabInfo = sTalentTabStore.LookupEntry(talentInfo->TalentTab);
    if (CurTalentPoints < talentPointsChange)
        return;
    learnSpell(spellId);
    learned = true;
    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);
    SetFreeTalentPoints(CurTalentPoints - talentPointsChange);
    sScriptMgr->OnPlayerLearnTalents(this, talentId, talentRank, spellId);
}
"""

IMPORT_FIXTURE = """
bool LearnValidated(Player* bot, ValidatedBuild const& plan,
        std::string& error)
{
    for (TalentSelection const& selection : plan.Ordered)
    {
        bot->LearnTalent(selection.Id, selection.Rank - 1);
        if (!bot->HasTalent(spellId, bot->GetActiveSpec()))
            return false;
    }
    return true;
}
"""


class NT1DirectLearnHazard(unittest.TestCase):
    def test_proves_risk_not_safety(self):
        r = check_direct_learn_risk(CORE_FIXTURE, IMPORT_FIXTURE)
        self.assertTrue(r["core_can_veto_each_selection"])
        self.assertTrue(r["nt1_mutates_before_checking_next_selection"])
        self.assertFalse(r["safe_gear_inert_changed_build_apply"])

    def test_veto_on_first_is_noop_in_model(self):
        ok, spells = model_sequential_learn((100, 200, 300), 0)
        self.assertFalse(ok)
        self.assertEqual(spells, ())

    def test_veto_on_second_leaves_first_committed(self):
        ok, spells = model_sequential_learn((100, 200, 300), 1)
        self.assertFalse(ok)
        self.assertEqual(spells, (100,))

    def test_veto_on_third_leaves_two_committed(self):
        ok, spells = model_sequential_learn((100, 200, 300), 2)
        self.assertFalse(ok)
        self.assertEqual(spells, (100, 200))

    def test_no_veto_can_complete_but_does_not_prove_real_apply(self):
        ok, spells = model_sequential_learn((100, 200, 300), None)
        self.assertTrue(ok)
        self.assertEqual(spells, (100, 200, 300))

    def test_missing_script_hook_fails_closed(self):
        with self.assertRaises(SourceContractError):
            check_direct_learn_risk(
                CORE_FIXTURE.replace("OnPlayerCanLearnTalent", "OtherHook"),
                IMPORT_FIXTURE,
            )

    def test_changed_core_addtalent_result_fails_closed(self):
        with self.assertRaises(SourceContractError):
            check_direct_learn_risk(
                CORE_FIXTURE.replace(
                    "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
                    "if (!addTalent(spellId, GetActiveSpecMask(), currentTalentRank)) return;",
                ),
                IMPORT_FIXTURE,
            )

    def test_bool_const_addtalent_result_fails_closed(self):
        # CS02 peer review found the original checker missed this form.
        with self.assertRaises(SourceContractError):
            check_direct_learn_risk(
                CORE_FIXTURE.replace(
                    "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
                    "bool const added = addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
                ),
                IMPORT_FIXTURE,
            )

    def test_auto_addtalent_result_fails_closed(self):
        with self.assertRaises(SourceContractError):
            check_direct_learn_risk(
                CORE_FIXTURE.replace(
                    "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
                    "auto result = addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
                ),
                IMPORT_FIXTURE,
            )

    def test_every_nonstandalone_addtalent_form_fails_closed(self):
        # Any unfamiliar invocation must force a human source review.
        original = "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);"
        variants = (
            "bool added{addTalent(spellId, GetActiveSpecMask(), currentTalentRank)};",
            "auto result{addTalent(spellId, GetActiveSpecMask(), currentTalentRank)};",
            "added = addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
            "return addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
            "ASSERT(addTalent(spellId, GetActiveSpecMask(), currentTalentRank));",
            "this->addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
            "Player::addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
            "call(addTalent(spellId, GetActiveSpecMask(), currentTalentRank));",
            "addTalent(spellId, GetActiveSpecMask(), currentTalentRank); extraCall();",
            "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);\n"
            "    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises(SourceContractError):
                    check_direct_learn_risk(
                        CORE_FIXTURE.replace(original, variant),
                        IMPORT_FIXTURE,
                    )

    def test_preceding_line_nonstandalone_addtalent_fails_closed(self):
        # CS02 exact-head review found that checking only the call line
        # missed assignments, return and unbraced control flow above it.
        original = "    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);"
        variants = (
            "    bool added =\n" + original,
            "    added =\n" + original,
            "    return\n" + original,
            "    (void)\n" + original,
            "    if (canLearn)\n" + original,
            "    if (canLearn)\n        " + original.strip(),
            "    doSomething(1),\n" + original,
            "    SomeWrapper(\n" + original,
            "    bool added{\n" + original,
        )
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises(SourceContractError):
                    check_direct_learn_risk(
                        CORE_FIXTURE.replace(original, variant),
                        IMPORT_FIXTURE,
                    )

    def test_braced_control_flow_and_lambda_addtalent_fail_closed(self):
        # CS02 found that a preceding '{' passed the old line-boundary
        # check; function_body() returns LearnTalent's braces EXCLUDED.
        # The pinned addTalent statement must be at brace nesting depth 0.
        original = "    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);"
        variants = (
            "    if (canLearn) {\n        " + original.strip() + "\n    }",
            "    while (shouldApply) {\n        " + original.strip() + "\n    }",
            "    auto wrapper = [&]() {\n        " + original.strip() + "\n    };",
            "    if (canLearn)\n    {\n        " + original.strip() + "\n    }",
        )
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises(SourceContractError):
                    check_direct_learn_risk(
                        CORE_FIXTURE.replace(original, variant), IMPORT_FIXTURE)

    def test_balanced_control_blocks_before_addtalent_fail_closed(self):
        # A balanced block can return or otherwise alter control flow while
        # leaving brace nesting zero before the original mutation call.
        original = "    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);"
        variants = (
            "    if (blocked) { return; }\n" + original,
            "    if (blocked)\n    {\n        return;\n    }\n" + original,
            "    while (blocked) { break; }\n" + original,
            "    {\n        doSomething();\n    }\n" + original,
        )
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises(SourceContractError):
                    check_direct_learn_risk(
                        CORE_FIXTURE.replace(original, variant),
                        IMPORT_FIXTURE,
                    )

    def test_exact_pinned_player_cpp_blob_guard_rejects_control_drift(self):
        # The lexical checker can still accept this unbraced conditional.
        # The production CLI must fingerprint the entire pinned Player.cpp
        # before applying the narrower source contract to the risk.
        original = "    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);"
        modified = CORE_FIXTURE.replace(
            original, "    if (blocked) return;\n" + original)
        self.assertTrue(check_direct_learn_risk(modified, IMPORT_FIXTURE))
        for core_sha in PINNED_PLAYER_CPP_BLOBS:
            with self.subTest(core_sha=core_sha):
                with self.assertRaises(SourceContractError):
                    verify_pinned_player_cpp_blob(modified, core_sha)
                with self.assertRaises(SourceContractError):
                    verify_pinned_player_cpp_blob(CORE_FIXTURE, core_sha)

    def test_full_blob_fingerprint_changes_on_any_source_mutation(self):
        original = git_blob_oid(CORE_FIXTURE)
        for variant in (
            CORE_FIXTURE + "// unrelated comment\n",
            CORE_FIXTURE.replace("    learned = true;", "    learned = false;"),
            CORE_FIXTURE.replace(
                "    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
                "    goto missing_label;\n    "
                "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);"),
            CORE_FIXTURE.replace(
                "    addTalent(spellId, GetActiveSpecMask(), currentTalentRank);",
                "    throw 1;\n    "
                "addTalent(spellId, GetActiveSpecMask(), currentTalentRank);"),
        ):
            with self.subTest(variant=variant[-65:]):
                self.assertNotEqual(git_blob_oid(variant), original)

    def test_unknown_reference_denied_before_source_contract(self):
        with self.assertRaises(SourceContractError):
            verify_pinned_player_cpp_blob(CORE_FIXTURE, "unreviewed-or-mixed-pin")

    def test_changed_importer_sequence_fails_closed(self):
        with self.assertRaises(SourceContractError):
            check_direct_learn_risk(
                CORE_FIXTURE, IMPORT_FIXTURE.replace("bot->LearnTalent(", "bot->OtherCall("),
            )

    def test_missing_or_ambiguous_core_symbol_fails_closed(self):
        with self.assertRaises(SourceContractError):
            check_direct_learn_risk("", IMPORT_FIXTURE)
        with self.assertRaises(SourceContractError):
            check_direct_learn_risk(CORE_FIXTURE + CORE_FIXTURE, IMPORT_FIXTURE)


if __name__ == "__main__":
    unittest.main()
