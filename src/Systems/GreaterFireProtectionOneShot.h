#ifndef NAXXRAMAS_GREATER_FIRE_PROTECTION_ONE_SHOT_H
#define NAXXRAMAS_GREATER_FIRE_PROTECTION_ONE_SHOT_H

#include <cstdint>

// Pure timing policy; the actual aura and bot-scope checks belong to
// BotRaidConsumables.cpp. One deadline may be consumed only once, even when
// the bot is unavailable or aura application fails. No delayed retry loop.
struct NaxxramasOneShotTimer
{
    explicit NaxxramasOneShotTimer(std::uint32_t delayMs)
        : RemainingMs(delayMs)
    {
    }

    bool ConsumeIfDue(std::uint32_t diff)
    {
        if (!Pending)
            return false;

        if (RemainingMs > diff)
        {
            RemainingMs -= diff;
            return false;
        }

        Pending = false;
        RemainingMs = 0;
        return true;
    }

    std::uint32_t RemainingMs = 0;
    bool Pending = true;
};

#endif
