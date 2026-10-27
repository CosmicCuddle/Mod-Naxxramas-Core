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

#include "QuestLootNormalSlotPolicy.h"

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

    // Separately gated experimental stock-loot visibility/award parity.
    // Remains OFF even when the existing QuestLootProtection master is ON.
    bool RestrictHiddenOrdinarySlots()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.QuestLootProtection.RestrictHiddenOrdinarySlots", false);
    }

    // Return true to leave this request to normal AzerothCore validation.
    // The legacy one-copy quest-turn guard and the new ordinary hidden-slot
    // parity candidate have INDEPENDENT default-OFF switches. Neither
    // requires enabling the other; all supported source/method checks stay.
    bool PermitPickup(Player* player, uint8 requestedSlot,
        bool legacyQuestTurnEnabled, bool hiddenOrdinarySlotEnabled)
    {
        if (!player || !player->IsInWorld() || !player->GetMap())
            return true;

        Group* group = player->GetGroup();
        if (!group)
            return true;

        switch (group->GetLootMethod())
        {
            case GROUP_LOOT:
            case ROUND_ROBIN:
            case NEED_BEFORE_GREED:
                break;
            // Do not override the native FFA, Master Loot or other modes.
            default:
                return true;
        }

        ObjectGuid const sourceGuid = player->GetLootGUID();
        if (!sourceGuid.IsCreatureOrVehicle())
            return true;

        Creature* creature = player->GetMap()->GetCreature(sourceGuid);
        if (!creature || !creature->isDead() ||
            !creature->IsWithinDistInMap(player, INTERACTION_DISTANCE) ||
            creature->GetLootRecipientGroup() != group)
            return true;

        Loot const& loot = creature->loot;
        if (loot.loot_type != LOOT_CORPSE ||
            !loot.roundRobinPlayer ||
            loot.roundRobinPlayer == player->GetGUID())
            return true;

        // The first N slots are normal items. Quest slots are viewer-
        // specific: never index quest_items with the client slot directly.
        std::size_t const normalCount = loot.items.size();
        if (requestedSlot < normalCount)
        {
            // REVIEW-ONLY candidate: there is a native difference between
            // ordinary-item loot window visibility and its store-time check.
            // Never reinterpret normal quest-collection items as personal.
            if (!hiddenOrdinarySlotEnabled)
                return true;

            LootItem const& item = loot.items[requestedSlot];
            // Restrict the pilot to the requester's live map. AzerothCore
            // warns that global FindPlayer access is not thread-safe across
            // maps; no cross-map owner fields may be inspected here.
            // A departed/other-map owner fails open to native handling.
            Player* turnOwner = ObjectAccessor::GetPlayer(*player, loot.roundRobinPlayer);
            bool ownerLiveHere = false;
            if (turnOwner && turnOwner->IsInWorld() &&
                turnOwner->GetGroup() == group)
            {
                Map const* ownerMap = turnOwner->FindMap();
                Map const* requesterMap = player->FindMap();
                Map const* sourceMap = creature->FindMap();
                ownerLiveHere = ownerMap && ownerMap == requesterMap &&
                    ownerMap == sourceMap &&
                    turnOwner->GetInstanceId() == player->GetInstanceId() &&
                    turnOwner->GetInstanceId() == creature->GetInstanceId();
            }

            namespace NormalSlot = NaxxramasQuestLootNormalSlotPolicy;
            NormalSlot::Facts facts;
            facts.Enabled = true;
            switch (group->GetLootMethod())
            {
                case ROUND_ROBIN:
                    facts.Method = NormalSlot::GroupMethod::RoundRobin;
                    break;
                case GROUP_LOOT:
                    facts.Method = NormalSlot::GroupMethod::GroupLoot;
                    break;
                case NEED_BEFORE_GREED:
                    facts.Method = NormalSlot::GroupMethod::NeedBeforeGreed;
                    break;
                default:
                    facts.Method = NormalSlot::GroupMethod::Other;
                    break;
            }

            facts.HasActiveTurn = bool(loot.roundRobinPlayer);
            facts.RequesterHoldsTurn =
                loot.roundRobinPlayer == player->GetGUID();
            facts.OwnerPresentInSameGroupAndMap = ownerLiveHere;
            facts.OrdinarySlotExists = true;
            facts.IsLooted = item.is_looted;
            facts.IsFreeForAllItem = item.freeforall;
            facts.HasConditions = !item.conditions.empty();
            facts.IsBlocked = item.is_blocked;
            facts.HasRollWinner = bool(item.rollWinnerGUID);
            facts.IsUnderThreshold = item.is_underthreshold;
            facts.FollowsSpecialLootRules = item.follow_loot_rules;

            if (!NormalSlot::RejectHiddenOrdinarySlot(facts))
                return true;

            // Only suppress a request for an ordinary slot that the
            // stock per-viewer permission would hide. Native remains
            // authoritative for all visible and unsupported slots.
            if (Debug())
                LOG_INFO("module",
                    "QuestLootProtection: hidden ordinary item request "
                    "player {} creature {} item {} slot {} owner {}",
                    player->GetGUID().GetCounter(), creature->GetEntry(),
                    item.itemid, uint32(requestedSlot),
                    loot.roundRobinPlayer.GetCounter());

            player->SendLootError(sourceGuid, LOOT_ERROR_LOCKED);
            return false;
        }

        // A stock-compatible ordinary-slot pilot must NOT implicitly arm
        // the older, non-stock one-copy quest-turn protection.
        if (!legacyQuestTurnEnabled)
            return true;

        auto const& personal = loot.GetPlayerQuestItems();
        auto const found = personal.find(player->GetGUID());
        if (found == personal.end() || !found->second)
            return true;

        std::size_t const personalSlot = requestedSlot - normalCount;
        if (personalSlot >= found->second->size())
            return true;

        QuestItem const& view = found->second->at(personalSlot);
        if (view.is_looted || view.index >= loot.quest_items.size())
            return true;

        LootItem const& item = loot.quest_items[view.index];
        // Deliberately narrow: only one-copy, already generated quest loot.
        // ITEM_FLAG_MULTI_DROP maps to freeforall in LootItem's constructor.
        // follow_loot_rules, rolls and blocked slots stay core-owned.
        if (!item.needs_quest || item.count != 1 || item.is_looted ||
            item.freeforall || item.follow_loot_rules ||
            item.is_blocked || item.rollWinnerGUID)
            return true;

        ItemTemplate const* proto = sObjectMgr->GetItemTemplate(item.itemid);
        if (!proto || proto->HasFlag(ITEM_FLAG_MULTI_DROP))
            return true;

        // Never cache ownership: LootHandler clears roundRobinPlayer when
        // its owner releases the corpse. A departed or offline owner cannot
        // be assumed to still control an active loot turn.
        //
        // Fail open. Deny another looter only when the owner is found,
        // IsInWorld(), and on the same live map and the same instance as
        // the looter and this corpse. Use the already-reviewed #132
        // map-scoped GetPlayer rather than cross-map global FindPlayer;
        // a missing or other-map owner still defers to native loot.
        // GetPlayer itself may read IsInWorld()/GetMap() after its global
        // lookup lock has been released; this change reduces, but does
        // not prove the absence of, concurrency races at eight map threads.
        // Pinned AllowedForPlayer does not test map, instance, or range;
        // an owner who left the instance must not strand this item.
        //
        // Distance and death are not extra denies. A dead owner who is
        // still in world on this map and instance keeps the turn. The
        // looter is already inside INTERACTION_DISTANCE; an owner who is
        // elsewhere in the same instance remains the round-robin owner.
        Player* owner = ObjectAccessor::GetPlayer(*player, loot.roundRobinPlayer);
        if (!owner || owner->GetGroup() != group)
            return true;

        if (!owner->IsInWorld())
            return true;

        Map const* ownerMap = owner->FindMap();
        Map const* looterMap = player->FindMap();
        Map const* corpseMap = creature->FindMap();
        if (!ownerMap || !looterMap || !corpseMap)
            return true;

        // Different continent or dungeon. Map id is compared on the live
        // map objects, not on a cached id from when the loot was built.
        if (ownerMap != looterMap || ownerMap != corpseMap ||
            ownerMap->GetId() != looterMap->GetId() ||
            ownerMap->GetId() != corpseMap->GetId())
            return true;

        // Same map id, different instance (a second copy of this dungeon).
        if (owner->GetInstanceId() != player->GetInstanceId() ||
            owner->GetInstanceId() != creature->GetInstanceId() ||
            ownerMap->GetInstanceId() != looterMap->GetInstanceId() ||
            ownerMap->GetInstanceId() != corpseMap->GetInstanceId())
            return true;

        // Only protect an owner who was actually given an unlooted
        // player-specific quest slot for this corpse. FillLoot populates
        // those views only for eligible group members in reward range.
        // A remote, ineligible or already-finished owner must not leave
        // a quest item unnecessarily locked for a valid group member.
        auto const ownerView = personal.find(owner->GetGUID());
        if (ownerView == personal.end() || !ownerView->second)
            return true;

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
            return true;

        // Do not strand a quest drop if the owner no longer needs it or
        // fails native item eligibility. Let AzerothCore decide fallback.
        if (!owner->HasQuestForItem(item.itemid) ||
            !item.AllowedForPlayer(owner, loot.sourceWorldObjectGUID))
            return true;

        // Reject BEFORE Player::StoreLootItem modifies inventory or loot.
        // This does not alter the original packet or shared loot state.
        // Debug flag is the explicit logging gate; INFO avoids requiring
        // an unrelated global logger-level change to see denied pickups.
        if (Debug())
            LOG_INFO("module",
                "QuestLootProtection: blocked player {} creature entry {} guid {} "
                "item {} slot {} owner {} reason=active_owner_still_eligible",
                player->GetGUID().GetCounter(), creature->GetEntry(),
                creature->GetGUID().GetCounter(), item.itemid,
                uint32(requestedSlot), loot.roundRobinPlayer.GetCounter());

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
            !session || !session->GetPlayer() || packet.size() < 1)
            return true;

        bool const legacyQuestTurnEnabled = NaxxramasQuestLootProtection::Enabled();
        bool const hiddenOrdinarySlotEnabled =
            NaxxramasQuestLootProtection::RestrictHiddenOrdinarySlots();
        if (!legacyQuestTurnEnabled && !hiddenOrdinarySlotEnabled)
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
            session->GetPlayer(), requestedSlot,
            legacyQuestTurnEnabled, hiddenOrdinarySlotEnabled);
    }
};

void AddQuestLootProtectionScripts()
{
    new NaxxramasQuestLootProtectionScript();
}
