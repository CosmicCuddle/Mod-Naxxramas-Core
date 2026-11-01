/*
 * Naxxramas Core - Master Loot quest-slot give script (see the header).
 *
 * Default OFF. Runs from ServerScript::CanPacketReceive for
 * CMSG_LOOT_MASTER_GIVE, which pinned WorldSession::Update calls right before
 * the handler on the same thread (the opcode is PROCESS_THREADSAFE, so both
 * run in the map update). The packet is const, so a wrong quest slot cannot
 * be corrected in place: for a quest slot this script performs the give
 * itself and consumes the packet. Every other request, and every request
 * that fails one of the handler's own checks, goes to the core unchanged.
 * docs/P4-H-MASTER-LOOT-QUEST-GIVE.md has the evidence and limits.
 */
#include "Config.h"
#include "Creature.h"
#include "GameObject.h"
#include "Group.h"
#include "LootMgr.h"
#include "Map.h"
#include "ObjectAccessor.h"
#include "Opcodes.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptDefines/ServerScript.h"
#include "ScriptDefines/WorldScript.h"
#include "WorldPacket.h"
#include "WorldSession.h"
#include "MasterLootQuestGive.h"

#include <atomic>

namespace
{
    std::atomic<bool> s_masterLootQuestGiveEnabled{false};

    // True to let the core handle the request as usual. The checks below are
    // the handler's own, in its order (LootHandler.cpp L485-538); any failure
    // is passed through so the core sends its own error.
    bool PermitMasterGive(Player* leader, ObjectGuid lootGuid, uint8 slot, ObjectGuid targetGuid)
    {
        if (!leader || !leader->IsInWorld() || !leader->GetMap())
            return true;

        Group* group = leader->GetGroup();
        if (!group || group->GetMasterLooterGuid() != leader->GetGUID() || group->GetLootMethod() != MASTER_LOOT)
            return true;

        Player* target = ObjectAccessor::GetPlayer(*leader, targetGuid);
        if (!target)
            return true;

        if (leader->GetLootGUID() != lootGuid)
            return true;

        if (!leader->IsInRaidWith(target) || target->HasPlayerFlag(PLAYER_FLAGS_NO_PLAY_TIME))
            return true;

        Loot* loot = nullptr;
        if (lootGuid.IsCreatureOrVehicle())
        {
            if (Creature* creature = leader->GetMap()->GetCreature(lootGuid))
                loot = &creature->loot;
        }
        else if (lootGuid.IsGameObject())
        {
            if (GameObject* go = leader->GetMap()->GetGameObject(lootGuid))
                loot = &go->loot;
        }
        if (!loot)
            return true;

        // Out of range: the core logs it and ignores it.
        if (slot >= loot->items.size() + loot->quest_items.size())
            return true;

        NaxxramasMasterLootQuestGive::Outcome const outcome =
            NaxxramasMasterLootQuestGive::GiveQuestSlot(leader, target, *loot, slot);
        switch (outcome.result)
        {
            case NaxxramasMasterLootQuestGive::Result::PassThrough:
                return true;
            case NaxxramasMasterLootQuestGive::Result::AlreadyLooted:
                leader->SendEquipError(EQUIP_ERR_ALREADY_LOOTED, nullptr, nullptr);
                return false;
            case NaxxramasMasterLootQuestGive::Result::Error:
                leader->SendLootError(lootGuid, outcome.error);
                return false;
            case NaxxramasMasterLootQuestGive::Result::Given:
                return false;
        }
        return true;
    }
}

class NaxxramasMasterLootQuestGiveConfig final : public WorldScript
{
public:
    NaxxramasMasterLootQuestGiveConfig()
        : WorldScript("NaxxramasMasterLootQuestGiveConfig", {WORLDHOOK_ON_AFTER_CONFIG_LOAD}) { }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        s_masterLootQuestGiveEnabled.store(
            sConfigMgr->GetOption<bool>("NaxxramasCore.MasterLootQuestGive.Enabled", false),
            std::memory_order_relaxed);
    }
};

class NaxxramasMasterLootQuestGivePacket final : public ServerScript
{
public:
    NaxxramasMasterLootQuestGivePacket()
        : ServerScript("NaxxramasMasterLootQuestGivePacket", {SERVERHOOK_CAN_PACKET_RECEIVE}) { }

    bool CanPacketReceive(WorldSession* session, WorldPacket const& packet) override
    {
        // Runs for every opcode: leave everything else immediately.
        if (packet.GetOpcode() != CMSG_LOOT_MASTER_GIVE ||
            !s_masterLootQuestGiveEnabled.load(std::memory_order_relaxed) ||
            !session || !session->GetPlayer() ||
            packet.size() < sizeof(uint64) + sizeof(uint8) + sizeof(uint64))
            return true;

        // Same reads as the handler (lootguid, slotid, target), from a copy.
        WorldPacket copy(packet);
        copy.rpos(0);
        ObjectGuid lootGuid;
        ObjectGuid targetGuid;
        uint8 slot = 0;
        copy >> lootGuid >> slot >> targetGuid;
        return PermitMasterGive(session->GetPlayer(), lootGuid, slot, targetGuid);
    }
};

void AddMasterLootQuestGiveScripts()
{
    new NaxxramasMasterLootQuestGiveConfig();
    new NaxxramasMasterLootQuestGivePacket();
}
