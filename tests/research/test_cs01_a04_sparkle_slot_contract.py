"""A04 Part29: source-anchored visible corpse vs viewer quest slot model.

NO owner data, SQL, runtime hooks, gameplay policy, or entitlement writes.
These tests use only the exact PUBLIC Grimfeather AzerothCore source pin.
The synthetic references distinguish possible stock paths, not H1/H2 proof.
"""
import os
import unittest
from dataclasses import dataclass
from pathlib import Path

PIN = "8daffdabe9202c228e45d833c9a1d399597a15cd"
CORE = Path(os.environ.get("A04_PINNED_CORE", "acore"))

PATHS = {
    "player_storage": "src/server/game/Entities/Player/PlayerStorage.cpp",
    "player_quest": "src/server/game/Entities/Player/PlayerQuest.cpp",
    "player": "src/server/game/Entities/Player/Player.cpp",
    "loot": "src/server/game/Loot/LootMgr.cpp",
    "handler": "src/server/game/Handlers/LootHandler.cpp",
}


def compact(value):
    return " ".join(value.split())


def read(name):
    path = CORE / PATHS[name]
    if not path.is_file():
        raise AssertionError("Exact public pin source missing: " + str(path))
    return path.read_text(encoding="utf-8")


def between(text, start, end):
    assert text.count(start) == 1, ("source entrypoint changed", start)
    a = text.index(start)
    assert text.count(end) >= 1, ("source endpoint changed", end)
    b = text.index(end, a + len(start))
    return compact(text[a:b])


@dataclass(frozen=True)
class QuestWindowCase:
    # Already in PlayerQuestItems when the corpse marker was checked;
    # NOT a fresh native FillQuestLoot eligibility decision.
    snapshot_quest_slot: bool
    still_unlooted: bool
    objective_counter_short: bool
    inventory_short: bool
    freeforall: bool = False


def source_shaped_quest_view(case):
    """Constrained transcription of Loot::hasItemFor and LootView quest block.

    This models only the quest-slot branch and player/item state at its
    checkpoints. Creature, group, range, source flags, other loot and hooks
    are intentionally held favorable; no claim about real client rendering.
    """
    sparkle_quest_contribution = case.snapshot_quest_slot and case.still_unlooted
    if not sparkle_quest_contribution:
        return (False, "NO_QUEST_ROW", False, False)

    # LootView re-calls HasQuestForItem(..., &showInLoot), which for a
    # ReqItem objective checks BOTH the stored objective counter AND bag
    # count. The no-objective-need path keeps showInLoot=true -> LOCKED.
    if not case.objective_counter_short:
        return (True, "LOCKED", False, False)
    if not case.inventory_short:
        # showInLoot=false: the *serialization* code flags viewer qitem,
        # and, for one shared non-FFA quest item, also the loot item.
        return (True, "HIDDEN", True, not case.freeforall)
    return (True, "ALLOW", False, False)


class SourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = read("player_storage")
        cls.quest = read("player_quest")
        cls.loot = read("loot")
        cls.player = read("player")
        cls.handler = read("handler")

    def test_corpse_sparkle_checks_cached_quest_item_not_live_objective(self):
        s = between(self.storage,
                    "bool Player::isAllowedToLoot(Creature const* creature)",
                    "void Player::_LoadActions(")
        self.assertIn("!loot->hasItemForAll() && !loot->hasItemFor(this)", s)
        self.assertIn("return loot->hasItemFor(this);", s)
        self.assertIn("loot->roundRobinPlayer == GetGUID()", s)
        self.assertIn("loot->hasOverThresholdItem()", s)
        q = between(self.loot, "bool Loot::hasItemFor(Player* player) const",
                    "bool Loot::hasOverThresholdItem() const")
        self.assertIn("PlayerQuestItems.find(player->GetGUID())", q)
        self.assertIn("if (!qi->is_looted && !item.is_looted) return true;", q)
        self.assertNotIn("HasQuestForItem(", q)
        self.assertNotIn("GetItemCount(", q)

    def test_viewer_specific_quest_list_filled_before_display(self):
        s = between(self.loot, "QuestItemList* Loot::FillQuestLoot(Player* player)",
                    "QuestItemList* Loot::FillNonQuestNonFFAConditionalLoot(")
        self.assertIn("item.AllowedForPlayer(player, sourceWorldObjectGUID)", s)
        self.assertIn("ql->push_back(QuestItem(i));", s)
        self.assertIn("PlayerQuestItems[player->GetGUID()] = ql;", s)
        self.assertIn("bool isMasterLooter", s)
        self.assertIn("if (!allowed && !isMasterLooter) continue;", s)

    def test_quest_counter_and_inventory_are_distinct_window_inputs(self):
        s = between(self.quest, "bool Player::HasQuestForItem(", "// This part - for ReqSource")
        self.assertIn("q_status.ItemCount[j] < qinfo->RequiredItemCount[j]", s)
        self.assertIn("if (showInLoot)", s)
        self.assertIn("GetItemCount(itemid, true) < qinfo->RequiredItemCount[j]", s)
        self.assertIn("*showInLoot = false;", s)
        self.assertIn("return true;", s)

    def test_quest_window_rechecks_and_can_emit_a_locked_row(self):
        s = self.loot
        at = s.index("bool showInLoot = true;")
        q = compact(s[at:s.index("QuestItemMap const& lootPlayerFFAItems", at)])
        self.assertIn("HasQuestForItem(item.itemid, 0, false, &showInLoot)", q)
        self.assertIn("if (!hasQuestForItem)", q)
        self.assertIn("if (!showInLoot)", q)
        self.assertIn("LOOT_SLOT_TYPE_LOCKED", q)
        self.assertIn("l.items.size() + (qi - q_list->begin())", q)

    def test_window_can_hide_a_quest_slot_and_mark_shared_item_looted(self):
        s = self.loot
        at = s.index("bool showInLoot = true;")
        section = compact(s[at:s.index("b << uint8(l.items.size() + (qi - q_list->begin()));", at)])
        self.assertIn("const_cast<QuestItem*>(&(*qi))->is_looted = true;", section)
        self.assertIn("if (!item.freeforall)", section)
        self.assertIn("item.is_looted = true;", section)
        # Source evidence of mutation during viewer-specific serialization;
        # NOT proof that the owner's other player was denied or lost an item.

    def test_autostore_quest_slot_uses_viewer_mapping_then_native_checks(self):
        l = between(self.loot, "LootItem* Loot::LootItemInSlot(",
                    "uint32 Loot::GetMaxSlotInLootFor(")
        self.assertIn("questSlot = lootSlot - items.size();", l)
        self.assertIn("PlayerQuestItems.find(player->GetGUID())", l)
        self.assertIn("item = &quest_items[qitem2->index];", l)
        p = between(self.player, "LootItem* Player::StoreLootItem(",
                    "uint32 Player::CalculateTalentsPoints() const")
        self.assertIn("loot->LootItemInSlot(lootSlot, this, &qitem, &ffaitem, &conditem)", p)
        self.assertIn("item->AllowedForPlayer(this, loot->sourceWorldObjectGUID)", p)
        self.assertIn("if (!qitem && item->is_blocked)", p)
        self.assertIn("item->rollWinnerGUID && item->rollWinnerGUID != GetGUID()", p)
        self.assertIn("CanStoreNewItem(NULL_BAG, NULL_SLOT, dest,", p)

    def test_native_pickup_failure_and_positive_award_are_different(self):
        h = between(self.handler,
                    "void WorldSession::HandleAutostoreLootItemOpcode(",
                    "void WorldSession::HandleLootMoneyOpcode(")
        self.assertIn("player->StoreLootItem(lootSlot, loot, msg);", h)
        p = between(self.player, "LootItem* Player::StoreLootItem(",
                    "uint32 Player::CalculateTalentsPoints() const")
        self.assertIn("SendEquipError(EQUIP_ERR_ALREADY_LOOTED", p)
        self.assertIn("SendLootRelease(GetLootGUID());", p)
        self.assertIn("SendEquipError(msg, nullptr, nullptr, item->itemid);", p)
        self.assertIn("Item* newitem = StoreNewItem(dest, item->itemid", p)
        self.assertIn("sScriptMgr->OnPlayerLootItem(this, newitem", p)
        # A sparkle, lock marker or request attempt alone is not an
        # inventory award, and these returns have different diagnostics.


class SyntheticQuestWindowWitnesses(unittest.TestCase):
    def test_still_eligible_slot_can_be_shown(self):
        self.assertEqual(
            source_shaped_quest_view(QuestWindowCase(True, True, True, True)),
            (True, "ALLOW", False, False))

    def test_cached_slot_after_objective_completed_can_sparkle_and_lock(self):
        self.assertEqual(
            source_shaped_quest_view(QuestWindowCase(True, True, False, True)),
            (True, "LOCKED", False, False))

    def test_counter_short_bags_full_can_hide_and_flag_shared_item(self):
        self.assertEqual(
            source_shaped_quest_view(QuestWindowCase(True, True, True, False)),
            (True, "HIDDEN", True, True))

    def test_freeforall_hides_local_slot_without_marking_shared_item(self):
        self.assertEqual(
            source_shaped_quest_view(QuestWindowCase(True, True, True, False,
                                                     freeforall=True)),
            (True, "HIDDEN", True, False))

    def test_no_snapshot_or_already_taken_slot_has_no_quest_sparkle(self):
        for case in (
            QuestWindowCase(False, True, True, True),
            QuestWindowCase(True, False, True, True),
        ):
            with self.subTest(case=case):
                self.assertEqual(source_shaped_quest_view(case),
                                 (False, "NO_QUEST_ROW", False, False))

    def test_distinct_states_do_not_imply_owner_case_h1_or_h2(self):
        # The same client-visible "sparkle" may lead to different
        # source-shaped loot rows without any core bug or item award.
        cases = [
            QuestWindowCase(True, True, True, True),
            QuestWindowCase(True, True, False, True),
            QuestWindowCase(True, True, True, False),
        ]
        results = [source_shaped_quest_view(x) for x in cases]
        self.assertTrue(all(x[0] for x in results))
        self.assertEqual([x[1] for x in results],
                         ["ALLOW", "LOCKED", "HIDDEN"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
