/*
 * Naxxramas Core - quest loot view guard (policy-neutral P4 fix).
 *
 * Pinned AzerothCore operator<<(ByteBuffer&, LootView const&) hides a quest
 * row from a viewer whose HasQuestForItem(..., &showInLoot) is false with
 * showInLoot == false (the viewer already owns enough, counting the bank).
 * For a single-copy (non-FFA) item it then ALSO sets the shared
 * LootItem::is_looted, without any award and without lowering
 * unlootedCount. Another eligible player then loses the item and the corpse
 * never finishes looting.
 *
 * This guard runs from PlayerScript::OnPlayerBeforeSendLoot, which pinned
 * Player::SendLoot calls immediately before it serializes the LootView. It
 * applies the same test to the viewer's own quest rows and marks only that
 * viewer's QuestItem::is_looted. The serializer then skips those rows (it
 * only examines rows that are not yet looted), so the viewer sees exactly
 * what the core would show, and the shared flag is never written by a view.
 * No award, count, round robin, FFA, Master Loot, roll or gold state changes.
 *
 * Header-only so the same code is compiled by the module and by the
 * extracted-pinned-source test harness. The includer must provide the
 * LootMgr.h types and a complete Player type.
 */
#ifndef NAXXRAMAS_QUEST_LOOT_VIEW_GUARD_H
#define NAXXRAMAS_QUEST_LOOT_VIEW_GUARD_H

#include "LootMgr.h"

namespace NaxxramasQuestLootViewGuard
{
    // Returns how many of the viewer's own rows were marked looted.
    inline uint32 HideOwnSatisfiedQuestRows(Player* viewer, Loot& loot)
    {
        if (!viewer)
            return 0;

        QuestItemMap const& questLists = loot.GetPlayerQuestItems();
        QuestItemMap::const_iterator list = questLists.find(viewer->GetGUID());
        if (list == questLists.end() || !list->second)
            return 0;

        uint32 marked = 0;
        for (QuestItem& row : *list->second)
        {
            // The core serializer only looks at rows where neither flag is set.
            if (row.is_looted || row.index >= loot.quest_items.size())
                continue;

            LootItem const& item = loot.quest_items[row.index];
            if (item.is_looted)
                continue;

            bool showInLoot = true;
            bool const hasQuestForItem = viewer->HasQuestForItem(item.itemid, 0, false, &showInLoot);
            if (!hasQuestForItem && !showInLoot)
            {
                row.is_looted = true;
                ++marked;
            }
        }
        return marked;
    }
}

#endif
