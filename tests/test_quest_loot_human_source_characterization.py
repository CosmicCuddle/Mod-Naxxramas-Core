"""A04 human-vs-human loot regression *characterization* (synthetic only).

These tests describe the existing source's three separate decisions:
1. A viewer's broad corpse sparkle, 2. the module's narrow packet refusal,
3. the core's item-storage checks. They DO NOT show what happened in-game or
prove a corrected policy. See issue #109 and draft PR #110.
"""
from dataclasses import dataclass
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Systems/QuestLootProtection.cpp"

GROUP_METHODS = ("GROUP_LOOT", "NEED_BEFORE_GREED", "ROUND_ROBIN")


@dataclass(frozen=True)
class HumanCase:
    """A single candidate quest drop under the pinned current-source rules."""
    group_method: str = "GROUP_LOOT"
    rr_active: bool = True
    viewer_is_turn_holder: bool = False
    quest_view: bool = True
    other_valid_loot: bool = False  # viewer-specific FFA/conditional item
    over_threshold_item: bool = False  # GROUP/NBG non-holder visibility
    gold: bool = False  # gold alone does NOT create a non-holder sparkle
    viewer_is_master_looter: bool = False
    owner_needs_item: bool = True
    quest_slot: bool = True         # QuestRequired -> loot.quest_items
    has_quest_for_item: bool = True
    follow_loot_rules: bool = False
    blocked: bool = False
    count: int = 1
    multi_drop: bool = False
    owner_available_and_eligible: bool = True
    player_can_receive_item: bool = True
    guard_enabled: bool = True
    server_flag_lootable: bool = True


def core_sparkle(case):
    """Approximate pinned isAllowedToLoot -> UNIT_DYNFLAG_LOOTABLE path.

    'quest_view' stands for Loot::hasItemFor(viewer) being true. This
    broad check does not encode the module's active turn restriction.
    """
    if not case.server_flag_lootable:
        return False
    if case.group_method in ("FREE_FOR_ALL", "MASTER_LOOT"):
        return True
    if case.group_method not in GROUP_METHODS:
        return False
    if not case.rr_active or case.viewer_is_turn_holder:
        return True
    if case.group_method in ("GROUP_LOOT", "NEED_BEFORE_GREED") and case.over_threshold_item:
        return True
    return case.quest_view or case.other_valid_loot


def module_blocks_autostore(case):
    """Necessary slice of the existing 21-part human packet deny conjunction.

    Assumes creature corpse, correct group, valid packet/quest slot and same
    live map unless a field states otherwise. Failure of any listed guard
    permits normal core processing. This is NOT a replacement guard.
    """
    return all((
        case.guard_enabled,
        case.group_method in GROUP_METHODS,
        case.rr_active,
        not case.viewer_is_turn_holder,
        case.quest_view,
        case.quest_slot,
        case.count == 1,
        not case.multi_drop,
        not case.follow_loot_rules,
        not case.blocked,
        case.owner_available_and_eligible,
        case.owner_needs_item,
    ))


def native_store_candidate(case):
    """Potential core StoreLootItem path, not an actual item award.

    Assumes an existing LootItemInSlot for this player, no inventory error,
    no roll winner, no blocked slot; the pinned StoreLootItem lacks a blanket
    round-robin check for qitem slots. Other core validity still matters.
    """
    return case.player_can_receive_item and case.quest_view


def core_quest_window_slot_type(case):
    """Simplified pinned LootView quest-row display for a needed quest item.

    For a non-FFA non-follow-rules personal quest view, the core emits
    LOOT_SLOT_TYPE_ALLOW_LOOT in GROUP/ROUND_ROBIN/RESTRICTED permissions,
    without a fresh active round-robin owner check in that quest loop.
    This explains the *item label*, separate from the corpse sparkle.
    """
    if not case.quest_view or not case.quest_slot:
        return "NO_QUEST_ROW"
    if not case.has_quest_for_item:
        return "LOCKED"  # only when native showInLoot remains true
    if case.follow_loot_rules:
        if case.group_method == "MASTER_LOOT":
            if case.viewer_is_master_looter:
                return "MASTER"
            return "LOCKED" if case.blocked else "ALLOW_LOOT"
        if case.blocked:
            return "ROLL_ONGOING"
        return "ALLOW_LOOT"
    if case.group_method == "MASTER_LOOT" and case.viewer_is_master_looter:
        return "MASTER"
    return "ALLOW_LOOT"


def human_pickup_candidate(case):
    """Whether this simplified sequential pipeline reaches native storage."""
    return not module_blocks_autostore(case) and native_store_candidate(case)


def whole_packet_veto_hides_legitimate_loot(case):
    """Negative model: a wholesale SMSG_LOOT_RESPONSE veto hides ALL rows/gold.

    Pinned ServerScript::CanPacketSend accepts a const WorldPacket& and can
    only permit or veto that whole packet. This helper is a *counterexample*,
    NOT a recommendation to intercept packets.
    """
    return case.other_valid_loot


class ExistingHumanLootSourceCharacterization(unittest.TestCase):
    def test_active_turn_can_sparkle_even_when_human_packet_denied(self):
        case = HumanCase()
        self.assertTrue(core_sparkle(case))
        self.assertTrue(module_blocks_autostore(case))
        self.assertFalse(human_pickup_candidate(case))

    def test_human_quest_row_can_say_allow_loot_despite_packet_denial(self):
        case = HumanCase()
        self.assertTrue(core_sparkle(case))
        self.assertEqual(core_quest_window_slot_type(case), "ALLOW_LOOT")
        self.assertTrue(module_blocks_autostore(case))

    def test_quest_row_remains_allow_while_round_robin_owner_releases(self):
        before = HumanCase(rr_active=True)
        after = HumanCase(rr_active=False)
        self.assertEqual(core_quest_window_slot_type(before), "ALLOW_LOOT")
        self.assertEqual(core_quest_window_slot_type(after), "ALLOW_LOOT")
        self.assertTrue(module_blocks_autostore(before))
        self.assertFalse(module_blocks_autostore(after))

    def test_quest_view_with_follow_rules_keeps_roll_and_master_display(self):
        self.assertEqual(core_quest_window_slot_type(HumanCase(
            follow_loot_rules=True, blocked=True)), "ROLL_ONGOING")
        self.assertEqual(core_quest_window_slot_type(HumanCase(
            group_method="MASTER_LOOT", viewer_is_master_looter=True)), "MASTER")
        self.assertFalse(module_blocks_autostore(HumanCase(
            follow_loot_rules=True, blocked=True)))

    def test_h09_friend_is_the_turn_holder_guard_allows_by_design(self):
        case = HumanCase(viewer_is_turn_holder=True)
        self.assertTrue(core_sparkle(case))
        self.assertEqual(core_quest_window_slot_type(case), "ALLOW_LOOT")
        self.assertFalse(module_blocks_autostore(case))
        self.assertTrue(human_pickup_candidate(case))

    def test_h10_turn_holder_does_not_need_quest_guard_falls_open(self):
        case = HumanCase(owner_needs_item=False)
        self.assertTrue(core_sparkle(case))
        self.assertEqual(core_quest_window_slot_type(case), "ALLOW_LOOT")
        self.assertFalse(module_blocks_autostore(case))
        self.assertTrue(human_pickup_candidate(case))

    def test_master_loot_restricted_player_still_sees_allow_loot_quest_row(self):
        restricted = HumanCase(group_method="MASTER_LOOT", viewer_is_master_looter=False)
        master = HumanCase(group_method="MASTER_LOOT", viewer_is_master_looter=True)
        self.assertEqual(core_quest_window_slot_type(restricted), "ALLOW_LOOT")
        self.assertEqual(core_quest_window_slot_type(master), "MASTER")
        self.assertEqual(core_quest_window_slot_type(HumanCase(
            group_method="MASTER_LOOT", follow_loot_rules=True,
            blocked=True, viewer_is_master_looter=False)), "LOCKED")

    def test_gold_alone_does_not_grant_sparkle_to_nonholder(self):
        case = HumanCase(quest_view=False, other_valid_loot=False,
                         over_threshold_item=False, gold=True)
        self.assertFalse(core_sparkle(case))
        self.assertFalse(module_blocks_autostore(case))

    def test_over_threshold_group_spot_vs_round_robin_differ(self):
        group = HumanCase(group_method="GROUP_LOOT", quest_view=False,
                          over_threshold_item=True)
        rr = HumanCase(group_method="ROUND_ROBIN", quest_view=False,
                       over_threshold_item=True)
        self.assertTrue(core_sparkle(group))
        self.assertFalse(core_sparkle(rr))

    def test_released_turn_can_show_and_reach_native_store(self):
        case = HumanCase(rr_active=False)
        self.assertTrue(core_sparkle(case))
        self.assertFalse(module_blocks_autostore(case))
        self.assertTrue(human_pickup_candidate(case))

    def test_quest_related_normal_slot_can_bypass_narrow_guard(self):
        case = HumanCase(quest_slot=False)
        self.assertTrue(core_sparkle(case))
        self.assertFalse(module_blocks_autostore(case))
        self.assertTrue(human_pickup_candidate(case))

    def test_disabled_guard_can_reach_native_store(self):
        case = HumanCase(guard_enabled=False)
        self.assertTrue(core_sparkle(case))
        self.assertFalse(module_blocks_autostore(case))
        self.assertTrue(human_pickup_candidate(case))

    def test_multi_drop_copy_is_intentionally_not_blocked(self):
        case = HumanCase(multi_drop=True)
        self.assertTrue(core_sparkle(case))
        self.assertFalse(module_blocks_autostore(case))
        self.assertTrue(human_pickup_candidate(case))
        # This can be a valid independent copy, NOT demonstrated theft.

    def test_item_count_above_one_is_legacy_fail_open(self):
        case = HumanCase(count=2)
        self.assertTrue(core_sparkle(case))
        self.assertFalse(module_blocks_autostore(case))

    def test_owner_missing_is_legacy_fail_open(self):
        case = HumanCase(owner_available_and_eligible=False)
        self.assertTrue(core_sparkle(case))
        self.assertFalse(module_blocks_autostore(case))

    def test_other_valid_loot_may_require_sparkle(self):
        case = HumanCase(quest_view=False, other_valid_loot=True)
        self.assertTrue(core_sparkle(case))
        self.assertFalse(module_blocks_autostore(case))
        self.assertFalse(native_store_candidate(case))  # no *quest* slot

    def test_nonholder_without_any_view_or_other_right_has_no_sparkle(self):
        case = HumanCase(quest_view=False, other_valid_loot=False)
        self.assertFalse(core_sparkle(case))
        self.assertFalse(module_blocks_autostore(case))

    def test_deny_is_not_a_global_corpse_flag_change(self):
        case = HumanCase()
        self.assertTrue(case.server_flag_lootable)
        self.assertTrue(module_blocks_autostore(case))
        self.assertTrue(case.server_flag_lootable)

    def test_master_and_ffa_are_not_automatically_forbidden(self):
        for method in ("MASTER_LOOT", "FREE_FOR_ALL"):
            with self.subTest(method=method):
                case = HumanCase(group_method=method)
                self.assertTrue(core_sparkle(case))
                self.assertFalse(module_blocks_autostore(case))
                # Native mastery/FFA eligibility has extra checks in reality.

    def test_wholesale_response_veto_would_hide_rightful_gold_or_item(self):
        # Viewer may have legitimate money/ordinary loot on the SAME corpse
        # even if a single quest-item row is wrong for them.
        case = HumanCase(other_valid_loot=True)
        self.assertTrue(whole_packet_veto_hides_legitimate_loot(case))
        self.assertTrue(core_sparkle(case))
        self.assertEqual(core_quest_window_slot_type(case), "ALLOW_LOOT")
        # Dropping the entire response must NOT be treated as an A04 fix.

    def test_empty_other_rewards_does_not_make_whole_response_rewrite_safe(self):
        case = HumanCase(other_valid_loot=False)
        self.assertFalse(whole_packet_veto_hides_legitimate_loot(case))
        # Even so, core does not expose per-item mutation in the send veto.
        # Empty other rewards is not proof that packet/slot edits are safe.

    def test_live_source_still_has_narrow_packet_only_guard(self):
        if not SOURCE.is_file():
            self.skipTest("module source absent outside repository checkout")
        cpp = SOURCE.read_text(encoding="utf-8")
        for snippet in (
            "SERVERHOOK_CAN_PACKET_RECEIVE",
            "CMSG_AUTOSTORE_LOOT_ITEM",
            "if (requestedSlot < normalCount)",
            "if (loot.loot_type != LOOT_CORPSE ||",
            "!loot.roundRobinPlayer",
            "if (!item.needs_quest || item.count != 1",
            "item.freeforall",
            "item.follow_loot_rules",
            "ITEM_FLAG_MULTI_DROP",
        ):
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, cpp)
        self.assertNotIn("UNITHOOK_ON_PATCH_VALUES_UPDATE", cpp)
        self.assertNotIn("class NaxxramasQuestLootProtectionViewer", cpp)


if __name__ == "__main__":
    unittest.main()
