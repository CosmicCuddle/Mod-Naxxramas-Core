/*
 * Naxxramas Core - quest loot view guard script (see QuestLootViewGuard.h).
 *
 * Default OFF. The config value is read once on the world thread after each
 * config load and published through an atomic; the map-thread loot hook only
 * reads the atomic. docs/P4-QUEST-LOOT-VIEW-GUARD.md has the evidence and limits.
 */
#include "Config.h"
#include "LootMgr.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptDefines/PlayerScript.h"
#include "ScriptDefines/WorldScript.h"
#include "QuestLootViewGuard.h"

#include <atomic>

namespace
{
    std::atomic<bool> s_viewGuardEnabled{false};
}

class NaxxramasQuestLootViewGuardConfig final : public WorldScript
{
public:
    NaxxramasQuestLootViewGuardConfig()
        : WorldScript("NaxxramasQuestLootViewGuardConfig", {WORLDHOOK_ON_AFTER_CONFIG_LOAD}) { }

    void OnAfterConfigLoad(bool /*reload*/) override
    {
        s_viewGuardEnabled.store(
            sConfigMgr->GetOption<bool>("NaxxramasCore.QuestLootViewGuard.Enabled", false),
            std::memory_order_relaxed);
    }
};

class NaxxramasQuestLootViewGuardPlayer final : public PlayerScript
{
public:
    NaxxramasQuestLootViewGuardPlayer()
        : PlayerScript("NaxxramasQuestLootViewGuardPlayer", {PLAYERHOOK_ON_BEFORE_SEND_LOOT}) { }

    // Pinned Player::SendLoot calls this right before serializing the LootView.
    void OnPlayerBeforeSendLoot(Player* player, ObjectGuid /*lootGuid*/, Loot* loot) override
    {
        if (!loot || !s_viewGuardEnabled.load(std::memory_order_relaxed))
            return;

        NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(player, *loot);
    }
};

void AddQuestLootViewGuardScripts()
{
    new NaxxramasQuestLootViewGuardConfig();
    new NaxxramasQuestLootViewGuardPlayer();
}
