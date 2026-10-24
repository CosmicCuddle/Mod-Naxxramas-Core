"""A04: source-shaped FFA viewer-map/slot lookup hypothesis, NOT gameplay.

At Grimfeather AzerothCore 8daffdabe9202c228e45d833c9a1d399597a15cd,
Loot::LootItemInSlot initializes normal item->is_looted, then optionally
replaces it with the matching viewer's PlayerFFAItems entry. A missing
viewer/index does not visibly turn is_looted true in that branch.
This does NOT establish a stock-client exploit or the owner's report.
"""

from dataclasses import dataclass
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class FFASlot:
    item_is_looted: bool = False
    viewer_has_ffa_map: bool = False
    viewer_has_matching_index: bool = False
    viewer_personal_entry_looted: bool = False
    allowed_for_player: bool = True
    blocked: bool = False
    other_roll_winner: bool = False


def native_ffa_slot_resolves(f):
    """Model ONLY normal-slot LootItemInSlot's per-view FFA is_looted choice."""
    effective_looted = f.item_is_looted
    if f.viewer_has_ffa_map and f.viewer_has_matching_index:
        effective_looted = f.viewer_personal_entry_looted
    return not effective_looted


def possible_native_award_if_requested(f, packet_sent):
    """Narrow award-path prediction; excludes source/range/bags/master rules."""
    return (
        packet_sent
        and native_ffa_slot_resolves(f)
        and f.allowed_for_player
        and not f.blocked
        and not f.other_roll_winner
    )


class FFASlotHypothesis(unittest.TestCase):
    def test_valid_personal_entry_can_resolve(self):
        f = FFASlot(viewer_has_ffa_map=True, viewer_has_matching_index=True)
        self.assertTrue(native_ffa_slot_resolves(f))

    def test_already_personally_looted_entry_is_denied(self):
        f = FFASlot(
            viewer_has_ffa_map=True, viewer_has_matching_index=True,
            viewer_personal_entry_looted=True
        )
        self.assertFalse(native_ffa_slot_resolves(f))
        self.assertFalse(possible_native_award_if_requested(f, True))

    def test_absent_viewer_map_falls_back_to_global_not_looted(self):
        f = FFASlot()
        self.assertTrue(native_ffa_slot_resolves(f))
        self.assertTrue(possible_native_award_if_requested(f, True))

    def test_absent_index_in_existing_map_is_same_source_candidate(self):
        f = FFASlot(viewer_has_ffa_map=True, viewer_has_matching_index=False)
        self.assertTrue(native_ffa_slot_resolves(f))

    def test_native_allowed_for_player_still_can_refuse_award(self):
        f = FFASlot(allowed_for_player=False)
        self.assertTrue(native_ffa_slot_resolves(f))
        self.assertFalse(possible_native_award_if_requested(f, True))

    def test_globally_looted_item_without_personal_map_is_denied(self):
        f = FFASlot(item_is_looted=True)
        self.assertFalse(native_ffa_slot_resolves(f))
        self.assertFalse(possible_native_award_if_requested(f, True))

    def test_no_packet_no_award_even_with_missing_viewer_entry(self):
        f = FFASlot()
        self.assertFalse(possible_native_award_if_requested(f, False))

    def test_blocked_or_other_roll_winner_still_prevents_award(self):
        for f in (FFASlot(blocked=True), FFASlot(other_roll_winner=True)):
            with self.subTest(f=f):
                self.assertFalse(possible_native_award_if_requested(f, True))

    def test_research_does_not_claim_owner_incident_proved(self):
        research = (ROOT / "docs/research/A04-PER-VIEWER-FFA-AND-PLAYERBOT-PACKET-SOURCE-TRACE.md").read_text("utf-8")
        self.assertIn("not confirmation of the human friend's reported incorrect quest pickup", research)
        self.assertIn("Loot::LootItemInSlot", research)
        self.assertIn("PlayerFFAItems", research)
        self.assertIn("QueuePacket(packet)", research)
        self.assertIn("not proof every bot", research.lower())
        self.assertIn("No owner item ID", research)


if __name__ == "__main__":
    unittest.main()
