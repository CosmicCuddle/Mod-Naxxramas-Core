/*
 * Naxxramas Core - temporary creature quest loot turn protection.
 *
 * Packet-only, read-only validation before the native autostore handler.
 * Never alter Loot::roundRobinPlayer, quest slots, item state or awards.
 * See docs/QUEST-LOOT-PROTECTION.md for compatibility and test limits.
 */
#include "Config.h"
#include "Creature.h"
#include "Group.h"
#include "ItemTemplate.h"
#include "Log.h"
#include "LootMgr.h"
#include "Map.h"
#include "ObjectAccessor.h"
#include "ObjectMgr.h"
#include "Opcodes.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptDefines/ServerScript.h"
#include "WorldPacket.h"
#include "WorldSession.h"
#include "QuestLootTurnGuard.h"

namespace NaxxramasQuestLootProtection
{
    bool Enabled()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.QuestLootProtection.Enabled", false);
    }

    bool Debug()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.QuestLootProtection.Debug", false);
    }

    // Same narrow eligibility used by real autostore AND per-viewer H2.
    // No loot/player writes, logging, packet sends or GetLootGUID access.
    bool WouldDenyQuestSlotForViewer(Player* player, Creature* creature, uint8 requestedSlot)
    {
        if (!player || !creature || !player->IsInWorld() || !player->GetMap())
            return false;

        Group* group = player->GetGroup();
        if (!group)
            return false;

        switch (group->GetLootMethod())
        {
            case GROUP_LOOT:
            case ROUND_ROBIN:
            case NEED_BEFORE_GREED:
                break;
            // Do not override the native FFA, Master Loot or other modes.
            default:
                return false;
        }

        // Caller supplies the corpse: passive per-viewer sparkle updates
        // occur before a client has a GetLootGUID. Only the real pickup
        // wrapper checks that GUID and interaction distance.
        if (!creature->isDead() || creature->GetLootRecipientGroup() != group)
            return false;

        Loot const& loot = creature->loot;
        if (loot.loot_type != LOOT_CORPSE ||
            !loot.roundRobinPlayer ||
            loot.roundRobinPlayer == player->GetGUID())
            return false;

        // The first N slots are normal items. Quest slots are viewer-
        // specific: never index quest_items with the client slot directly.
        std::size_t const normalCount = loot.items.size();
        if (requestedSlot < normalCount)
            return false;

        auto const& personal = loot.GetPlayerQuestItems();
        auto const found = personal.find(player->GetGUID());
        if (found == personal.end() || !found->second)
            return false;

        std::size_t const personalSlot = requestedSlot - normalCount;
        if (personalSlot >= found->second->size())
            return false;

        QuestItem const& view = found->second->at(personalSlot);
        if (view.is_looted || view.index >= loot.quest_items.size())
            return false;

        LootItem const& item = loot.quest_items[view.index];
        // Deliberately narrow: only one-copy, already generated quest loot.
        // ITEM_FLAG_MULTI_DROP maps to freeforall in LootItem's constructor.
        // follow_loot_rules, rolls and blocked slots stay core-owned.
        if (!item.needs_quest || item.count != 1 || item.is_looted ||
            item.freeforall || item.follow_loot_rules ||
            item.is_blocked || item.rollWinnerGUID)
            return false;

        ItemTemplate const* proto = sObjectMgr->GetItemTemplate(item.itemid);
        if (!proto || proto->HasFlag(ITEM_FLAG_MULTI_DROP))
            return false;

        // Never cache ownership: LootHandler clears roundRobinPlayer when
        // its owner releases the corpse. A departed or offline owner cannot
        // be assumed to still control an active loot turn.
        //
        // Fail open. Deny another looter only when the owner is found,
        // IsInWorld(), and on the same live map and the same instance as
        // the looter and this corpse. Pinned FindPlayer returns nullptr
        // unless the player is already in world, and the explicit
        // IsInWorld() test stays on the pointer we would deny for: GetMap()
        // asserts when the player has no map. Pinned AllowedForPlayer does
        // not test map, instance, or range, so a still-grouped owner who
        // left the instance must not strand this one-copy quest item.
        //
        // Distance and death are not extra denies. A dead owner who is
        // still in world on this map and instance keeps the turn. The
        // looter is already inside INTERACTION_DISTANCE; an owner who is
        // elsewhere in the same instance remains the round-robin owner.
        Player* owner = ObjectAccessor::FindPlayer(loot.roundRobinPlayer);
        if (!owner || owner->GetGroup() != group)
            return false;

        if (!owner->IsInWorld())
            return false;

        Map const* ownerMap = owner->FindMap();
        Map const* looterMap = player->FindMap();
        Map const* corpseMap = creature->FindMap();
        if (!ownerMap || !looterMap || !corpseMap)
            return false;

        // Different continent or dungeon. Map id is compared on the live
        // map objects, not on a cached id from when the loot was built.
        if (ownerMap != looterMap || ownerMap != corpseMap ||
            ownerMap->GetId() != looterMap->GetId() ||
            ownerMap->GetId() != corpseMap->GetId())
            return false;

        // Same map id, different instance (a second copy of this dungeon).
        if (owner->GetInstanceId() != player->GetInstanceId() ||
            owner->GetInstanceId() != creature->GetInstanceId() ||
            ownerMap->GetInstanceId() != looterMap->GetInstanceId() ||
            ownerMap->GetInstanceId() != corpseMap->GetInstanceId())
            return false;

        // Only protect an owner who was actually given an unlooted
        // player-specific quest slot for this corpse. FillLoot populates
        // those views only for eligible group members in reward range.
        // A remote, ineligible or already-finished owner must not leave
        // a quest item unnecessarily locked for a valid group member.
        auto const ownerView = personal.find(owner->GetGUID());
        if (ownerView == personal.end() || !ownerView->second)
            return false;

        bool ownerHasUnlootedSlot = false;
        for (QuestItem const& ownerItem : *ownerView->second)
        {
            if (ownerItem.index == view.index && !ownerItem.is_looted)
            {
                ownerHasUnlootedSlot = true;
                break;
            }
        }
        if (!ownerHasUnlootedSlot)
            return false;

        // Do not strand a quest drop if the owner no longer needs it or
        // fails native item eligibility. Let AzerothCore decide fallback.
        if (!owner->HasQuestForItem(item.itemid) ||
            !item.AllowedForPlayer(owner, loot.sourceWorldObjectGUID))
            return false;

        return true; // a known, still-eligible owner holds this one copy
    }

    // Keep original live packet identity/range and denial side effects.
    bool PermitPickup(Player* player, uint8 requestedSlot)
    {
        if (!player || !player->IsInWorld() || !player->GetMap())
            return true;

        ObjectGuid const sourceGuid = player->GetLootGUID();
        if (!sourceGuid.IsCreatureOrVehicle())
            return true;
        Creature* creature = player->GetMap()->GetCreature(sourceGuid);
        if (!creature || !creature->isDead() ||
            !creature->IsWithinDistInMap(player, INTERACTION_DISTANCE))
            return true;
        if (!WouldDenyQuestSlotForViewer(player, creature, requestedSlot))
            return true;

        if (Debug())
        {
            Loot const& loot = creature->loot;
            auto const& personal = loot.GetPlayerQuestItems();
            auto const found = personal.find(player->GetGUID());
            // The shared predicate has already checked these bounds.
            QuestItem const& view = found->second->at(requestedSlot - loot.items.size());
            LootItem const& item = loot.quest_items[view.index];
            LOG_INFO("module",
                "QuestLootProtection: blocked player {} creature entry {} guid {} "
                "item {} slot {} owner {} reason=active_owner_still_eligible",
                player->GetGUID().GetCounter(), creature->GetEntry(),
                creature->GetGUID().GetCounter(), item.itemid,
                uint32(requestedSlot), loot.roundRobinPlayer.GetCounter());
        }

        player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED);
        return false;
    }
}

class NaxxramasQuestLootProtectionScript final : public ServerScript
{
public:
    NaxxramasQuestLootProtectionScript()
        : ServerScript("NaxxramasQuestLootProtection",
            {SERVERHOOK_CAN_PACKET_RECEIVE}) { }

    bool CanPacketReceive(WorldSession* session,
        WorldPacket const& packet) override
    {
        // The hook runs for every incoming opcode. Fast-exit unrelated
        // packets before any ConfigMgr lookup or WorldSession inspection.
        if (packet.GetOpcode() != CMSG_AUTOSTORE_LOOT_ITEM ||
            !NaxxramasQuestLootProtection::Enabled() ||
            !session || !session->GetPlayer() || packet.size() < 1)
            return true;

        // WorldPacket(copy) preserves the caller's original read cursor.
        // Native Grimfeather autostore reads a single uint8 slot and does
        // not reject extra trailing bytes. Checking size == 1 here would
        // create a bypass: inspect the first byte if at least one exists.
        // Empty packets remain the core's responsibility.
        WorldPacket copy(packet);
        copy.rpos(0);
        uint8 requestedSlot = 0;
        copy >> requestedSlot;
        return NaxxramasQuestLootProtection::PermitPickup(
            session->GetPlayer(), requestedSlot);
    }
};

void AddQuestLootProtectionScripts()
{
    new NaxxramasQuestLootProtectionScript();
}
