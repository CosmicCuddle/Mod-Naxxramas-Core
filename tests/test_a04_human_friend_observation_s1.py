"""A04: human-friend quest loot investigation -- synthetic source contract only.

This does NOT implement a loot policy, run a worldserver, or award an item.
It checks the pinned current guard's intentional early permits and the
separation of debug logging from the real denial signal.
The owner still must choose any replacement entitlement policy.
"""
from dataclasses import dataclass
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Systems/QuestLootProtection.cpp").read_text("utf-8")
REPORT = (ROOT / "docs/research/A04-HUMAN-FRIEND-OBSERVATION-GATES-S1.md").read_text("utf-8")


@dataclass(frozen=True)
class Observation:
    enabled: bool = True
    creature_corpse: bool = True
    recipient_group_matches: bool = True
    guarded_loot_method: bool = True
    round_robin_holder_exists: bool = True
    viewer_holds_turn: bool = False
    quest_slot: bool = True
    unique_shared_copy: bool = True
    holder_present_and_eligible: bool = True
    viewer_has_personal_multidrop: bool = False


def existing_guard_decision(o):
    """First matching branch in today's PermitPickup, simplified to the
    eligible grouped/in-range/item-template case. This is not an independent
    representation of every AzerothCore loot path."""
    if not o.enabled:
        return "PERMIT_FEATURE_OFF"
    if not o.guarded_loot_method:
        return "PERMIT_LOOT_METHOD"
    if not o.creature_corpse:
        return "PERMIT_NON_CORPSE"
    if not o.recipient_group_matches:
        return "PERMIT_DIFFERENT_RECIPIENT"
    if not o.round_robin_holder_exists:
        return "PERMIT_RELEASED_TURN"
    if o.viewer_holds_turn:
        return "PERMIT_CURRENT_HOLDER"
    if not o.quest_slot:
        return "PERMIT_NORMAL_ITEM_SLOT"
    if o.viewer_has_personal_multidrop or not o.unique_shared_copy:
        return "PERMIT_NOT_ONE_SHARED_COPY"
    if not o.holder_present_and_eligible:
        return "PERMIT_HOLDER_INELIGIBLE"
    return "DENY_ACTIVE_ELIGIBLE_OWNER"


class SourceBoundary(unittest.TestCase):
    def test_feature_stays_off_by_default(self):
        self.assertIn('"NaxxramasCore.QuestLootProtection.Enabled", false', SOURCE)

    def test_scope_returns_before_quest_owner_logic(self):
        landmarks = (
            "if (!sourceGuid.IsCreatureOrVehicle())",
            "creature->GetLootRecipientGroup() != group",
            "loot.loot_type != LOOT_CORPSE",
            "!loot.roundRobinPlayer",
            "loot.roundRobinPlayer == player->GetGUID()",
            "requestedSlot < normalCount",
            "item.freeforall",
            "owner->HasQuestForItem(item.itemid)",
            "player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED)",
        )
        positions = [SOURCE.index(marker) for marker in landmarks]
        self.assertEqual(positions, sorted(positions))

    def test_debug_off_does_not_disable_denial(self):
        self.assertEqual(SOURCE.count('LOG_INFO("module",'), 1)
        start = SOURCE.index("if (Debug())")
        log = SOURCE.index('LOG_INFO("module",', start)
        signal = SOURCE.index("player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED)", log)
        denied = SOURCE.index("return false;", signal)
        self.assertLess(start, log)
        self.assertLess(log, signal)
        self.assertLess(signal, denied)
        self.assertIn("Debug=0", REPORT)

    def test_observation_report_disclaims_actual_gameplay(self):
        for marker in ("HF-01", "HF-02", "HF-03", "HF-04",
                       "HF-05", "HF-06", "HF-07", "NOT RUN"):
            with self.subTest(marker=marker):
                self.assertIn(marker, REPORT)


    def test_owner_policy_preserves_stock_quest_loot(self):
        spec = (ROOT / "docs/research/A04-HUMAN-TO-HUMAN-S2-FUNCTIONAL-GATE.md").read_text("utf-8")
        self.assertIn("Owner-approved requirement — stock WoW quest-loot parity", spec)
        self.assertIn("legitimate shared-loot turn", spec)
        self.assertIn("no B/C policy choice", spec)
        self.assertIn("No B/C loot-policy redesign is requested or approved", spec)
        self.assertNotIn("Owner decision needed for actual S2", spec)


class HumanFriendObservationModels(unittest.TestCase):
    def test_hf01_friend_is_holder_can_consume_shared_copy(self):
        self.assertEqual(existing_guard_decision(Observation(viewer_holds_turn=True)),
                         "PERMIT_CURRENT_HOLDER")

    def test_hf02_active_eligible_owner_blocks_other_human(self):
        self.assertEqual(existing_guard_decision(Observation()),
                         "DENY_ACTIVE_ELIGIBLE_OWNER")

    def test_hf03_released_round_robin_turn_does_not_block(self):
        self.assertEqual(existing_guard_decision(
            Observation(round_robin_holder_exists=False)), "PERMIT_RELEASED_TURN")

    def test_hf04_quest_relevant_but_normal_loot_bucket(self):
        self.assertEqual(existing_guard_decision(Observation(quest_slot=False)),
                         "PERMIT_NORMAL_ITEM_SLOT")

    def test_hf05_independent_personal_multidrop_not_theft(self):
        self.assertEqual(existing_guard_decision(
            Observation(viewer_has_personal_multidrop=True)),
            "PERMIT_NOT_ONE_SHARED_COPY")

    def test_hf06_unprotected_group_loot_method(self):
        self.assertEqual(existing_guard_decision(
            Observation(guarded_loot_method=False)), "PERMIT_LOOT_METHOD")

    def test_hf07_gameobject_or_noncorpse_is_outside_guard(self):
        self.assertEqual(existing_guard_decision(
            Observation(creature_corpse=False)), "PERMIT_NON_CORPSE")

    def test_hf07_foreign_tagged_corpse_group_deferred_to_native(self):
        self.assertEqual(existing_guard_decision(
            Observation(recipient_group_matches=False)),
            "PERMIT_DIFFERENT_RECIPIENT")

    def test_absent_or_ineligible_owner_deferred_to_native(self):
        self.assertEqual(existing_guard_decision(
            Observation(holder_present_and_eligible=False)),
            "PERMIT_HOLDER_INELIGIBLE")

    def test_master_disabled_is_never_a_denial(self):
        self.assertEqual(existing_guard_decision(Observation(enabled=False)),
                         "PERMIT_FEATURE_OFF")


if __name__ == "__main__":
    unittest.main()
