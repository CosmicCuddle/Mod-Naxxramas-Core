/*
 * Naxxramas Core
 *
 * Honor Overflow
 *
 * Converts Honor earned above the configured AzerothCore Honor cap
 * into gold at a configurable conversion rate.
 *
 * Battleground behavior:
 * - Currency is awarded immediately.
 * - Individual conversion messages are suppressed during the Battleground.
 * - A single summary message is shown when the Battleground ends or the
 *   player leaves early.
 */

#include "Chat.h"
#include "Config.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "ScriptDefines/AllBattlegroundScript.h"
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

    struct BattlegroundHonorSummary
    {
        uint64 ExcessHonor = 0;
        uint64 RequestedCopper = 0;
        uint64 AwardedCopper = 0;
    };

    std::unordered_map<ObjectGuid::LowType, HonorSnapshot> HonorSnapshots;
    std::unordered_map<ObjectGuid::LowType, BattlegroundHonorSummary> BattlegroundHonorSummaries;

    bool IsPlayerBot(Player* player)
    {
#if NAXXRAMAS_CORE_HAS_PLAYERBOTS
        return GET_PLAYERBOT_AI(player) != nullptr;
#else
        return false;
#endif
    }

    std::string FormatMoney(uint64 copper)
    {
        uint64 gold = copper / GOLD;
        copper %= GOLD;

        uint64 silver = copper / SILVER;
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

    void AddBattlegroundSummary(
        Player* player,
        uint32 excessHonor,
        uint64 requestedCopper,
        uint32 awardedCopper)
    {
        BattlegroundHonorSummary& summary =
            BattlegroundHonorSummaries[player->GetGUID().GetCounter()];

        summary.ExcessHonor += excessHonor;
        summary.RequestedCopper += requestedCopper;
        summary.AwardedCopper += awardedCopper;
    }

    void SendBattlegroundSummary(Player* player)
    {
        if (!player)
            return;

        ObjectGuid::LowType guid = player->GetGUID().GetCounter();

        auto itr = BattlegroundHonorSummaries.find(guid);
        if (itr == BattlegroundHonorSummaries.end())
            return;

        BattlegroundHonorSummary summary = itr->second;
        BattlegroundHonorSummaries.erase(itr);

        if (!HonorOverflowNotify || !player->GetSession() || summary.ExcessHonor == 0)
            return;

        if (summary.AwardedCopper == 0)
        {
            ChatHandler(player->GetSession()).PSendSysMessage(
                "Your Honor was capped during this Battleground. {} excess Honor was earned, but no gold could be added because you are at the gold cap.",
                summary.ExcessHonor);

            return;
        }

        if (summary.AwardedCopper < summary.RequestedCopper)
        {
            ChatHandler(player->GetSession()).PSendSysMessage(
                "Your Honor was capped during this Battleground. {} excess Honor was converted, but you could only receive {} because you reached the gold cap.",
                summary.ExcessHonor,
                FormatMoney(summary.AwardedCopper));

            return;
        }

        ChatHandler(player->GetSession()).PSendSysMessage(
            "Your Honor was capped during this Battleground. {} excess Honor has been converted into {}.",
            summary.ExcessHonor,
            FormatMoney(summary.AwardedCopper));
    }

    void ProcessHonorOverflow(Player* player, bool forceBattlegroundSummary = false)
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

        // Update the snapshot immediately so every check starts
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

        bool useBattlegroundSummary =
            forceBattlegroundSummary || player->InBattleground();

        if (useBattlegroundSummary)
        {
            AddBattlegroundSummary(
                player,
                excessHonor,
                requestedCopper,
                rewardCopper);

            return;
        }

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

        // A fresh login should never inherit an old in-memory BG summary.
        BattlegroundHonorSummaries.erase(
            player->GetGUID().GetCounter());
    }

    void OnPlayerLogout(Player* player) override
    {
        ObjectGuid::LowType guid = player->GetGUID().GetCounter();

        HonorSnapshots.erase(guid);
        BattlegroundHonorSummaries.erase(guid);
    }

    void OnPlayerUpdate(Player* player, uint32 /*diff*/) override
    {
        ProcessHonorOverflow(player);
    }
};

class NaxxramasCoreHonorOverflowBattleground : public BGScript
{
public:
    NaxxramasCoreHonorOverflowBattleground()
        : BGScript(
            "NaxxramasCoreHonorOverflowBattleground",
            {
                ALLBATTLEGROUNDHOOK_ON_BATTLEGROUND_END_REWARD,
                ALLBATTLEGROUNDHOOK_ON_BATTLEGROUND_REMOVE_PLAYER_AT_LEAVE
            })
    {
    }

    void OnBattlegroundEndReward(
        Battleground* /*bg*/,
        Player* player,
        TeamId /*winnerTeamId*/) override
    {
        // Catch any final Honor awarded at Battleground completion before
        // showing the single combined summary.
        ProcessHonorOverflow(player, true);
        SendBattlegroundSummary(player);
    }

    void OnBattlegroundRemovePlayerAtLeave(
        Battleground* /*bg*/,
        Player* player) override
    {
        // Leaving early is the end of this player's Battleground session.
        // Awarded currency is already safe; show one summary and clear it.
        ProcessHonorOverflow(player, true);
        SendBattlegroundSummary(player);
    }
};

void AddHonorOverflowScripts()
{
    new NaxxramasCoreHonorOverflowConfig();
    new NaxxramasCoreHonorOverflowPlayer();
    new NaxxramasCoreHonorOverflowBattleground();
}
