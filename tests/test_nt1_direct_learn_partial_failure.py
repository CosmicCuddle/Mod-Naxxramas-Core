"""Source-contract negative tests; no talent, gear, database or server writes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_nt1_direct_learn_partial_failure import (  # noqa: E402
    SourceContractError, check_direct_learn_risk, model_sequential_learn,
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
