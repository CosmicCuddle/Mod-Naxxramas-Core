/*
 * Naxxramas Core - loot pickup authorization script (see the header).
 *
 * Default OFF. Runs from ServerScript::CanPacketReceive for
 * CMSG_AUTOSTORE_LOOT_ITEM, which pinned WorldSession::Update calls right
 * before the handler, on the same map thread (the opcode is PROCESS_INPLACE).
 * Only creature corpse loot is checked; everything else is left to the core.
 * docs/P4-H1-PICKUP-AUTHORIZATION.md has the evidence and limits.
 */
#include "Config.h"
#include "Creature.h"
#include "Group.h"
#include "LootMgr.h"
#include "Map.h"
#include "Opcodes.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptDefines/ServerScript.h"
#include "ScriptDefines/WorldScript.h"
#include "WorldPacket.h"
#include "WorldSession.h"
#include "QuestLootPickupAuthorization.h"

#include <atomic>

namespace
{
    std::atomic<bool> s_pickupAuthorizationEnabled{false};

    // True to let the core handle the request as usual.
    bool PermitAutostore(Player* player, uint8 requestedSlot)
    {
        if (!player || !player->IsInWorld() || !player->GetMap())
            return true;

        ObjectGuid const lootGuid = player->GetLootGUID();
        if (!lootGuid.IsCreatureOrVehicle())
            return true;

        Creature* creature = player->GetMap()->GetCreature(lootGuid);
        if (!creature || creature->IsAlive())
            return true;

        Loot& loot = creature->loot;
        if (loot.loot_type != LOOT_CORPSE)
            return true;

        Group* recipientGroup = creature->GetLootRecipientGroup();
        PermissionTypes const permission = NaxxramasQuestLootPickupAuthorization::CorpsePermission(
            recipientGroup != nullptr,
            recipientGroup && player->GetGroup() == recipientGroup,
            creature->GetLootRecipientGUID() == player->GetGUID(),
            recipientGroup ? recipientGroup->GetLootMethod() : FREE_FOR_ALL,
            recipientGroup && recipientGroup->GetMasterLooterGuid() == player->GetGUID());

        // No loot rights at all: the core already refuses; do not add a reply.
        if (permission == NONE_PERMISSION)
            return true;

        if (NaxxramasQuestLootPickupAuthorization::SlotVisibleInServerView(player, loot, permission, requestedSlot))
            return true;

        player->SendLootError(lootGuid, LOOT_ERROR_LOCKED);
        return false;
    }
}

class NaxxramasQuestLootPickupAuthorizationConfig final : public WorldScript
{
public:
    NaxxramasQuestLootPickupAuthorizationConfig()
        : WorldScript("NaxxramasQuestLootPickupAuthorizationConfig", {WORLDHOOK_ON_AFTER_CONFIG_LOAD}) { }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        s_pickupAuthorizationEnabled.store(
            sConfigMgr->GetOption<bool>("NaxxramasCore.QuestLootPickupAuthorization.Enabled", false),
            std::memory_order_relaxed);
    }
};

class NaxxramasQuestLootPickupAuthorizationPacket final : public ServerScript
{
public:
    NaxxramasQuestLootPickupAuthorizationPacket()
        : ServerScript("NaxxramasQuestLootPickupAuthorizationPacket", {SERVERHOOK_CAN_PACKET_RECEIVE}) { }

    bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override
    {
        // Runs for every opcode: leave everything else immediately.
        if (packet.GetOpcode() != CMSG_AUTOSTORE_LOOT_ITEM ||
            !s_pickupAuthorizationEnabled.load(std::memory_order_relaxed) ||
            !session || !session->GetPlayer() || packet.size() < 1)
            return true;

        // Read the slot from a copy, as QuestLootProtection does; the core
        // handler reads one uint8 and ignores trailing bytes.
        WorldPacket copy(packet);
        copy.rpos(0);
        uint8 requestedSlot = 0;
        copy >> requestedSlot;
        return PermitAutostore(session->GetPlayer(), requestedSlot);
    }
};

void AddQuestLootPickupAuthorizationScripts()
{
    new NaxxramasQuestLootPickupAuthorizationConfig();
    new NaxxramasQuestLootPickupAuthorizationPacket();
}
