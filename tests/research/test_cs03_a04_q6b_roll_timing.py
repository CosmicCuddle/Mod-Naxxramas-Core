"""A04 Q6b research witnesses: roll-time vs award-time eligibility (core 8daffda).

Research only. GAP tests show a stock source path that can give an item to
a player the native rule would refuse at award time, or strand a copy.
REF tests show legitimate stock behaviour that any later change must keep.
Nothing here proves the owner's report; that still needs one anonymized
sample (item flags, quest, source, both humans' eligibility, bag or mail).
"""
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from a04_turn_model import Corpse, GroupTurns, try_pickup  # noqa: E402
from a04_roll_model import (  # noqa: E402
    DISENCHANT, GREED, MAIL_DISABLED, MAIL_EVERYWHERE, MAIL_LFG_ONLY, NEED,
    NOT_EMITED_YET, PASS, SLOT_ALLOW_LOOT, SLOT_HIDDEN, SLOT_OWNER,
    SLOT_ROLL_ONGOING, Group, ItemTemplate, LootItem, Player, Quest,
    QuestObjective, can_roll_on_item, loot_view_slot, slot_rolls,
    store_loot_item,
)

ITEM = 9001          # a synthetic quest objective item
OTHER = 9002         # a second objective of the same quest
NEEDED = 1           # the quest needs one copy


def humans(free=16):
    a = Player("A", bag_slots_free=free, quests=[QuestObjective(ITEM, NEEDED)])
    b = Player("B", bag_slots_free=free, quests=[QuestObjective(ITEM, NEEDED)])
    return a, b


def quest_drop(max_count=0, follow=True, ignore=False):
    return LootItem(ItemTemplate(ITEM, max_count, follow, ignore), needs_quest=True)


def same_pull(group, n, max_count=0, follow=True):
    """n corpses from one AoE pull, each with one copy; all rolls start
    together, so admission happens before any award (Group::GroupLoot)."""
    drops = [quest_drop(max_count, follow) for _ in range(n)]
    return drops, [group.start_roll(d) for d in drops]


class RollAdmission(unittest.TestCase):
    def test_ref_quest_bucket_only_rolls_with_follow_loot_rules(self):
        # Group.cpp L1220-L1224: without custom flag 0x4 the quest copy never
        # rolls; it is picked up from the per-player quest slot instead.
        self.assertFalse(slot_rolls(quest_drop(follow=False)))
        self.assertTrue(slot_rolls(quest_drop(follow=True)))

    def test_ref_admission_checks_eligibility_and_max_count(self):
        a, b = humans()
        b.quests[0].incomplete = False                       # B already finished
        group = Group([a, b])
        roll = group.start_roll(quest_drop())
        self.assertEqual(roll.votes, {"A": NOT_EMITED_YET, "B": PASS})
        self.assertEqual([g for g, _ in group.start_roll_sent], ["A"])
        capped = Player("C", inventory={ITEM: 1},
                        quests=[QuestObjective(ITEM, 5)])
        self.assertFalse(can_roll_on_item(quest_drop(max_count=1), capped))

    def test_ref_direct_pickup_rechecks_eligibility(self):
        # Without flag 0x4: A takes one copy, completes the quest, and the
        # second copy is refused by StoreLootItem L13889; B can take it.
        a, b = humans()
        first, second = quest_drop(follow=False), quest_drop(follow=False)
        self.assertTrue(store_loot_item(a, first, via_quest_slot=True))
        self.assertFalse(store_loot_item(a, second, via_quest_slot=True))
        self.assertTrue(store_loot_item(b, second, via_quest_slot=True))
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM)), (1, 1))


class Q6bSamePullRolls(unittest.TestCase):
    def test_ref_single_roll_both_eligible_is_legitimate(self):
        a, b = humans()
        group = Group([a, b])
        roll = group.start_roll(quest_drop())
        group.count_roll_vote(roll, "A", NEED)
        group.count_roll_vote(roll, "B", NEED, rolls={"A": 70, "B": 20})
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM)), (1, 0))

    def test_ref_two_rolls_split_when_b_wins_second(self):
        a, b = humans()
        group = Group([a, b])
        _, (r1, r2) = same_pull(group, 2)
        for r, nums in ((r1, {"A": 90, "B": 10}), (r2, {"A": 10, "B": 90})):
            group.count_roll_vote(r, "A", NEED)
            group.count_roll_vote(r, "B", NEED, rolls=nums)
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM)), (1, 1))

    def test_gap_q6b_surplus_copy_awarded_without_recheck(self):
        # Unlimited max count: A wins both same-pull rolls. The second award
        # happens after A's quest completed, so AllowedForPlayer would now
        # refuse A, but CountTheRoll (L1662) stores it anyway. B, eligible
        # throughout, ends with nothing.
        a, b = humans()
        group = Group([a, b])
        drops, (r1, r2) = same_pull(group, 2, max_count=0)
        for r in (r1, r2):
            group.count_roll_vote(r, "A", NEED)
            if r is r2:
                self.assertFalse(drops[1].allowed_for_player(a))  # award-time rule
                self.assertTrue(drops[1].allowed_for_player(b))
            group.count_roll_vote(r, "B", NEED, rolls={"A": 95, "B": 5})
        self.assertEqual(a.item_count(ITEM), 2)
        self.assertEqual(b.item_count(ITEM), 0)
        self.assertTrue(b.has_quest_for_item(ITEM))

    def test_gap_q6b_greed_branch_has_same_gap(self):
        a, b = humans()
        group = Group([a, b])
        _, (r1, r2) = same_pull(group, 2)
        for r in (r1, r2):
            group.count_roll_vote(r, "A", GREED)
            group.count_roll_vote(r, "B", GREED, rolls={"A": 60, "B": 40})
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM)), (2, 0))

    def test_gap_q6b_max_count_strands_the_copy(self):
        # Max count 1: the second award fails with CANT_CARRY_MORE, which is
        # not INVENTORY_FULL, so it is never mailed (L1672). The slot is
        # unblocked but reserved to A (L1682-L1683): hidden from B
        # (LootMgr L1033-L1037) and refused to B (L13902). A is refused too
        # (quest complete, max count). Nobody can loot it.
        a, b = humans()
        group = Group([a, b], mail_on_full=MAIL_EVERYWHERE)
        drops, (r1, r2) = same_pull(group, 2, max_count=1)
        for r in (r1, r2):
            group.count_roll_vote(r, "A", NEED)
            group.count_roll_vote(r, "B", NEED, rolls={"A": 99, "B": 1})
        stranded = drops[1]
        self.assertEqual(stranded.roll_winner, "A")
        self.assertFalse(stranded.is_blocked)
        self.assertEqual(loot_view_slot(b, stranded, via_quest_slot=False), SLOT_HIDDEN)
        self.assertEqual(loot_view_slot(a, stranded, via_quest_slot=False), SLOT_OWNER)
        self.assertFalse(store_loot_item(b, stranded, via_quest_slot=True))
        self.assertFalse(store_loot_item(a, stranded, via_quest_slot=True))
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM), a.mailbox), (1, 0, []))

    def test_gap_q6_abandon_while_roll_pending(self):
        # Classic Q6: A is admitted, then abandons the quest within 60 s.
        a, b = humans()
        group = Group([a, b])
        roll = group.start_roll(quest_drop())
        a.quests.clear()
        self.assertFalse(roll.item.allowed_for_player(a))
        group.count_roll_vote(roll, "A", NEED)
        group.count_roll_vote(roll, "B", NEED, rolls={"A": 80, "B": 20})
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM)), (1, 0))

    def test_ref_ignore_quest_status_item_is_not_a_gap(self):
        # flagsCustom 0x2: quest status is never checked, so a second copy
        # to A is the item's intended rule, not an eligibility lapse.
        a, b = humans()
        group = Group([a, b])
        drop = LootItem(ItemTemplate(ITEM, 0, True, True), needs_quest=True)
        group.start_roll(drop)
        a.quests[0].incomplete = False
        self.assertTrue(drop.allowed_for_player(a))


class MailOnFull(unittest.TestCase):
    def _full_bags_second_win(self, mail, lfg=False):
        a, b = humans()
        group = Group([a, b], mail_on_full=mail, lfg=lfg)
        drops, (r1, r2) = same_pull(group, 2)
        group.count_roll_vote(r1, "A", NEED)
        group.count_roll_vote(r1, "B", NEED, rolls={"A": 90, "B": 10})
        a.bag_slots_free = 0
        group.count_roll_vote(r2, "A", NEED)
        group.count_roll_vote(r2, "B", NEED, rolls={"A": 90, "B": 10})
        return a, b, drops[1]

    def test_ref_default_config_never_mails(self):
        a, b, drop = self._full_bags_second_win(MAIL_DISABLED)
        self.assertEqual(a.mailbox, [])
        self.assertEqual(drop.roll_winner, "A")              # reserved, not mailed

    def test_gap_mail_everywhere_mails_without_eligibility(self):
        a, b, drop = self._full_bags_second_win(MAIL_EVERYWHERE)
        self.assertEqual(a.mailbox, [ITEM])                   # SendRollWonItemViaMail
        self.assertFalse(drop.allowed_for_player(a))
        self.assertEqual(b.item_count(ITEM), 0)

    def test_ref_lfg_only_mails_only_in_lfg_groups(self):
        a, _, _ = self._full_bags_second_win(MAIL_LFG_ONLY, lfg=False)
        self.assertEqual(a.mailbox, [])
        a, _, _ = self._full_bags_second_win(MAIL_LFG_ONLY, lfg=True)
        self.assertEqual(a.mailbox, [ITEM])


class ForgedOrOutOfBandActions(unittest.TestCase):
    def test_gap_q13_need_vote_overrides_auto_pass(self):
        # B never had the quest: auto-passed and sent no roll window.
        # A Need packet from B is still counted (CountRollVote L1497-L1546),
        # and because the earlier auto-pass is never subtracted, pass + need
        # already equals the number rolling: the roll ends at once and B
        # wins before A has voted. A's later vote finds no roll.
        a = Player("A", quests=[QuestObjective(ITEM, NEEDED)])
        b = Player("B")
        group = Group([a, b])
        roll = group.start_roll(quest_drop())
        self.assertEqual(roll.votes["B"], PASS)
        self.assertNotIn("B", [g for g, _ in group.start_roll_sent])
        self.assertTrue(group.count_roll_vote(roll, "B", NEED, rolls={"B": 1}))
        self.assertFalse(group.count_roll_vote(roll, "A", NEED, rolls={"A": 100}))
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM)), (0, 1))

    def test_gap_q15_quest_slot_pickup_during_roll_then_roll_awards_again(self):
        # Flag-0x4 quest copy with a pending roll: the honest window shows
        # ROLL_ONGOING, but StoreLootItem skips is_blocked for quest slots
        # (L13895). A forged pickup by B succeeds; CountTheRoll does not
        # check is_looted, so A is also given a copy: one drop, two items.
        a, b = humans()
        group = Group([a, b])
        drop = quest_drop()
        roll = group.start_roll(drop)
        self.assertEqual(loot_view_slot(b, drop, via_quest_slot=True), SLOT_ROLL_ONGOING)
        self.assertTrue(store_loot_item(b, drop, via_quest_slot=True))
        group.count_roll_vote(roll, "A", NEED)
        group.count_roll_vote(roll, "B", PASS, rolls={"A": 50})
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM)), (1, 1))

    def test_ref_normal_bucket_pickup_is_blocked_during_roll(self):
        a, b = humans()
        group = Group([a, b])
        drop = LootItem(ItemTemplate(ITEM), needs_quest=False)
        group.start_roll(drop)
        self.assertEqual(loot_view_slot(b, drop, via_quest_slot=False), SLOT_ROLL_ONGOING)
        self.assertFalse(store_loot_item(b, drop, via_quest_slot=False))

    def test_ref_disenchant_win_consumes_slot_without_the_item(self):
        a, b = humans()
        group = Group([a, b])
        drop = LootItem(ItemTemplate(ITEM), needs_quest=False)
        roll = group.start_roll(drop)
        group.count_roll_vote(roll, "A", DISENCHANT)
        group.count_roll_vote(roll, "B", GREED, rolls={"A": 70, "B": 30})
        self.assertTrue(drop.is_looted)
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM)), (0, 0))

    def test_ref_all_pass_unblocks_for_normal_pickup(self):
        a, b = humans()
        group = Group([a, b])
        drop = LootItem(ItemTemplate(ITEM), needs_quest=False)
        roll = group.start_roll(drop)
        group.count_roll_vote(roll, "A", PASS)
        group.count_roll_vote(roll, "B", PASS)
        self.assertFalse(drop.is_blocked)
        self.assertEqual(loot_view_slot(b, drop, via_quest_slot=False), SLOT_ALLOW_LOOT)
        self.assertTrue(store_loot_item(b, drop, via_quest_slot=False))


class ObjectiveCounters(unittest.TestCase):
    """Eligibility follows QuestStatusData.ItemCount, not inventory (CS01 6400615303)."""

    def test_ref_met_objective_ends_eligibility_while_quest_stays_incomplete(self):
        a = Player("A", quests=[Quest({ITEM: 1, OTHER: 1})])
        a.store_new_item(ITEM, 1)
        quest = a.quests[0]
        self.assertTrue(quest.incomplete)                  # OTHER still missing
        self.assertEqual(quest.counts[ITEM], 1)
        self.assertFalse(quest_drop().allowed_for_player(a))
        self.assertTrue(LootItem(ItemTemplate(OTHER), needs_quest=True).allowed_for_player(a))

    def test_ref_destroying_the_item_reopens_eligibility(self):
        a = Player("A", quests=[QuestObjective(ITEM, NEEDED)])
        a.store_new_item(ITEM, 1)
        self.assertFalse(a.quests[0].incomplete)
        a.remove_item(ITEM, 1)                             # ItemRemovedQuestCheck
        self.assertTrue(a.quests[0].incomplete)
        self.assertEqual(a.quests[0].counts[ITEM], 0)
        self.assertTrue(quest_drop().allowed_for_player(a))

    def test_ref_items_held_before_accepting_count_at_accept(self):
        a = Player("A", inventory={ITEM: 1})
        a.accept_quest(QuestObjective(ITEM, NEEDED))      # AdjustQuestReqItemCount
        self.assertEqual(a.quests[0].counts[ITEM], 1)
        self.assertFalse(quest_drop().allowed_for_player(a))

    def test_ref_loaded_counter_not_bags_decides_after_login(self):
        # A counter saved as met, with the copy no longer in the bags (for
        # example removed while offline), keeps the item ineligible after
        # login; a saved counter of 0 keeps it eligible even if a copy is
        # held. Eligibility follows the stored counter, not inventory.
        met = Player("A")
        met.load_quest(Quest({ITEM: 1, OTHER: 1}, counts={ITEM: 1, OTHER: 0}))
        self.assertEqual(met.item_count(ITEM), 0)
        self.assertFalse(quest_drop().allowed_for_player(met))
        lagging = Player("B", inventory={ITEM: 1})
        lagging.load_quest(Quest({ITEM: 1, OTHER: 1}, counts={ITEM: 0, OTHER: 0}))
        self.assertTrue(quest_drop().allowed_for_player(lagging))

    def test_gap_q6b_surplus_also_while_multi_objective_quest_incomplete(self):
        # The gap does not need the whole quest to finish: once A's ITEM
        # objective is met, a second same-pull win is still stored for A.
        a = Player("A", quests=[Quest({ITEM: 1, OTHER: 1})])
        b = Player("B", quests=[Quest({ITEM: 1, OTHER: 1})])
        group = Group([a, b])
        drops, (r1, r2) = same_pull(group, 2)
        for r in (r1, r2):
            group.count_roll_vote(r, "A", NEED)
            group.count_roll_vote(r, "B", NEED, rolls={"A": 90, "B": 10})
        self.assertTrue(a.quests[0].incomplete)
        self.assertEqual((a.item_count(ITEM), b.item_count(ITEM)), (2, 0))
        self.assertEqual(a.quests[0].counts[ITEM], 1)       # counter capped at required


class OwnerObservationMatrix(unittest.TestCase):
    """#109: candidate native paths for both owner observations.

    One shared, one-copy quest-bucket drop (QuestRequired=1, no MULTI_DROP,
    no flag 0x4), group loot with nothing over threshold, two humans in
    reward range, loot-bearing kills. The guard is configured ON in these
    fixtures because #109 reports it enabled; the owner's EFFECTIVE setting
    and binary are UNVERIFIED (the conf default is 0). These are
    hypotheses that reproduce the symptoms, not proof that no bug exists.
    """

    def setUp(self):
        self.owner, self.friend = humans()
        self.turns = GroupTurns(["A", "B"])

    def corpse(self):
        return Corpse(quest_drop(follow=False), self.turns.on_kill())

    def test_ref_turns_alternate_between_the_two_humans(self):
        # Only for loot-bearing kills with both humans in reward range.
        self.assertEqual([self.turns.on_kill() for _ in range(4)], ["A", "B", "A", "B"])

    def test_ref_empty_loot_kill_does_not_advance_the_turn(self):
        self.assertEqual(self.turns.on_kill(), "A")
        self.assertEqual(self.turns.on_kill(has_loot=False), "B")   # B's turn, no loot
        self.assertEqual(self.turns.on_kill(), "B")                 # still B's turn

    def test_ref_out_of_range_member_gets_no_turn(self):
        self.assertEqual([self.turns.on_kill(in_range={"A"}) for _ in range(3)],
                         ["A", "A", "A"])
        # Back in range: the in-range current looter keeps this kill
        # (ifneed), and the turn moves to B only after it.
        self.assertEqual([self.turns.on_kill(), self.turns.on_kill()], ["A", "B"])

    def test_ref_obs1_sparkle_then_denied_on_owners_turn(self):
        corpse = self.corpse()                              # owner's turn
        corpse.open_for(self.owner)
        corpse.open_for(self.friend)
        self.assertTrue(corpse.sparkles_for(self.friend))    # friend has an own quest slot
        self.assertEqual(try_pickup(True, self.friend, corpse, self.owner), "denied by module")
        self.assertEqual(try_pickup(True, self.owner, corpse, self.owner), "stored")

    def test_ref_obs2_friend_takes_the_shared_copy_on_friends_own_turn(self):
        self.turns.on_kill()                                 # kill 1 was the owner's
        corpse = self.corpse()                               # kill 2: friend's turn
        self.assertEqual(corpse.round_robin_player, "B")
        corpse.open_for(self.owner)
        self.assertEqual(try_pickup(True, self.friend, corpse, self.owner), "stored")
        self.assertEqual(try_pickup(True, self.owner, corpse, self.owner), "refused by core")
        self.assertEqual(self.owner.item_count(ITEM), 0)

    def test_ref_obs2_friend_takes_it_after_owner_closes_the_window(self):
        corpse = self.corpse()
        corpse.open_for(self.owner)
        corpse.release(self.owner)                           # owner closes without taking it
        self.assertEqual(corpse.round_robin_player, "")
        self.assertEqual(try_pickup(True, self.friend, corpse, self.owner), "stored")

    def test_ref_module_off_friend_takes_it_even_on_owners_turn(self):
        # Guard-OFF falsifier: the guard defaults to 0 in the conf, and the
        # owner's effective setting is UNVERIFIED.
        corpse = self.corpse()
        corpse.open_for(self.owner)
        self.assertEqual(try_pickup(False, self.friend, corpse, self.owner), "stored")

    def test_ref_ineligible_friend_never_gets_a_slot_or_the_item(self):
        self.friend.quests.clear()                           # friend lacks the quest
        corpse = self.corpse()
        corpse.open_for(self.owner)
        corpse.release(self.owner)
        corpse.open_for(self.friend)
        self.assertFalse(corpse.has_item_for(self.friend))
        self.assertEqual(try_pickup(True, self.friend, corpse, self.owner), "no slot")

    def test_ref_friend_who_already_finished_the_objective_gets_no_slot(self):
        self.friend.store_new_item(ITEM, 1)                  # counter met
        self.turns.on_kill()
        corpse = self.corpse()                               # even on friend's turn
        self.assertEqual(try_pickup(True, self.friend, corpse, self.owner), "no slot")

    def test_ref_module_guard_transcribed_from_main_blob_48729dc(self):
        # a04_turn_model.module_permits copies this exact file; any change
        # to it must re-review the transcription.
        source = Path(__file__).resolve().parents[2] / "src/Systems/QuestLootProtection.cpp"
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                         "2618b2541372be6855ca8d0e721f971bf2c98d3b1b0d53431409cf174b1862c2")


if __name__ == "__main__":
    unittest.main()
