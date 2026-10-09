/*
 * Naxxramas Core — calendar-based Elemental Invasions.
 *
 * Event 13 remains AzerothCore's original Elemental Invasions event.
 * Its game_event.world_event must be GAMEEVENT_INTERNAL (5) so that
 * AzerothCore's minute-based recurrence never fights the calendar controller.
 *
 * No changes to the AzerothCore core or to any other game events are needed.
 */

#include "Config.h"
#include "GameEventMgr.h"
#include "Log.h"
#include "ScriptMgr.h"

#include <algorithm>
#include <ctime>

namespace
{
    constexpr uint16 ELEMENTAL_INVASIONS_EVENT_ID = 13;
    constexpr uint32 CHECK_INTERVAL_MS = 60 * 1000;

    bool ElementalInvasionEnabled = false;
    uint32 ElementalInvasionHour = 0;
    uint32 ElementalInvasionMinute = 0;
    uint32 ElementalInvasionDurationDays = 5;

    bool GetLocalTime(std::time_t value, std::tm& result)
    {
#ifdef _WIN32
        return localtime_s(&result, &value) == 0;
#else
        return localtime_r(&value, &result) != nullptr;
#endif
    }

    // Both boundaries are wall-clock dates in the worldserver's local timezone.
    // mktime handles variable month lengths and local daylight-saving changes.
    bool InMonthlyWindow(std::time_t now, bool& active)
    {
        std::tm local = {};
        if (!GetLocalTime(now, local))
            return false;

        std::tm start = local;
        start.tm_mday = 1;
        start.tm_hour = static_cast<int>(ElementalInvasionHour);
        start.tm_min = static_cast<int>(ElementalInvasionMinute);
        start.tm_sec = 0;
        start.tm_isdst = -1;

        std::tm finish = start;
        finish.tm_mday += static_cast<int>(ElementalInvasionDurationDays);
        finish.tm_isdst = -1;

        std::time_t beginAt = std::mktime(&start);
        std::time_t endAt = std::mktime(&finish);
        if (beginAt == static_cast<std::time_t>(-1) ||
            endAt == static_cast<std::time_t>(-1) || endAt <= beginAt)
            return false;

        active = beginAt <= now && now < endAt;
        return true;
    }
}

class NaxxramasCoreElementalInvasionCalendar : public WorldScript
{
public:
    NaxxramasCoreElementalInvasionCalendar()
        : WorldScript("NaxxramasCoreElementalInvasionCalendar",
            { WORLDHOOK_ON_BEFORE_CONFIG_LOAD, WORLDHOOK_ON_STARTUP, WORLDHOOK_ON_UPDATE })
    {
    }

    void OnBeforeConfigLoad(bool /*reload*/) override
    {
        ElementalInvasionEnabled =
            sConfigMgr->GetOption<bool>("NaxxramasCore.ElementalInvasion.Enabled", false);
        ElementalInvasionHour = std::min<uint32>(
            23, sConfigMgr->GetOption<uint32>("NaxxramasCore.ElementalInvasion.Hour", 0));
        ElementalInvasionMinute = std::min<uint32>(
            59, sConfigMgr->GetOption<uint32>("NaxxramasCore.ElementalInvasion.Minute", 0));
        ElementalInvasionDurationDays = std::max<uint32>(1, std::min<uint32>(
            27, sConfigMgr->GetOption<uint32>("NaxxramasCore.ElementalInvasion.DurationDays", 5)));
    }

    void OnStartup() override
    {
        _checkTimer = 0;
        _reportedSetupError = false;
        _reportedStartError = false;
    }

    void OnUpdate(uint32 diff) override
    {
        // When disabled the module never touches game event 13.
        if (!ElementalInvasionEnabled)
            return;

        if (_checkTimer > diff)
        {
            _checkTimer -= diff;
            return;
        }

        _checkTimer = CHECK_INTERVAL_MS;
        SynchronizeInvasion();
    }

private:
    uint32 _checkTimer = 0;
    bool _reportedSetupError = false;
    bool _reportedStartError = false;

    void SynchronizeInvasion()
    {
        GameEventMgr::GameEventDataMap const& events = sGameEventMgr->GetEventMap();
        if (events.size() <= ELEMENTAL_INVASIONS_EVENT_ID ||
            events[ELEMENTAL_INVASIONS_EVENT_ID].State != GAMEEVENT_INTERNAL)
        {
            if (!_reportedSetupError)
            {
                LOG_ERROR("module",
                    "NaxxramasCore: Elemental Invasions requires game_event.eventEntry=13 "
                    "with world_event=5 (GAMEEVENT_INTERNAL). Apply the module SQL and restart.");
                _reportedSetupError = true;
            }
            return;
        }

        _reportedSetupError = false;

        bool shouldBeActive = false;
        if (!InMonthlyWindow(std::time(nullptr), shouldBeActive))
        {
            if (!_reportedSetupError)
            {
                LOG_ERROR("module", "NaxxramasCore: Could not calculate the local "
                    "Elemental Invasions calendar window.");
                _reportedSetupError = true;
            }
            return;
        }

        bool isActive = sGameEventMgr->IsActiveEvent(ELEMENTAL_INVASIONS_EVENT_ID);
        if (shouldBeActive && !isActive)
        {
            sGameEventMgr->StartInternalEvent(ELEMENTAL_INVASIONS_EVENT_ID);
            if (sGameEventMgr->IsActiveEvent(ELEMENTAL_INVASIONS_EVENT_ID))
            {
                _reportedStartError = false;
                LOG_INFO("module", "NaxxramasCore: Monthly Elemental Invasions started.");
            }
            else if (!_reportedStartError)
            {
                LOG_ERROR("module",
                    "NaxxramasCore: Could not start Elemental Invasions event 13. "
                    "Check the game event disabled-state and server logs.");
                _reportedStartError = true;
            }
        }
        else if (!shouldBeActive && isActive)
        {
            sGameEventMgr->StopEvent(ELEMENTAL_INVASIONS_EVENT_ID);
            _reportedStartError = false;
            LOG_INFO("module", "NaxxramasCore: Monthly Elemental Invasions ended.");
        }
    }
};

void AddElementalInvasionCalendarScripts()
{
    new NaxxramasCoreElementalInvasionCalendar();
}
