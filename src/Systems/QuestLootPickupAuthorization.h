/*
 * Naxxramas Core - loot pickup authorization (P4 H1, policy-neutral slice).
 *
 * Pinned Player::StoreLootItem awards a normal loot slot without re-checking
 * what the server's own LootView shows that player. A below-threshold item
 * that round robin hides from everyone but the current owner can still be
 * stored by another group member who asks for that slot index (a stale or
 * hand-made CMSG_AUTOSTORE_LOOT_ITEM). This check asks the ORIGINAL LootView
 * serializer which rows the player can see right now and refuses an
 * autostore for a slot that is not one of them. It never refuses a visible
 * slot, so ownership rules stay exactly as the core shows them: round robin,
 * release, FFA copies, Master Loot, rolls, gold and quest eligibility.
 *
 * Header-only so the module and the extracted-pinned-source harness compile
 * the same code. The includer must provide LootMgr.h types, ByteBuffer and a
 * complete Player type.
 */
#ifndef NAXXRAMAS_QUEST_LOOT_PICKUP_AUTHORIZATION_H
#define NAXXRAMAS_QUEST_LOOT_PICKUP_AUTHORIZATION_H

#include "ByteBuffer.h"
#include "LootMgr.h"
#include "QuestLootViewGuard.h"

namespace NaxxramasQuestLootPickupAuthorization
{
    // The non-skinning creature-corpse branch of pinned Player::SendLoot
    // (Player.cpp L8321-L8348), as a pure function of its inputs.
    inline PermissionTypes CorpsePermission(bool hasRecipientGroup, bool inRecipientGroup, bool isRecipient,
                                            LootMethod method, bool isMasterLooter)
    {
        if (hasRecipientGroup)
        {
            if (!inRecipientGroup)
                return NONE_PERMISSION;
            switch (method)
            {
                case MASTER_LOOT:
                    return isMasterLooter ? MASTER_PERMISSION : RESTRICTED_PERMISSION;
                case FREE_FOR_ALL:
                    return ALL_PERMISSION;
                case ROUND_ROBIN:
                    return ROUND_ROBIN_PERMISSION;
                default:
                    return GROUP_PERMISSION;
            }
        }
        return isRecipient ? OWNER_PERMISSION : NONE_PERMISSION;
    }

    // True when 'slot' is one of the rows the original serializer would send
    // to this player now. The view guard runs first, so serializing has no
    // shared side effect (it only hides rows the core hides from this viewer).
    inline bool SlotVisibleInServerView(Player* viewer, Loot& loot, PermissionTypes permission, uint8 slot)
    {
        if (!viewer || permission == NONE_PERMISSION)
            return false;

        NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(viewer, loot);

        ByteBuffer view;
        view << LootView(loot, viewer, permission);
        view.read<uint32>();                       // gold
        uint8 const rows = view.read<uint8>();
        for (uint8 i = 0; i < rows; ++i)
        {
            uint8 const shownSlot = view.read<uint8>();
            view.read_skip(5 * sizeof(uint32));    // item id, count, display, suffix, property
            view.read<uint8>();                    // slot type
            if (shownSlot == slot)
                return true;
        }
        return false;
    }
}

#endif
