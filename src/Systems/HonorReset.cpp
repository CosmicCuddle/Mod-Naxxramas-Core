/*
 * Naxxramas Core
 *
 * Fortnightly Honor Reset
 *
 * Automatically resets spendable Honor on a configurable schedule.
 * The reset survives server restarts and will catch up a missed reset.
 */

#include "Chat.h"
#include "Config.h"
#include "DatabaseEnv.h"
#include "Log.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "WorldSessionMgr.h"

#include <algorithm>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <string>

namespace
{
    bool HonorResetEnabled = false;
    uint32 HonorResetIntervalWeeks = 2;
    uint32 HonorResetDayOfWeek = 3;
    uint32 HonorResetHour = 6;
    uint32 HonorResetMinute = 0;
    std::string HonorResetAnchorDate = "2026-10-07";
    bool HonorResetNotify = true;

    constexpr uint32 HONOR_RESET_CHECK_INTERVAL = 60000; // 60 seconds

    bool GetLocalTime(std::time_t value, std::tm& result)
    {
#ifdef _WIN32
        return localtime_s(&result, &value) == 0;
#else
        return localtime_r(&value, &result) != nullptr;
#endif
    }

    bool BuildAnchorTime(std::time_t& result)
    {
        std::tm anchor = {};

        std::istringstream stream(HonorResetAnchorDate);
        stream >> std::get_time(&anchor, "%Y-%m-%d");

        if (stream.fail())
            return false;

        anchor.tm_hour = static_cast<int>(HonorResetHour);
        anchor.tm_min = static_cast<int>(HonorResetMinute);
        anchor.tm_sec = 0;
        anchor.tm_isdst = -1;

        std::time_t anchorTime = std::mktime(&anchor);

        if (anchorTime == static_cast<std::time_t>(-1))
            return false;

        std::tm normalized = {};

        if (!GetLocalTime(anchorTime, normalized))
            return false;

        // tm_wday:
        // 0 = Sunday
        // 1 = Monday
        // ...
        // 6 = Saturday
        if (static_cast<uint32>(normalized.tm_wday) != HonorResetDayOfWeek)
            return false;

        result = anchorTime;
        return true;
    }

    std::time_t AddWeeks(std::time_t baseTime, uint32 weeks)
    {
        std::tm local = {};

        if (!GetLocalTime(baseTime, local))
            return static_cast<std::time_t>(-1);

        local.tm_mday += static_cast<int>(weeks * 7);
        local.tm_isdst = -1;

        return std::mktime(&local);
    }

    std::time_t GetLatestScheduledReset(std::time_t now)
    {
        std::time_t anchorTime;

        if (!BuildAnchorTime(anchorTime))
            return 0;

        if (now < anchorTime)
            return 0;

        std::time_t scheduledReset = anchorTime;

        while (true)
        {
            std::time_t nextReset =
                AddWeeks(scheduledReset, HonorResetIntervalWeeks);

            if (nextReset == static_cast<std::time_t>(-1))
                return scheduledReset;

            if (nextReset > now)
                return scheduledReset;

            scheduledReset = nextReset;
        }
    }

    uint64 LoadLastHonorReset()
    {
        QueryResult result = CharacterDatabase.Query(
            "SELECT `last_reset` "
            "FROM `mod_naxxramas_honor_reset` "
            "WHERE `id` = 1");

        if (!result)
            return 0;

        return (*result)[0].Get<uint64>();
    }

    void SaveLastHonorReset(uint64 resetTime)
    {
        CharacterDatabase.DirectExecute(
            "INSERT INTO `mod_naxxramas_honor_reset` "
            "(`id`, `last_reset`) "
            "VALUES (1, {}) "
            "ON DUPLICATE KEY UPDATE "
            "`last_reset` = VALUES(`last_reset`)",
            resetTime);
    }

    void PerformHonorReset(uint64 scheduledReset)
    {
        // Reset Honor stored for every character, including offline players.
        CharacterDatabase.Execute(
            CharacterDatabase.GetPreparedStatement(
                CHAR_UPD_ALL_HONOR_POINTS));

        // Online players also need their in-memory Honor reset.
        sWorldSessionMgr->DoForAllOnlinePlayers([](Player* player)
        {
            if (!player)
                return;

            player->SetHonorPoints(0);

            if (HonorResetNotify && player->GetSession())
            {
                ChatHandler(player->GetSession()).PSendSysMessage(
                    "Your Honor has been reset as part of the fortnightly PvP reset. "
                    "The next Honor cycle has begun.");
            }
        });

        SaveLastHonorReset(scheduledReset);

        LOG_INFO(
            "module",
            "NaxxramasCore: Fortnightly Honor reset completed.");
    }
}

class NaxxramasCoreHonorReset : public WorldScript
{
public:
    NaxxramasCoreHonorReset()
        : WorldScript(
            "NaxxramasCoreHonorReset",
            {
                WORLDHOOK_ON_BEFORE_CONFIG_LOAD,
                WORLDHOOK_ON_STARTUP,
                WORLDHOOK_ON_UPDATE
            })
    {
    }

    void OnBeforeConfigLoad(bool /*reload*/) override
    {
        HonorResetEnabled =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.HonorReset.Enabled",
                false);

        HonorResetIntervalWeeks =
            std::max<uint32>(
                1,
                sConfigMgr->GetOption<uint32>(
                    "NaxxramasCore.HonorReset.IntervalWeeks",
                    2));

        HonorResetDayOfWeek =
            std::min<uint32>(
                6,
                sConfigMgr->GetOption<uint32>(
                    "NaxxramasCore.HonorReset.DayOfWeek",
                    3));

        HonorResetHour =
            std::min<uint32>(
                23,
                sConfigMgr->GetOption<uint32>(
                    "NaxxramasCore.HonorReset.Hour",
                    6));

        HonorResetMinute =
            std::min<uint32>(
                59,
                sConfigMgr->GetOption<uint32>(
                    "NaxxramasCore.HonorReset.Minute",
                    0));

        HonorResetAnchorDate =
            sConfigMgr->GetOption<std::string>(
                "NaxxramasCore.HonorReset.AnchorDate",
                "2026-10-07");

        HonorResetNotify =
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.HonorReset.Notify",
                true);
    }

    void OnStartup() override
    {
        _lastReset = LoadLastHonorReset();
        _checkTimer = 0;

        if (HonorResetEnabled)
            CheckForReset();
    }

    void OnUpdate(uint32 diff) override
    {
        if (!HonorResetEnabled)
            return;

        if (_checkTimer > diff)
        {
            _checkTimer -= diff;
            return;
        }

        _checkTimer = HONOR_RESET_CHECK_INTERVAL;

        CheckForReset();
    }

private:
    uint32 _checkTimer = 0;
    uint64 _lastReset = 0;

    void CheckForReset()
    {
        std::time_t now = std::time(nullptr);

        std::time_t scheduledReset =
            GetLatestScheduledReset(now);

        if (scheduledReset <= 0)
            return;

        uint64 scheduledResetValue =
            static_cast<uint64>(scheduledReset);

        if (scheduledResetValue <= _lastReset)
            return;

        PerformHonorReset(scheduledResetValue);

        _lastReset = scheduledResetValue;
    }
};

void AddHonorResetScripts()
{
    new NaxxramasCoreHonorReset();
}