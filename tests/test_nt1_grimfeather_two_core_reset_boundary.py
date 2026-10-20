"""No-worldserver, fail-closed contract tests for two-core NT1 risk checker."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_nt1_grimfeather_two_core_reset_boundary import (  # noqa: E402
    SourceContractError, function_body, verify_source
)


PLAYER_H = """
bool resetTalents(bool noResetCost = false);
bool addTalent(uint32 spellId, uint8 addSpecMask, uint8 oldTalentRank);
void _removeTalent(PlayerTalentMap::iterator& itr, uint8 specMask);
uint32 m_usedTalentCount;
"""

PLAYER_CPP = """
bool Player::resetTalents(bool noResetCost)
{
    sScriptMgr->OnPlayerTalentsReset(this, noResetCost);
    if (m_usedTalentCount == 0) return false;
    m_usedTalentCount = 0;
    RemovePet(nullptr, PET_SAVE_NOT_IN_SLOT, true);
    _removeTalentAurasAndSpells(id);
    AutoUnequipOffhandIfNeed();
    return true;
}
void Player::AutoUnequipOffhandIfNeed(bool force /*= false*/)
{
    if (Item* item = GetItemByPos(0, 0)) {
        CanStoreItem(0);
        RemoveItem(0);
        StoreItem(0);
    } else {
        MoveItemFromInventory(0);
        MailDraft(0).SendMailTo(0);
        CharacterDatabase.CommitTransaction(0);
    }
}
bool Player::addTalent(uint32 spellId, uint8 addSpecMask, uint8 oldTalentRank)
{
    _removeTalent(0);
    m_usedTalentCount += 1;
    return true;
}
void Player::_removeTalent(PlayerTalentMap::iterator& itr, uint8 specMask)
{
    m_talents.erase(itr);
}
"""


class SafetyBoundary(unittest.TestCase):
    def test_original_hazard_is_fully_classified_but_apply_is_not_certified(self):
        result = verify_source(PLAYER_CPP, PLAYER_H)
        self.assertTrue(result["reset_invokes_offhand_relocation"])
        self.assertTrue(result["offhand_can_move_or_mail_item"])
        self.assertFalse(result["different_build_altbot_apply_safe"])

    def test_guard_denies_no_offhand_call(self):
        with self.assertRaises(SourceContractError):
            verify_source(
                PLAYER_CPP.replace("AutoUnequipOffhandIfNeed();", ""),
                PLAYER_H)

    def test_guard_denies_hidden_mail_path(self):
        with self.assertRaises(SourceContractError):
            verify_source(PLAYER_CPP.replace("MailDraft(0)", "OtherMethod(0)"), PLAYER_H)

    def test_guard_denies_missing_reset_hook(self):
        with self.assertRaises(SourceContractError):
            verify_source(
                PLAYER_CPP.replace(
                    "sScriptMgr->OnPlayerTalentsReset(this, noResetCost);", ""),
                PLAYER_H)

    def test_guard_denies_changed_partial_remove_accounting(self):
        with self.assertRaises(SourceContractError):
            verify_source(
                PLAYER_CPP.replace(
                    "m_talents.erase(itr);",
                    "m_talents.erase(itr); m_usedTalentCount -= 1;"),
                PLAYER_H)

    def test_guard_denies_changed_player_header_api(self):
        with self.assertRaises(SourceContractError):
            verify_source(PLAYER_CPP, PLAYER_H.replace("uint32 m_usedTalentCount;", ""))

    def test_parser_denies_missing_or_ambiguous_symbol(self):
        with self.assertRaises(SourceContractError):
            function_body(PLAYER_CPP, "void Player::Unknown()")
        with self.assertRaises(SourceContractError):
            function_body(PLAYER_CPP + PLAYER_CPP, "bool Player::resetTalents(bool noResetCost)")


if __name__ == "__main__":
    unittest.main()
