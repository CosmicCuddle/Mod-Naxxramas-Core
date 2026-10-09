/*
 * Naxxramas Core - Individual Progression meeting stones
 *
 * While a character is in Vanilla progression, meeting stones behave as
 * scenery: clicking them must not start the WotLK meeting-stone summon.
 * TBC and WotLK characters use the unmodified AzerothCore implementation.
 *
 * The AllGameObjectScript hook runs at the beginning of GameObject::Use,
 * before the meeting-stone spell (23598) is selected. No world GO templates,
 * client DBC files, Individual Progression source, or AzerothCore files
 * need changing.
 */

#include "Chat.h"
#include "Config.h"
#include "GameObject.h"
#include "Player.h"
#include "ScriptMgr.h"

#include <type_traits>
#include <utility>

#if __has_include("IndividualProgression.h")
#include "IndividualProgression.h"
#define NAXXRAMAS_MEETING_STONES_HAS_IP_HEADER 1
#else
#define NAXXRAMAS_MEETING_STONES_HAS_IP_HEADER 0
#endif

namespace
{
    // The current Individual Progression release marks TBC entry when the
    // PRE_TBC milestone (8) is rewarded. Its earlier versions have a
    // different ProgressionState numbering scheme: TBC starts at 7.
    constexpr uint8 CURRENT_IP_TBC_ENTRY = 8;
    constexpr uint8 LEGACY_IP_TBC_ENTRY = 7;
    constexpr uint32 CURRENT_IP_TBC_ENTRY_QUEST = 66000 + CURRENT_IP_TBC_ENTRY;

#if NAXXRAMAS_MEETING_STONES_HAS_IP_HEADER
    // Distinguish the current hidden-quest IP API from the older player-
    // settings IP API at compile time, without depending on enum names
    // that are missing from the older module.
    template <typename T, typename = void>
    struct HasQuestProgressionReader : std::false_type {};

    template <typename T>
    struct HasQuestProgressionReader<T, std::void_t<
        decltype(std::declval<T const&>().GetPlayerProgressionFromQuests(
            std::declval<Player*>()))>> : std::true_type {};
#endif

    bool IsVanillaProgression(Player* player)
    {
        if (!player || !player->IsInWorld())
            return false;

#if NAXXRAMAS_MEETING_STONES_HAS_IP_HEADER
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

class NaxxramasCoreMeetingStoneProgression : public AllGameObjectScript
{
public:
    NaxxramasCoreMeetingStoneProgression()
        : AllGameObjectScript("NaxxramasCoreMeetingStoneProgression")
    {
    }

    bool CanGameObjectGossipHello(Player* player, GameObject* go) override
    {
        if (!player || !go ||
            go->GetGoType() != GAMEOBJECT_TYPE_MEETINGSTONE ||
            !sConfigMgr->GetOption<bool>(
                "NaxxramasCore.MeetingStones.ClassicMode.Enabled", true))
        {
            return false;
        }

        if (!IsVanillaProgression(player))
            return false; // Hand off to AzerothCore for TBC/WotLK.

        // Returning true stops GameObject::Use before the native
        // meeting-stone summon starts; the stone remains visible.
        if (player->GetSession())
            ChatHandler(player->GetSession()).SendSysMessage(
                "Summoning stones are currently unavailable. They unlock when you reach The Burning Crusade in Individual Progression.");

        return true;
    }
};

void AddMeetingStoneProgressionScripts()
{
    new NaxxramasCoreMeetingStoneProgression();
}
