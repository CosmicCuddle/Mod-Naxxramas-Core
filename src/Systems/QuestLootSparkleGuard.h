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
 * The view guard helper runs first, so serializing writes no shared state;
 * it may only hide the viewer's own quest rows that the core hides from them.
 */
#ifndef NAXXRAMAS_QUEST_LOOT_SPARKLE_GUARD_H
#define NAXXRAMAS_QUEST_LOOT_SPARKLE_GUARD_H

#include "QuestLootPickupAuthorization.h"

namespace NaxxramasQuestLootSparkleGuard
{
    inline bool ViewOffersSomething(Player* viewer, Loot& loot, PermissionTypes permission)
    {
        if (!viewer || permission == NONE_PERMISSION)
            return false;

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
            if (slot < normalRows || slotType != LOOT_SLOT_TYPE_LOCKED)
                return true;
        }
        return false;
    }
}

#endif
