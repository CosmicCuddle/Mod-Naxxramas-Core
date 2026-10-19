"""Review-only, source-level model of a proposed human Hunter IP rank handoff.

No AzerothCore/IP/Playerbots source is executed or changed.
A successful model test is NOT C++ compile, live behavior or approval.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "proposals/hunter-player-ip-autocast-legal-rank-review-only.patch"


def model_transfer(known, wipe, keep, legal_ids, autocastable, bar_ids,
                   same_pet=True, being_loaded=False, learn_succeeds=True,
                   same_rank_chain=True):
    """Model guarded one-old-rank transfer, never all IP family spell grants."""
    if (not keep or keep not in wipe or keep in known or
            keep not in legal_ids or keep not in autocastable):
        return None
    # Any second known old spell in the wipe list is ambiguous, even if
    # it is passive/unrecognized: do NOT silently exclude it from the count.
    existing_old = [i for i in wipe if i != keep and i in known]
    if len(existing_old) != 1:
        return None
    old_id = existing_old[0]
    old_state = known[old_id]
    if (old_id not in autocastable or
            not isinstance(old_state, bool) or not same_rank_chain):
        return None
    if not (learn_succeeds and same_pet and not being_loaded and
            keep in bar_ids):
        return None
    return old_state


class HumanHunterIPReviewProposalTests(unittest.TestCase):
    def test_previous_explicit_on_survives_one_legal_rank_replacement(self):
        self.assertIs(model_transfer({101: True}, [101, 102], 102,
                                    {102}, {101, 102}, {102}), True)

    def test_previous_explicit_off_is_preserved_not_forced_on(self):
        self.assertIs(model_transfer({101: False}, [101, 102], 102,
                                    {102}, {101, 102}, {102}), False)

    def test_existing_permitted_rank_must_remain_untouched(self):
        self.assertIsNone(model_transfer({101: True, 102: False}, [101, 102],
                                         102, {102}, {101, 102}, {102}))

    def test_no_legal_rank_or_no_training_is_never_restored(self):
        self.assertIsNone(model_transfer({101: True}, [101, 102], 0,
                                         set(), {101, 102}, {102}))
        self.assertIsNone(model_transfer({101: True}, [101, 102], 102,
                                         set(), {101, 102}, {102}))

    def test_ambiguous_two_old_rank_states_fail_closed(self):
        self.assertIsNone(model_transfer({100: True, 101: False},
                                         [100, 101, 102], 102, {102},
                                         {100, 101, 102}, {102}))

    def test_spell_must_be_autocastable_before_and_after(self):
        self.assertIsNone(model_transfer({101: True}, [101, 102], 102,
                                         {102}, {101}, {102}))
        self.assertIsNone(model_transfer({101: True}, [101, 102], 102,
                                         {102}, {102}, {102}))

    def test_mixed_wipe_ids_do_not_cross_spell_rank_chains(self):
        self.assertIsNone(model_transfer({101: True}, [101, 102], 102,
                                         {102}, {101, 102}, {102},
                                         same_rank_chain=False))

    def test_unlisted_keepid_cannot_receive_old_choice(self):
        self.assertIsNone(model_transfer({101: True}, [101], 102,
                                         {102}, {101, 102}, {102}))

    def test_unknown_second_known_spell_makes_old_state_ambiguous(self):
        self.assertIsNone(model_transfer({100: True, 101: 7},
                                         [100, 101, 102], 102, {102},
                                         {100, 102}, {102}))

    def test_invalid_old_state_cannot_masquerade_as_boolean_off(self):
        self.assertIsNone(model_transfer({101: 0}, [101, 102], 102,
                                         {102}, {101, 102}, {102}))

    def test_pet_swap_and_async_loading_fail_closed(self):
        self.assertIsNone(model_transfer({101: True}, [101, 102], 102,
                                         {102}, {101, 102}, {102},
                                         same_pet=False))
        self.assertIsNone(model_transfer({101: True}, [101, 102], 102,
                                         {102}, {101, 102}, {102},
                                         being_loaded=True))

    def test_unlearned_replacement_and_missing_bar_fail_closed(self):
        self.assertIsNone(model_transfer({101: True}, [101, 102], 102,
                                         {102}, {101, 102}, set()))
        self.assertIsNone(model_transfer({101: True}, [101, 102], 102,
                                         {102}, {101, 102}, {102},
                                         learn_succeeds=False))

    def test_review_diff_has_only_one_ip_file_and_existing_api_patterns(self):
        patch = PATCH.read_text(encoding="utf-8")
        self.assertEqual(patch.count("diff --git "), 1)
        self.assertIn("a/src/IndividualProgressionSpells.cpp", patch)
        self.assertIn("b/src/IndividualProgressionSpells.cpp", patch)
        for token in (
            "keepId && !pet->HasSpell(keepId)",
            "presentOldRanks == 1 && eligibleOldRanks == 1",
            "oldInfo->IsDifferentRankOf(keepInfo)",
            "keepIdInWipeList",
            "player->GetPet() == pet",
            "pet->getPetType() == HUNTER_PET",
            "!pet->isBeingLoaded()",
            "oldAutocast >= 0",
            "keepInfo->IsAutocastable()",
            "barHasKeepSpell",
            "pet->ToggleAutocast(keepInfo, enabled)",
            "charm->SetSpellAutocast(keepInfo, enabled)",
            "player->PetSpellInitialize()",
        ):
            self.assertIn(token, patch)
        # The proposal itself should not add persistence or automated
        # retransmission/always-on loops. Existing IP unlearn/learn remains.
        for prohibited in ("CharacterDatabase.Execute", "CharacterDatabase.Commit",
                           "UPDATE pet_spell", "INSERT INTO pet_spell",
                           "PlayerbotAI", "m_Events.AddEvent("):
            self.assertNotIn("+" + prohibited, patch)


if __name__ == "__main__":
    unittest.main()
