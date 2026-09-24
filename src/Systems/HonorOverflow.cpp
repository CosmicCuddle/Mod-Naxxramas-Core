/*
 * Naxxramas Core
 *
 * Honor Overflow
 *
 * Converts Honor earned above the configured AzerothCore Honor cap
 * into gold at a configurable conversion rate.
 */

#include "Chat.h"
#include "Config.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "World.h"

#if __has_include("Playerbots.h")
#include "Playerbots.h"
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 1
#else
#define NAXXRAMAS_CORE_HAS_PLAYERBOTS 0
#endif

#include <algorithm>
#include <sstream>
#include <unordered_map>

namespace
{
    bool HonorOverflowEnabled = true;
    uint32 HonorOverflowCopperPerHonor = 10;
    bool HonorOverflowNotify = true;
    bool HonorOverflowIncludeBots = false;

    struct HonorSnapshot
    {
        uint32 Honor = 0;
        uint32 TodayContribution = 0;
    };

    std::unordered_map<ObjectGuid::LowType, HonorSnapshot> HonorSnapshots;

    bool IsPlayerBot(Player* player)
    {
#if NAXXRAMAS_CORE_HAS_PLAYERBOTS
        return GET_PLAYERBOT_AI(player) != nullptr;
#else
        return false;
#endif
    }

    std::string FormatMoney(uint32 copper)
    {
        uint32 gold = copper / GOLD;
        copper %= GOLD;

        uint32 silver = copper / SILVER;
        copper %= SILVER;

        std::ostringstream output;
        bool hasValue = false;

        if (gold > 0)
        {
            output << gold << " Gold";
            hasValue = true;
        }

        if (silver > 0)
        {
            if (hasValue)
                output << " ";

            output << silver << " Silver";
            hasValue = true;
        }

        if (copper > 0 || !hasValue)
        {
            if (hasValue)
                output << " ";

            output << copper << " Copper";
        }

        return output.str();
    }

    void StoreHonorSnapshot(Player* player)
    {
        HonorSnapshots[player->GetGUID().GetCounter()] =
        {
            player->GetHonorPoints(),
            player->GetUInt32Value(PLAYER_FIELD_TODAY_CONTRIBUTION)
        };
    }
}

class NaxxramasCoreHonorOverflowConfig : public WorldScript
{
public:
    NaxxramasCoreHonorOverflowConfig()
        : WorldScript("NaxxramasCoreHonorOverflowConfig",
        {
            WORLDHOOK_ON_BEFORE_CONFIG_LOAD
        })
    {
    }

    void OnBeforeConfigLoad(bool /*reload*/) override
    {
        HonorOverflowEnabled =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.HonorOverflow.Enabled",
                true);

        HonorOverflowCopperPerHonor =
            sConfigMgr->GetOption<uint32>(
                "NaxxramasCore.HonorOverflow.CopperPerHonor",
                10);

        HonorOverflowNotify =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.HonorOverflow.Notify",
                true);

        HonorOverflowIncludeBots =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.HonorOverflow.IncludeBots",
                false);
    }
};

class NaxxramasCoreHonorOverflowPlayer : public PlayerScript
{
public:
    NaxxramasCoreHonorOverflowPlayer()
        : PlayerScript("NaxxramasCoreHonorOverflowPlayer",
        {
            PLAYERHOOK_ON_LOGIN,
            PLAYERHOOK_ON_LOGOUT,
            PLAYERHOOK_ON_UPDATE
        })
    {
    }

    void OnPlayerLogin(Player* player) override
    {
        StoreHonorSnapshot(player);
    }

    void OnPlayerLogout(Player* player) override
    {
        HonorSnapshots.erase(player->GetGUID().GetCounter());
    }

    void OnPlayerUpdate(Player* player, uint32 /*diff*/) override
    {
        if (!player)
            return;

        ObjectGuid::LowType guid = player->GetGUID().GetCounter();

        uint32 currentHonor = player->GetHonorPoints();
        uint32 currentTodayContribution =
            player->GetUInt32Value(PLAYER_FIELD_TODAY_CONTRIBUTION);

        auto itr = HonorSnapshots.find(guid);

        if (itr == HonorSnapshots.end())
        {
            StoreHonorSnapshot(player);
            return;
        }

        HonorSnapshot previous = itr->second;

        // Update the snapshot immediately so every server update starts
        // from the latest known values.
        itr->second.Honor = currentHonor;
        itr->second.TodayContribution = currentTodayContribution;

        if (!HonorOverflowEnabled || HonorOverflowCopperPerHonor == 0)
            return;

        if (!HonorOverflowIncludeBots && IsPlayerBot(player))
            return;

        uint32 earnedHonor = 0;

        // Normal case.
        if (currentTodayContribution >= previous.TodayContribution)
        {
            earnedHonor =
                currentTodayContribution - previous.TodayContribution;
        }
        // Daily Honor contribution reset.
        else
        {
            earnedHonor = currentTodayContribution;
        }

        if (earnedHonor == 0)
            return;

        uint32 maxHonor =
            sWorld->getIntConfig(CONFIG_MAX_HONOR_POINTS);

        // Nothing is overflow unless the character has actually reached
        // the configured Honor cap.
        if (currentHonor < maxHonor)
            return;

        uint32 storedHonorIncrease = 0;

        if (currentHonor > previous.Honor)
            storedHonorIncrease = currentHonor - previous.Honor;

        storedHonorIncrease =
            std::min(storedHonorIncrease, earnedHonor);

        uint32 excessHonor =
            earnedHonor - storedHonorIncrease;

        if (excessHonor == 0)
            return;

        uint64 requestedCopper =
            uint64(excessHonor) * HonorOverflowCopperPerHonor;

        uint64 availableMoney =
            player->GetMoney() < MAX_MONEY_AMOUNT
                ? uint64(MAX_MONEY_AMOUNT) - player->GetMoney()
                : 0;

        uint32 rewardCopper =
            uint32(std::min(requestedCopper, availableMoney));

        if (rewardCopper > 0)
            player->ModifyMoney(static_cast<int32>(rewardCopper));

        if (!HonorOverflowNotify || !player->GetSession())
            return;

        if (rewardCopper == 0)
        {
            ChatHandler(player->GetSession()).PSendSysMessage(
                "Your Honor is capped, but no gold could be added because you are at the gold cap.");

            return;
        }

        if (uint64(rewardCopper) < requestedCopper)
        {
            ChatHandler(player->GetSession()).PSendSysMessage(
                "Your Honor is capped. {} excess Honor was converted, but you could only receive {} because you are near the gold cap.",
                excessHonor,
                FormatMoney(rewardCopper));

            return;
        }

        ChatHandler(player->GetSession()).PSendSysMessage(
            "Your Honor is capped. {} excess Honor has been converted into {}.",
            excessHonor,
            FormatMoney(rewardCopper));
    }
};

void AddHonorOverflowScripts()
{
    new NaxxramasCoreHonorOverflowConfig();
    new NaxxramasCoreHonorOverflowPlayer();
}