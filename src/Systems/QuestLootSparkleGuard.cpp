/*
 * Naxxramas Core - corpse sparkle guard script (see the header).
 *
 * Default OFF. Pinned Unit::PatchValuesUpdate calls
 * UnitScript::OnPatchValuesUpdate per viewer after it has set the dynamic
 * flags. This hook can only CLEAR UNIT_DYNFLAG_LOOTABLE for that viewer's
 * packet; it never sets it and never changes the creature's own field.
 * docs/P4-H2-SPARKLE-GUARD.md has the evidence and limits.
 */
#include "Config.h"
#include "Creature.h"
#include "Group.h"
#include "LootMgr.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptDefines/UnitScript.h"
#include "ScriptDefines/WorldScript.h"
#include "UnitUtils.h"
#include "QuestLootSparkleGuard.h"

#include <atomic>

namespace
{
    std::atomic<bool> s_sparkleGuardEnabled{false};
}

class NaxxramasQuestLootSparkleGuardConfig final : public WorldScript
{
public:
    NaxxramasQuestLootSparkleGuardConfig()
        : WorldScript("NaxxramasQuestLootSparkleGuardConfig", {WORLDHOOK_ON_AFTER_CONFIG_LOAD}) { }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        s_sparkleGuardEnabled.store(
            sConfigMgr->GetOption<bool>("NaxxramasCore.QuestLootSparkleGuard.Enabled", false),
            std::memory_order_relaxed);
    }
};

class NaxxramasQuestLootSparkleGuardUnit final : public UnitScript
{
public:
    NaxxramasQuestLootSparkleGuardUnit()
        : UnitScript("NaxxramasQuestLootSparkleGuardUnit", true, {UNITHOOK_ON_PATCH_VALUES_UPDATE}) { }

    void OnPatchValuesUpdate(Unit const* unit, ByteBuffer& buffer, BuildValuesCachePosPointers& positions,
                             Player* target) override
    {
        if (!s_sparkleGuardEnabled.load(std::memory_order_relaxed) || !unit || !target ||
            positions.UnitDynamicFlagsPos < 0)
            return;

        Creature const* corpse = unit->ToCreature();
        if (!corpse || corpse->IsAlive())
            return;

        uint32 const flags = buffer.read<uint32>(std::size_t(positions.UnitDynamicFlagsPos));
        if (!(flags & UNIT_DYNFLAG_LOOTABLE))
            return;  // the core already hides it

        // Corpse loot before anyone opened it (LOOT_NONE) or after (LOOT_CORPSE).
        // Skinning and pickpocket loot stay as stock.
        Loot& loot = const_cast<Creature*>(corpse)->loot;
        if (loot.loot_type != LOOT_CORPSE && loot.loot_type != LOOT_NONE)
            return;

        Group* recipientGroup = corpse->GetLootRecipientGroup();
        PermissionTypes const permission = NaxxramasQuestLootPickupAuthorization::CorpsePermission(
            recipientGroup != nullptr,
            recipientGroup && target->GetGroup() == recipientGroup,
            corpse->GetLootRecipientGUID() == target->GetGUID(),
            recipientGroup ? recipientGroup->GetLootMethod() : FREE_FOR_ALL,
            recipientGroup && recipientGroup->GetMasterLooterGuid() == target->GetGUID());
        if (permission == NONE_PERMISSION)
            return;  // leave the core's decision alone

        if (!NaxxramasQuestLootSparkleGuard::ViewOffersSomething(target, loot, permission))
            buffer.put<uint32>(std::size_t(positions.UnitDynamicFlagsPos), flags & ~uint32(UNIT_DYNFLAG_LOOTABLE));
    }
};

void AddQuestLootSparkleGuardScripts()
{
    new NaxxramasQuestLootSparkleGuardConfig();
    new NaxxramasQuestLootSparkleGuardUnit();
}
