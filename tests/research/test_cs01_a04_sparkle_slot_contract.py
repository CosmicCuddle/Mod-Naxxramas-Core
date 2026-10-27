"""A04 Part29: source-anchored visible corpse vs viewer quest slot model.

NO owner data, SQL, runtime hooks, gameplay policy, or entitlement writes.
These tests use only the exact PUBLIC Grimfeather AzerothCore source pin.
The synthetic references distinguish possible stock paths, not H1/H2 proof.
"""
import os
import re
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
    "loot_header": "src/server/game/Loot/LootMgr.h",
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
        cls.loot_header = read("loot_header")

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


    def test_shared_nonffa_quest_row_is_counted_once_during_fill(self):
        fill = between(self.loot,
                       "QuestItemList* Loot::FillQuestLoot(Player* player)",
                       "QuestItemList* Loot::FillNonQuestNonFFAConditionalLoot(")
        self.assertIn("item.AllowedForPlayer(player, sourceWorldObjectGUID)", fill)
        self.assertIn("ql->push_back(QuestItem(i));", fill)
        self.assertIn("if (item.freeforall)", fill)
        self.assertIn("else if (!item.is_counted)", fill)
        self.assertIn("++unlootedCount;", fill)
        self.assertIn("item.is_counted = true;", fill)
        self.assertIn("PlayerQuestItems[player->GetGUID()] = ql;", fill)
        # For a shared non-FFA item whose two viewer lists were filled
        # while eligible, the counter is incremented once, not twice.

    def test_window_shared_looted_mutation_has_no_count_reconciliation(self):
        # The exact pinned quest-window hide branch is a data mutation,
        # with no balancing decrement of the global outstanding count.
        start = self.loot.index("bool showInLoot = true;")
        end = self.loot.index(
            "b << uint8(l.items.size() + (qi - q_list->begin()));", start)
        hidden = compact(self.loot[start:end])
        self.assertIn("const_cast<QuestItem*>(&(*qi))->is_looted = true;", hidden)
        self.assertIn("if (!item.freeforall)", hidden)
        self.assertIn("item.is_looted = true;", hidden)
        self.assertIn("continue;", hidden)
        self.assertNotIn("--unlootedCount;", hidden)
        self.assertNotIn("--l.unlootedCount;", hidden)
        self.assertNotIn("unlootedCount--;", hidden)

    def test_second_viewer_cached_slot_reuses_shared_is_looted_flag(self):
        view = self.loot[self.loot.index("QuestItemMap const& lootPlayerQuestItems = l.GetPlayerQuestItems();"):]
        self.assertIn("if (!qi->is_looted && !item.is_looted)", compact(view))
        has = between(self.loot, "bool Loot::hasItemFor(Player* player) const",
                      "bool Loot::hasOverThresholdItem() const")
        self.assertIn("if (!qi->is_looted && !item.is_looted) return true;",
                      compact(has))
        slot = between(self.loot, "LootItem* Loot::LootItemInSlot(",
                       "uint32 Loot::GetMaxSlotInLootFor(")
        self.assertIn("item = &quest_items[qitem2->index];", compact(slot))
        award = between(self.player, "LootItem* Player::StoreLootItem(",
                        "uint32 Player::CalculateTalentsPoints() const")
        self.assertIn("if (!item || item->is_looted)", compact(award))

    def test_islooted_depends_on_count_and_loot_release_uses_islooted(self):
        self.assertIn(
            "[[nodiscard]] bool isLooted() const { return gold == 0 && unlootedCount == 0; }",
            compact(self.loot_header))
        release = between(self.handler, "void WorldSession::DoLootRelease(",
                          "void WorldSession::HandleLootMasterGiveOpcode(")
        self.assertIn("if (loot->isLooted())", release)
        self.assertIn("creature->RemoveDynamicFlag(UNIT_DYNFLAG_LOOTABLE);", release)
        self.assertIn("loot->roundRobinPlayer.Clear();", release)
        # A nonzero stale unlootedCount takes the NOT fully-looted
        # branch on creature release, even if the shared item is flagged.

    def test_native_award_has_separate_count_decrement(self):
        award = between(self.player, "LootItem* Player::StoreLootItem(",
                        "uint32 Player::CalculateTalentsPoints() const")
        self.assertIn("Item* newitem = StoreNewItem(", award)
        self.assertIn("if (!item->freeforall) item->is_looted = true;",
                      compact(award))
        self.assertIn("--loot->unlootedCount;", award)
        # A real award and serialization-side suppression use different
        # count transitions: never treat one as evidence of the other.

@dataclass
class TwoViewerSharedQuest:
    """Minimal same-corpse state, not a simulation of a running Worldserver.

    For shared quest loot, FillQuestLoot counted one item once, with a
    separately mapped quest entry for two eligible humans at spawn.
    """
    shared_looted: bool = False
    owner_slot_looted: bool = False
    friend_slot_looted: bool = False
    unlooted_count: int = 1
    round_robin_owner: bool = True

    def show(self, viewer, objective_short=True, bag_short=True):
        local = self.owner_slot_looted if viewer == "owner" else self.friend_slot_looted
        result = source_shaped_quest_view(QuestWindowCase(
            True, not self.shared_looted and not local,
            objective_short, bag_short, freeforall=False,
        ))
        if result[2]:
            if viewer == "owner":
                self.owner_slot_looted = True
            else:
                self.friend_slot_looted = True
        if result[3]:
            self.shared_looted = True
        # Pinned LootView hide path has NO decrement, regardless of who
        # viewed the source.
        return result[1]

    def store(self, viewer):
        local = self.owner_slot_looted if viewer == "owner" else self.friend_slot_looted
        if self.shared_looted or local:
            return False
        self.shared_looted = True
        self.unlooted_count -= 1
        if viewer == "owner":
            self.owner_slot_looted = True
        else:
            self.friend_slot_looted = True
        return True

    def release_owner(self):
        # Only the turn is cleared for a NOT-fully-looted corpse.
        # The model never clears or re-counts this shared item.
        if self.unlooted_count:
            self.round_robin_owner = False

    def is_looted(self):
        return self.unlooted_count == 0



def player_method(text, signature):
    """Exact public-source method slice up to next top-level Player method."""
    i = text.index(signature)
    next_method = re.search(
        r"(?m)^(?:void|bool|Item\*|uint8|uint16|uint32|int|InventoryResult)"
        r"\s+Player::[A-Za-z_]+\(",
        text[i + len(signature):],
    )
    if next_method is None:
        raise AssertionError("next Player method sentinel not found: " + signature)
    return compact(text[i:i + len(signature) + next_method.start()])


@dataclass
class QuestCounterAtReceipt:
    """Synthetic deliver-quest counter model; not a player or owner DB."""
    needed: int
    counted: int = 0
    carried: int = 0

    def accept_existing(self, held):
        self.carried = held
        self.counted = min(held, self.needed)

    def receive_normal(self, count):
        # Source-shaped: ItemAddedQuestCheck updates still-incomplete
        # delivery objectives while StoreNewItem increases actual bags.
        if self.counted < self.needed:
            self.counted = min(self.counted + count, self.needed)
        self.carried += count

    def reload_saved(self, saved_counter, loaded_bags):
        # Deliberately inconsistent persisted state is injected by a test.
        # This does not assert stock normal gameplay creates such rows.
        self.counted = saved_counter
        self.carried = loaded_bags

    def remaining(self):
        return (self.counted < self.needed, self.carried < self.needed)


class PinnedCounterLifecycleContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.storage = read("player_storage")
        cls.quest = read("player_quest")

    def test_quest_accept_reconciles_existing_delivery_items(self):
        add = player_method(self.quest, "void Player::AddQuest(")
        adj = player_method(self.quest, "void Player::AdjustQuestReqItemCount(")
        self.assertIn("AdjustQuestReqItemCount(quest, questStatusData);", add)
        self.assertIn("GetItemCount(quest->RequiredItemId[i], true)", adj)
        self.assertIn("questStatusData.ItemCount[i] = std::min(curitemcount, reqitemcount);", adj)

    def test_ordinary_item_store_calls_quest_check_before_storeitem(self):
        store = player_method(
            self.storage,
            "Item* Player::StoreNewItem(ItemPosCountVec const& dest, "
            "uint32 item, bool update, int32 randomPropertyId, "
            "AllowedLooterSet& allowedLooters, bool refund)"
        )
        self.assertIn("ItemAddedQuestCheck(item, count);", store)
        self.assertIn("pItem = StoreItem(dest, pItem, update);", store)
        self.assertLess(store.index("ItemAddedQuestCheck(item, count);"),
                        store.index("pItem = StoreItem(dest, pItem, update);"))

    def test_item_added_check_updates_counter_and_completes_as_needed(self):
        added = player_method(self.quest, "void Player::ItemAddedQuestCheck(")
        self.assertIn("q_status.Status != QUEST_STATUS_INCOMPLETE", added)
        self.assertIn("qInfo->HasSpecialFlag(QUEST_SPECIAL_FLAGS_DELIVER)", added)
        self.assertIn("q_status.ItemCount[j] = std::min<uint16>(", added)
        self.assertIn("q_status.ItemCount[j] + count, reqitemcount", added)
        self.assertIn("if (CanCompleteQuest(questid)) CompleteQuest(questid);", added)

    def test_inventory_move_in_and_out_use_quest_counter_hooks(self):
        arrive = player_method(self.storage, "Item* Player::MoveItemToInventory(")
        depart = player_method(self.storage, "void Player::MoveItemFromInventory(")
        self.assertIn("ItemAddedQuestCheck(pItem->GetEntry(), pItem->GetCount());", arrive)
        self.assertIn("ItemRemovedQuestCheck(it->GetEntry(), it->GetCount());", depart)

    def test_quest_login_restores_saved_count_without_direct_reconciliation(self):
        loaded = player_method(self.storage, "void Player::_LoadQuestStatus(")
        inventory = player_method(self.storage, "void Player::_LoadInventory(")
        self.assertIn("questStatusData.ItemCount[i] = fields[8 + i].Get<uint16>();", loaded)
        self.assertNotIn("AdjustQuestReqItemCount(", loaded)
        self.assertNotIn("ItemAddedQuestCheck(", loaded)
        self.assertNotIn("ItemAddedQuestCheck(", inventory)
        self.assertNotIn("AdjustQuestReqItemCount(", inventory)
        # Scope limited to these two functions. Other login hooks and
        # custom IP additions have not been excluded.

    def test_quest_need_check_is_counter_gated_before_inventory(self):
        src = player_method(self.quest, "bool Player::HasQuestForItem(")
        self.assertIn("q_status.ItemCount[j] < qinfo->RequiredItemCount[j]", src)
        self.assertIn("if (showInLoot)", src)
        self.assertIn("GetItemCount(itemid, true) < qinfo->RequiredItemCount[j]", src)
        self.assertIn("*showInLoot = false;", src)


class SyntheticCounterFreshnessCases(unittest.TestCase):
    def test_ordinary_completion_does_not_create_short_counter_full_bags(self):
        q = QuestCounterAtReceipt(needed=2)
        q.receive_normal(2)
        self.assertEqual(q.remaining(), (False, False))
        self.assertEqual(
            source_shaped_quest_view(QuestWindowCase(True, True, *q.remaining())),
            (True, "LOCKED", False, False),
        )

    def test_prior_inventory_at_quest_accept_is_counted(self):
        q = QuestCounterAtReceipt(needed=2)
        q.accept_existing(held=2)
        self.assertEqual(q.remaining(), (False, False))

    def test_partial_normal_receipt_keeps_counter_and_bags_in_step(self):
        q = QuestCounterAtReceipt(needed=2)
        q.receive_normal(1)
        self.assertEqual(q.remaining(), (True, True))
        self.assertEqual(
            source_shaped_quest_view(QuestWindowCase(True, True, *q.remaining())),
            (True, "ALLOW", False, False),
        )

    def test_an_injected_prior_stale_saved_counter_reaches_hidden_case(self):
        q = QuestCounterAtReceipt(needed=2)
        q.reload_saved(saved_counter=1, loaded_bags=2)
        self.assertEqual(q.remaining(), (True, False))
        self.assertEqual(
            source_shaped_quest_view(QuestWindowCase(True, True, *q.remaining())),
            (True, "HIDDEN", True, True),
        )

    def test_fresh_counter_and_stale_counter_same_bags_diverge(self):
        fresh = QuestCounterAtReceipt(needed=1)
        fresh.receive_normal(1)
        stale = QuestCounterAtReceipt(needed=1)
        stale.reload_saved(saved_counter=0, loaded_bags=1)
        self.assertEqual(fresh.carried, stale.carried)
        self.assertNotEqual(fresh.remaining(), stale.remaining())
        self.assertEqual(source_shaped_quest_view(
            QuestWindowCase(True, True, *fresh.remaining()))[1], "LOCKED")
        self.assertEqual(source_shaped_quest_view(
            QuestWindowCase(True, True, *stale.remaining()))[1], "HIDDEN")


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


    def test_mismatch_viewed_first_strands_other_eligible_quest_viewer(self):
        corpse = TwoViewerSharedQuest()
        self.assertEqual(corpse.show("owner", objective_short=True, bag_short=False),
                         "HIDDEN")
        self.assertTrue(corpse.shared_looted)
        self.assertTrue(corpse.owner_slot_looted)
        self.assertFalse(corpse.friend_slot_looted)
        self.assertEqual(corpse.unlooted_count, 1)  # stale counter
        self.assertEqual(corpse.show("friend"), "NO_QUEST_ROW")
        self.assertFalse(corpse.store("friend"))
        self.assertFalse(corpse.is_looted())

    def test_releasing_owner_does_not_reopen_suppressed_shared_copy(self):
        corpse = TwoViewerSharedQuest()
        corpse.show("owner", objective_short=True, bag_short=False)
        corpse.release_owner()
        self.assertFalse(corpse.round_robin_owner)
        self.assertTrue(corpse.shared_looted)
        self.assertEqual(corpse.unlooted_count, 1)
        self.assertFalse(corpse.is_looted())
        self.assertFalse(corpse.store("friend"))

    def test_other_eligible_viewer_can_collect_before_mismatch_view(self):
        corpse = TwoViewerSharedQuest()
        self.assertEqual(corpse.show("friend"), "ALLOW")
        self.assertTrue(corpse.store("friend"))
        self.assertEqual(corpse.unlooted_count, 0)
        self.assertTrue(corpse.is_looted())
        # Stock shared one-copy loot is now genuinely consumed; this
        # reference behaviour must not be mistaken for duplication.
        self.assertFalse(corpse.store("owner"))

    def test_objective_completed_locked_row_does_not_suppress_friend(self):
        corpse = TwoViewerSharedQuest()
        self.assertEqual(corpse.show("owner", objective_short=False, bag_short=True),
                         "LOCKED")
        self.assertFalse(corpse.shared_looted)
        self.assertEqual(corpse.unlooted_count, 1)
        self.assertEqual(corpse.show("friend"), "ALLOW")
        self.assertTrue(corpse.store("friend"))
        self.assertTrue(corpse.is_looted())

    def test_no_unapproved_reconciliation_or_extra_copy_in_model(self):
        corpse = TwoViewerSharedQuest()
        self.assertEqual(corpse.show("owner", True, False), "HIDDEN")
        self.assertFalse(corpse.store("owner"))
        self.assertFalse(corpse.store("friend"))
        self.assertEqual(corpse.unlooted_count, 1)
        # A future policy repair must separately define whether stale
        # counts or inventory mismatch should be corrected, with
        # approval and controlled staging. This model changes neither.


if __name__ == "__main__":
    unittest.main(verbosity=2)
