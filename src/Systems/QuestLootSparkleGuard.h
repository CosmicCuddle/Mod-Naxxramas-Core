/*
 * Naxxramas Core - corpse sparkle guard (P4 H2, policy-neutral).
 *
 * Pinned Unit::PatchValuesUpdate sends UNIT_DYNFLAG_LOOTABLE per viewer and
 * clears it only when Player::isAllowedToLoot is false. That test is coarse:
 * Loot::hasItemFor(viewer) is true for any cached quest row, including a
 * stale one the viewer can no longer take (the #262 T3 case: the window shows
 * a LOCKED row and the pickup is denied). So the corpse sparkles for a player
 * who can take nothing.
 *
 * ViewOffersSomething asks the ORIGINAL LootView serializer what this viewer
 * would see and answers false only when the window would hold no gold and no
 * actionable row: no rows at all, or only quest rows marked LOCKED. Normal
 * rows of every slot type (including Master Loot's LOCKED rows), roll rows,
 * FFA copies and gold all count as something, exactly as stock.
 *
 * NON-MUTATING. This runs while a values update is being built, before the
 * player may have opened anything, so it must leave every loot flag exactly
 * as it found it. The pinned serializer writes only two things (LootMgr.cpp
 * L1115 the viewer's own QuestItem row, L1118 the shared item); the view
 * guard helper pre-marks those rows so the serializer skips both writes,
 * and the viewer's own row flags are saved first and restored on return.
 * Net effect on loot state: none (tested by exact snapshots).
 */
#ifndef NAXXRAMAS_QUEST_LOOT_SPARKLE_GUARD_H
#define NAXXRAMAS_QUEST_LOOT_SPARKLE_GUARD_H

#include "QuestLootPickupAuthorization.h"

#include <functional>
#include <utility>
#include <vector>

namespace NaxxramasQuestLootSparkleGuard
{
    inline bool ViewOffersSomething(Player* viewer, Loot& loot, PermissionTypes permission,
        std::function<bool(uint8)> const& deniedPickup = {})
    {
        if (!viewer || permission == NONE_PERMISSION)
            return false;

        // Save the viewer's own row flags; restored on every return below.
        std::vector<std::pair<QuestItem*, bool>> savedRows;
        QuestItemMap const& questLists = loot.GetPlayerQuestItems();
        QuestItemMap::const_iterator own = questLists.find(viewer->GetGUID());
        if (own != questLists.end() && own->second)
            for (QuestItem& row : *own->second)
                savedRows.emplace_back(&row, row.is_looted);
        struct RestoreRows
        {
            std::vector<std::pair<QuestItem*, bool>>& rows;
            ~RestoreRows()
            {
                for (std::pair<QuestItem*, bool>& saved : rows)
                    saved.first->is_looted = saved.second;
            }
        } restore{savedRows};

        NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(viewer, loot);

        ByteBuffer view;
        view << LootView(loot, viewer, permission);
        if (view.read<uint32>() != 0)               // gold
            return true;

        std::size_t const normalRows = loot.items.size();
        uint8 const rows = view.read<uint8>();
        for (uint8 i = 0; i < rows; ++i)
        {
            uint8 const slot = view.read<uint8>();
            view.read_skip(5 * sizeof(uint32));     // item id, count, display, suffix, property
            uint8 const slotType = view.read<uint8>();
            // Normal loot (including locked Master Loot rows) is unchanged.
            // A quest row is actionable only if it isn't LOCKED and the
            // enabled H1 pickup gate would actually allow this viewer.
            if (slot < normalRows)
                return true;
            if (slotType != LOOT_SLOT_TYPE_LOCKED &&
                (!deniedPickup || !deniedPickup(slot)))
                return true;
        }
        return false;
    }
}

#endif
