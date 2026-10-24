"""A04: source-shaped STOCK quest/ordinary loot display-vs-award model.

These are synthetic source predictions at AzerothCore Grimfeather
8daffdabe9202c228e45d833c9a1d399597a15cd.
No actual player is awarded an item by this test. It models ONLY:
- LootItem::AllowedForPlayer's quest-required condition (other prerequisites
  are represented by conditions_ok);
- LootView's ordinary, condition-free ROUND_ROBIN_PERMISSION visibility;
- the basic StoreLootItem award check for a normal item slot, not every
  AzerothCore handler, quest-slot, roll, master-loot or bot path.

A true model result does not prove the owner's real client sent that packet,
that this is the reported issue, or that a production fix exists.
Never use this model to impose a named-owner or per-player loot-copy system.
"""
from dataclasses import dataclass
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Facts:
    quest_required: bool = False
    viewer_needs_quest_item: bool = False
    ignore_quest_status_flag: bool = False
    conditions_ok: bool = True
    item_is_looted: bool = False
    item_is_blocked: bool = False
    item_is_personal_multidrop: bool = False
    item_has_conditions: bool = False
    another_round_robin_holder: bool = False
    roll_is_awarded_to_another_player: bool = False


def eligibility_check(f):
    """The quest-status arm of LootItem::AllowedForPlayer, plus a stand-in
    for its OTHER independent checks. This is NOT all of AllowedForPlayer."""
    if not f.conditions_ok:
        return False
    if f.quest_required and not f.ignore_quest_status_flag:
        return f.viewer_needs_quest_item
    return True


def normal_round_robin_slot_visible(f):
    """Normal items-only ROUND_ROBIN_PERMISSION branch of LootView.
    Personal FFA and quest views run other loops and are excluded."""
    if f.quest_required or f.item_is_personal_multidrop or f.item_has_conditions:
        return False
    if f.item_is_looted or not eligibility_check(f):
        return False
    return not f.another_round_robin_holder


def normal_slot_storable_after_request(f, request_sent):
    """Narrow native StoreLootItem comparison for a resolved normal slot.

    The core re-checks AllowedForPlayer / blocked / roll winner, but does
    not in general repeat LootView's round-robin holder check here.
    Assumes source, distance, item slot and inventory capacity passed.
    Does not model master-loot's special exception or item containers.
    """
    if f.quest_required or f.item_is_personal_multidrop or f.item_has_conditions:
        return False  # Outside this *ordinary-only* comparison.
    if not request_sent or f.item_is_looted or f.item_is_blocked:
        return False
    if f.roll_is_awarded_to_another_player or not eligibility_check(f):
        return False
    return True


class EligibilitySemantics(unittest.TestCase):
    def test_quest_only_item_without_need_rejected_by_stock(self):
        self.assertFalse(eligibility_check(Facts(quest_required=True)))

    def test_quest_only_item_with_need_can_be_eligible(self):
        self.assertTrue(eligibility_check(Facts(
            quest_required=True, viewer_needs_quest_item=True)))

    def test_quest_only_custom_ignore_flag_is_exception(self):
        self.assertTrue(eligibility_check(Facts(
            quest_required=True, ignore_quest_status_flag=True)))

    def test_regular_item_can_be_valid_shared_loot_without_quest(self):
        self.assertTrue(eligibility_check(Facts()))

    def test_other_native_conditions_are_still_required(self):
        self.assertFalse(eligibility_check(Facts(conditions_ok=False)))


class NormalRoundRobinComparison(unittest.TestCase):
    def test_owner_sees_normal_item(self):
        self.assertTrue(normal_round_robin_slot_visible(Facts()))

    def test_non_holder_does_not_see_normal_item(self):
        self.assertFalse(normal_round_robin_slot_visible(
            Facts(another_round_robin_holder=True)))

    def test_released_round_robin_turn_makes_normal_slot_visible(self):
        self.assertTrue(normal_round_robin_slot_visible(
            Facts(another_round_robin_holder=False)))

    def test_hidden_normal_slot_has_potential_server_request_discrepancy(self):
        f = Facts(another_round_robin_holder=True)
        self.assertFalse(normal_round_robin_slot_visible(f))
        self.assertTrue(normal_slot_storable_after_request(f, request_sent=True))

    def test_hidden_slot_does_not_spontaneously_award(self):
        f = Facts(another_round_robin_holder=True)
        self.assertFalse(normal_slot_storable_after_request(f, request_sent=False))

    def test_blocked_item_or_others_roll_winner_not_awarded(self):
        for facts in (Facts(item_is_blocked=True),
                      Facts(roll_is_awarded_to_another_player=True),
                      Facts(item_is_looted=True),
                      Facts(conditions_ok=False)):
            with self.subTest(facts=facts):
                self.assertFalse(normal_slot_storable_after_request(
                    facts, request_sent=True))

    def test_personal_and_quest_buckets_are_explicitly_outside_normal_model(self):
        for facts in (Facts(quest_required=True),
                      Facts(item_is_personal_multidrop=True),
                      Facts(item_has_conditions=True)):
            with self.subTest(facts=facts):
                self.assertFalse(normal_round_robin_slot_visible(facts))
                self.assertFalse(normal_slot_storable_after_request(
                    facts, request_sent=True))


class ResearchBoundaries(unittest.TestCase):
    def test_trace_disclaims_real_award_and_new_ownership_rules(self):
        report = (ROOT / "docs/research/A04-NATIVE-VISIBILITY-VS-AWARD-SOURCE-TRACE.md").read_text("utf-8")
        self.assertIn("candidate security/integrity seam", report)
        self.assertIn("not proof that a stock client sent a hidden-slot packet", report)
        self.assertIn("stock WoW/AzerothCore group-loot behavior", report)
        self.assertIn("Do not convert it to personal loot", report)
        self.assertIn("not proof", report.lower())


if __name__ == "__main__":
    unittest.main()
