/*
 * Naxxramas Core - shared Individual Progression era check.
 *
 * Same rule as IsVanillaProgression() in MeetingStoneProgression.cpp.
 * A source test keeps the two in step until Meeting Stones move here.
 */
#ifndef NAXXRAMAS_CORE_INDIVIDUAL_PROGRESSION_ERA_H
#define NAXXRAMAS_CORE_INDIVIDUAL_PROGRESSION_ERA_H

#include "Config.h"
#include "Player.h"

#include <type_traits>
#include <utility>

#if __has_include("IndividualProgression.h")
#include "IndividualProgression.h"
#define NAXXRAMAS_IP_ERA_HAS_IP_HEADER 1
#else
#define NAXXRAMAS_IP_ERA_HAS_IP_HEADER 0
#endif

namespace NaxxramasIpEra
{
    // Current IP: TBC entry is milestone 8 (quest 66008). Older IP: 7.
    constexpr uint8 CURRENT_IP_TBC_ENTRY = 8;
    constexpr uint8 LEGACY_IP_TBC_ENTRY = 7;
    constexpr uint32 CURRENT_IP_TBC_ENTRY_QUEST = 66000 + CURRENT_IP_TBC_ENTRY;

#if NAXXRAMAS_IP_ERA_HAS_IP_HEADER
    template <typename T, typename = void>
    struct HasQuestProgressionReader : std::false_type {};

    template <typename T>
    struct HasQuestProgressionReader<T, std::void_t<
        decltype(std::declval<T const&>().GetPlayerProgressionFromQuests(
            std::declval<Player*>()))>> : std::true_type {};
#endif

    inline bool IsVanillaProgression(Player* player)
    {
        if (!player || !player->IsInWorld())
            return false;

#if NAXXRAMAS_IP_ERA_HAS_IP_HEADER
        // When IP itself is disabled, preserve the stock WotLK behavior.
        if (!sIndividualProgression->enabled)
            return false;

        constexpr uint8 tbcEntry = HasQuestProgressionReader<
            IndividualProgression>::value
            ? CURRENT_IP_TBC_ENTRY
            : LEGACY_IP_TBC_ENTRY;

        return !sIndividualProgression->hasPassedProgression(
            player, static_cast<ProgressionState>(tbcEntry));
#else
        // Match IP's own enable/limit settings even when its public
        // header is not exported to this module.
        if (!sConfigMgr->GetOption<bool>("IndividualProgression.Enable", true))
            return false;

        const uint32 progressionLimit = sConfigMgr->GetOption<uint32>(
            "IndividualProgression.ProgressionLimit", 0);
        if (progressionLimit != 0 && progressionLimit < CURRENT_IP_TBC_ENTRY)
            return true;

        // Fallback for installations where IP's public header is not
        // exported to other modules. Current IP stores progress in
        // rewarded hidden quests; 66008 marks entry into TBC.
        //
        // On a legacy IP build without exported headers, this fallback
        // cannot read its old player-settings storage. See the README
        // compatibility and testing notes before enabling that setup.
        // Check all TBC and WotLK milestones, just as modern IP's
        // progression reader finds the highest rewarded stage.
        for (uint32 quest = CURRENT_IP_TBC_ENTRY_QUEST; quest <= 66018; ++quest)
        {
            if (player->GetQuestStatus(quest) == QUEST_STATUS_REWARDED)
                return false;
        }

        return true;
#endif
    }
}

#endif
