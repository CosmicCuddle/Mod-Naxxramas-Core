#!/usr/bin/env python3
"""A04 human-friend item-award classification: synthetic research only.

No AzerothCore runtime, SQL, packet interception, character data, or gameplay.
Uses *resolved generated-source* QuestRequired, NOT the mere fact that an
item happens to be mentioned by a quest. Never authorizes a loot denial.
"""

from dataclasses import dataclass
from enum import Enum
import unittest


class Finding(Enum):
    NEED_SOURCE_EVIDENCE = "need_source_evidence"
    NEED_QUEST_STATUS_EVIDENCE = "need_quest_status_evidence"
    EXPECTED_NATIVE_DENIAL = "expected_native_denial"
    REVIEW_POSSIBLE_AWARD_PATH = "review_possible_award_path"
    CUSTOM_QUEST_STATUS_EXCEPTION = "custom_quest_status_exception"
    ORDINARY_SHARED_LOOT = "ordinary_shared_loot"
    POSSIBLE_PERSONAL_MULTI_DROP = "possible_personal_multi_drop"
    POTENTIALLY_ELIGIBLE_NEEDS_TURN_EVIDENCE = "potentially_eligible_needs_turn_evidence"


@dataclass(frozen=True)
class Evidence:
    # Never paste player GUIDs/names or private world rows into this model.
    item_id: int | None = None
    source_resolved: bool = False  # direct/generated or fully resolved reference path
    needs_quest: bool | None = None  # resolved source row QuestRequired, not quest log
    friend_has_quest_for_item: bool | None = None  # AzerothCore predicate
    ignore_quest_status: bool | None = None  # item flagsCustom & 0x2
    multi_drop: bool | None = None  # item Flags & 0x800
    successful_award: bool | None = None  # inventory event, not corpse sparkle
    shared_one_copy_depleted: bool | None = None
    source_kind: str | None = None


@dataclass(frozen=True)
class Assessment:
    finding: Finding
    human_guard_scope_known: bool
    # Deliberately always false: the full native entitlement cannot be
    # established by these fields alone (conditions, turns, slots, roll etc).
    proves_invalid_loot: bool = False
    permits_runtime_fix: bool = False


def assess(e: Evidence) -> Assessment:
    # The current module packet guard is deliberately scoped to creature
    # corpse autostore; even this does not prove it ran/enabled on the owner.
    known_guard_source = e.source_kind == "creature_corpse_autostore"

    def result(finding: Finding) -> Assessment:
        return Assessment(finding, human_guard_scope_known=known_guard_source)

    if (e.item_id is None or e.item_id <= 0 or not e.source_resolved
            or e.needs_quest is None or e.ignore_quest_status is None
            or e.multi_drop is None):
        return result(Finding.NEED_SOURCE_EVIDENCE)

    # A regular loot.items row can be needed for a quest; it does not
    # become exclusive/personal just because a player has that quest.
    if not e.needs_quest:
        if e.multi_drop:
            return result(Finding.POSSIBLE_PERSONAL_MULTI_DROP)
        return result(Finding.ORDINARY_SHARED_LOOT)

    # The custom ignore flag can bypass HasQuestForItem for a needs_quest
    # row. Other eligibility checks still apply, so no award verdict.
    if e.ignore_quest_status:
        return result(Finding.CUSTOM_QUEST_STATUS_EXCEPTION)

    if e.friend_has_quest_for_item is None:
        return result(Finding.NEED_QUEST_STATUS_EVIDENCE)

    if not e.friend_has_quest_for_item:
        if e.successful_award is True:
            return result(Finding.REVIEW_POSSIBLE_AWARD_PATH)
        return result(Finding.EXPECTED_NATIVE_DENIAL)

    if e.multi_drop:
        return result(Finding.POSSIBLE_PERSONAL_MULTI_DROP)

    return result(Finding.POTENTIALLY_ELIGIBLE_NEEDS_TURN_EVIDENCE)


class A04ItemAwardTriage(unittest.TestCase):
    def base(self, **overrides: object) -> Evidence:
        values: dict[str, object] = dict(
            item_id=7777, source_resolved=True, needs_quest=True,
            friend_has_quest_for_item=False, ignore_quest_status=False,
            multi_drop=False, successful_award=True,
            shared_one_copy_depleted=True,
            source_kind="creature_corpse_autostore",
        )
        values.update(overrides)
        return Evidence(**values)

    def test_unidentified_item_never_claims_eligibility(self) -> None:
        self.assertEqual(assess(self.base(item_id=None)).finding, Finding.NEED_SOURCE_EVIDENCE)
        self.assertEqual(assess(self.base(item_id=0)).finding, Finding.NEED_SOURCE_EVIDENCE)

    def test_one_hop_result_does_not_prove_complete_nested_source(self) -> None:
        self.assertEqual(assess(self.base(source_resolved=False)).finding, Finding.NEED_SOURCE_EVIDENCE)

    def test_unknown_questrequired_never_guessed_from_quest_name(self) -> None:
        self.assertEqual(assess(self.base(needs_quest=None)).finding, Finding.NEED_SOURCE_EVIDENCE)

    def test_missing_custom_flag_prevents_false_invalid_award_claim(self) -> None:
        self.assertEqual(assess(self.base(ignore_quest_status=None)).finding, Finding.NEED_SOURCE_EVIDENCE)

    def test_unexpected_successful_needs_quest_award_only_flags_investigation(self) -> None:
        finding = assess(self.base())
        self.assertEqual(finding.finding, Finding.REVIEW_POSSIBLE_AWARD_PATH)
        self.assertFalse(finding.proves_invalid_loot)
        self.assertFalse(finding.permits_runtime_fix)

    def test_sparkle_or_failed_click_is_not_a_successful_award(self) -> None:
        for success in (False, None):
            with self.subTest(success=success):
                self.assertEqual(assess(self.base(successful_award=success)).finding,
                                 Finding.EXPECTED_NATIVE_DENIAL)

    def test_custom_ignore_flag_can_override_quest_status(self) -> None:
        self.assertEqual(assess(self.base(ignore_quest_status=True)).finding,
                         Finding.CUSTOM_QUEST_STATUS_EXCEPTION)

    def test_ordinary_quest_related_drop_stays_stock_shared(self) -> None:
        self.assertEqual(assess(self.base(needs_quest=False)).finding,
                         Finding.ORDINARY_SHARED_LOOT)

    def test_personal_multidrop_not_automatically_invalid(self) -> None:
        self.assertEqual(assess(self.base(needs_quest=False, multi_drop=True)).finding,
                         Finding.POSSIBLE_PERSONAL_MULTI_DROP)
        self.assertEqual(assess(self.base(friend_has_quest_for_item=True, multi_drop=True)).finding,
                         Finding.POSSIBLE_PERSONAL_MULTI_DROP)

    def test_quest_eligible_friend_may_take_shared_one_copy_under_turn(self) -> None:
        finding = assess(self.base(friend_has_quest_for_item=True))
        self.assertEqual(finding.finding, Finding.POTENTIALLY_ELIGIBLE_NEEDS_TURN_EVIDENCE)
        self.assertFalse(finding.proves_invalid_loot)

    def test_unknown_hasquestforitem_cannot_prove_deny(self) -> None:
        self.assertEqual(assess(self.base(friend_has_quest_for_item=None)).finding,
                         Finding.NEED_QUEST_STATUS_EVIDENCE)

    def test_chest_path_is_outside_current_creature_packet_guard(self) -> None:
        self.assertFalse(assess(self.base(source_kind="chest")).human_guard_scope_known)
        self.assertTrue(assess(self.base()).human_guard_scope_known)

    def test_every_result_forbids_automatic_server_policy_changes(self) -> None:
        examples = [self.base(), self.base(needs_quest=False),
                    self.base(friend_has_quest_for_item=True),
                    self.base(ignore_quest_status=True),
                    self.base(source_resolved=False)]
        for sample in examples:
            with self.subTest(sample=sample):
                finding = assess(sample)
                self.assertFalse(finding.proves_invalid_loot)
                self.assertFalse(finding.permits_runtime_fix)


if __name__ == "__main__":
    unittest.main()