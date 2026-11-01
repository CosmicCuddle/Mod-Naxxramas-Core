/*
 * Naxxramas Core - Master Loot quest-slot give (P4-H, policy-neutral).
 *
 * Pinned WorldSession::HandleLootMasterGiveOpcode (LootHandler.cpp L478-573)
 * resolves a quest slot as quest_items[slot - items.size()], a GLOBAL index,
 * and afterwards calls Loot::NotifyItemRemoved(slot), which sends the
 * leader's slot number to every looter. But the LootView serializer numbers
 * each viewer's quest rows by their position in that viewer's OWN quest list
 * (items.size() + j). So when the leader's list is not a prefix of
 * quest_items the wrong item is given (D1); other looters are told to remove
 * the wrong row (D3); and nothing checks whether the item was already looted,
 * so a copy autostored a moment earlier can be given again (D2).
 *
 * GiveQuestSlot performs the give for QUEST slots only, using:
 *  - the leader's own row, mapped exactly as Loot::LootItemInSlot maps a
 *    requester's slot (without its "allowed for the requester" check: the
 *    leader gives to someone else, and the target is checked as in stock);
 *  - the stock steps in the stock order with the stock error mapping;
 *  - Loot::NotifyQuestItemRemoved(row.index), the per-viewer notification
 *    Player::StoreLootItem uses for the same kind of item.
 * Normal slots return PassThrough and are left to the core. Who may give,
 * and to whom, is decided by the core before this runs (see the .cpp).
 *
 * Header-only so the same code is compiled by the module and by the
 * extracted-pinned-source harness. The includer must provide the LootMgr.h
 * types and a complete Player type.
 */
#ifndef NAXXRAMAS_MASTER_LOOT_QUEST_GIVE_H
#define NAXXRAMAS_MASTER_LOOT_QUEST_GIVE_H

#include "LootMgr.h"

namespace NaxxramasMasterLootQuestGive
{
    enum class Result : uint8
    {
        PassThrough,    // not a quest slot: let the core handle it
        Given,          // item stored on the target, viewers notified
        AlreadyLooted,  // no such row for the leader, or already looted
        Error,          // refused; send `error` to the leader
    };

    struct Outcome
    {
        Result result;
        LootError error;
    };

    inline Outcome GiveQuestSlot(Player* leader, Player* target, Loot& loot, uint8 slot)
    {
        if (slot < loot.items.size())
            return {Result::PassThrough, LOOT_ERROR_DIDNT_KILL};

        // The leader's own row, as Loot::LootItemInSlot finds it.
        std::size_t const questSlot = slot - loot.items.size();
        QuestItemMap const& questLists = loot.GetPlayerQuestItems();
        QuestItemMap::const_iterator own = questLists.find(leader->GetGUID());
        if (own == questLists.end() || !own->second || questSlot >= own->second->size())
            return {Result::AlreadyLooted, LOOT_ERROR_DIDNT_KILL};

        QuestItem& row = own->second->at(questSlot);
        if (row.index >= loot.quest_items.size())
            return {Result::AlreadyLooted, LOOT_ERROR_DIDNT_KILL};
        LootItem& item = loot.quest_items[row.index];
        if (row.is_looted || item.is_looted)
            return {Result::AlreadyLooted, LOOT_ERROR_DIDNT_KILL};

        // Everyone has a personal copy of a free-for-all quest item; the
        // leader is shown it as ALLOW_LOOT, never as a MASTER row.
        if (item.freeforall)
            return {Result::Error, LOOT_ERROR_MASTER_OTHER};

        // Stock order and error mapping (LootHandler.cpp L542-554).
        ItemPosCountVec dest;
        InventoryResult msg = target->CanStoreNewItem(NULL_BAG, NULL_SLOT, dest, item.itemid, item.count);
        if (!item.AllowedForPlayer(target, loot.sourceWorldObjectGUID))
            msg = EQUIP_ERR_YOU_CAN_NEVER_USE_THAT_ITEM;
        if (msg != EQUIP_ERR_OK)
        {
            if (msg == EQUIP_ERR_CANT_CARRY_MORE_OF_THIS)
                return {Result::Error, LOOT_ERROR_MASTER_UNIQUE_ITEM};
            if (msg == EQUIP_ERR_INVENTORY_FULL)
                return {Result::Error, LOOT_ERROR_MASTER_INV_FULL};
            return {Result::Error, LOOT_ERROR_MASTER_OTHER};
        }

        // Stock award steps (LootHandler.cpp L556-569).
        AllowedLooterSet looters = item.GetAllowedLooters();
        Item* newItem = target->StoreNewItem(dest, item.itemid, true, item.randomPropertyId, looters);
        target->SendNewItem(newItem, uint32(item.count), false, false, true);
        target->UpdateLootAchievements(&item, &loot);

        item.count = 0;
        item.is_looted = true;

        // Each looter is told its own slot for this item.
        loot.NotifyQuestItemRemoved(row.index);
        --loot.unlootedCount;
        return {Result::Given, LOOT_ERROR_DIDNT_KILL};
    }
}

#endif
