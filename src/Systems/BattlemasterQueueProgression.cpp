/*
 * Naxxramas Core - Classic Battlemaster queue requirement
 *
 * Players below the WotLK entry milestone (modern Individual Progression
 * stage 13) must initiate Battleground queues at a real, nearby Battlemaster.
 * This validates the supplied creature GUID server-side; hiding the buttons
 * in the optional 3.3.5a addon is only a visual convenience.
 *
 * Do not modify Individual Progression, Playerbots or AzerothCore itself.
 */

#include "AccountMgr.h"
#include "BattlegroundMgr.h"
#include "Chat.h"
#include "Config.h"
#include "Creature.h"
#include "Group.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"

#include <regex>
#include <string>

namespace
{
    constexpr uint32 DEFAULT_WOTLK_ENTRY_STAGE = 13;
    constexpr uint32 MAX_MODERN_IP_STAGE = 18;
    constexpr uint32 PROGRESSION_QUEST_START = 66000;

    bool FeatureEnabled()
    {
        return sConfigMgr->GetOption<bool>(
            "NaxxramasCore.BattlegroundQueue.ClassicMode.Enabled", false);
    }

    uint32 UnlockStage()
    {
        uint32 stage = sConfigMgr->GetOption<uint32>(
            "NaxxramasCore.BattlegroundQueue.ClassicMode.UnlockStage",
            DEFAULT_WOTLK_ENTRY_STAGE);
        return stage >= 1 && stage <= MAX_MODERN_IP_STAGE
            ? stage : DEFAULT_WOTLK_ENTRY_STAGE;
    }

    bool IsExempt(Player* player)
    {
        if (player->IsGameMaster() &&
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.BattlegroundQueue.ClassicMode.ExemptGMs", true))
            return true;

        if (!sConfigMgr->GetOption<bool>(
                "NaxxramasCore.BattlegroundQueue.ClassicMode.ExemptPlayerbots", true))
            return false;

        if (!player->GetSession())
            return false;

        // Mirror the bot-account rule used by modern Individual Progression.
        // This works even when its public C++ header is not exported.
        std::string accountName;
        if (!AccountMgr::GetName(player->GetSession()->GetAccountId(), accountName))
            return false;

        std::string pattern = sConfigMgr->GetOption<std::string>(
            "IndividualProgression.BotAccountsRegex", "^RNDBOT.*");

        try
        {
            return !pattern.empty() && std::regex_match(
                accountName, std::regex(pattern));
        }
        catch (std::regex_error const&)
        {
            // A malformed administrator-provided regex must never crash
            // a battleground queue request.
            return false;
        }
    }

    bool RemoteQueueUnlocked(Player* player, uint32 unlockStage)
    {
        if (!player || !player->IsInWorld())
            return true;

        // If IP is disabled, do not impose expansion restrictions.
        if (!sConfigMgr->GetOption<bool>("IndividualProgression.Enable", true))
            return true;

        if (IsExempt(player))
            return true;

        // Match the modern Individual Progression progression-limit policy.
        uint32 limit = sConfigMgr->GetOption<uint32>(
            "IndividualProgression.ProgressionLimit", 0);
        if (limit != 0 && limit < unlockStage)
            return false;

        // Modern IP stores each achieved milestone as a rewarded hidden quest.
        // Rewarding a later milestone may subsume earlier milestone quests.
        for (uint32 stage = unlockStage; stage <= MAX_MODERN_IP_STAGE; ++stage)
        {
            if (player->GetQuestStatus(PROGRESSION_QUEST_START + stage) ==
                QUEST_STATUS_REWARDED)
                return true;
        }

        return false;
    }

    bool HasValidBattlemaster(Player* player, ObjectGuid guid,
        BattlegroundTypeId battleground)
    {
        if (!guid)
            return false;

        // Validates that the NPC exists, is friendly, is nearby and has
        // the actual Battlemaster NPC flag. GUID alone is not enough.
        Creature* npc = player->GetNPCIfCanInteractWith(
            guid, UNIT_NPC_FLAG_BATTLEMASTER);

        return npc && npc->IsBattleMaster() &&
            sBattlegroundMgr->GetBattleMasterBG(npc->GetEntry()) == battleground;
    }
}

class NaxxramasCoreBattlemasterQueueProgression : public PlayerScript
{
public:
    NaxxramasCoreBattlemasterQueueProgression()
        : PlayerScript("NaxxramasCoreBattlemasterQueueProgression",
            { PLAYERHOOK_CAN_JOIN_IN_BATTLEGROUND_QUEUE })
    {
    }

    bool OnPlayerCanJoinInBattlegroundQueue(Player* player,
        ObjectGuid battlemasterGuid, BattlegroundTypeId bgType,
        uint8 joinAsGroup, GroupJoinBattlegroundResult& err) override
    {
        if (!FeatureEnabled() || !player || !player->IsInWorld())
            return true;

        uint32 unlockStage = UnlockStage();
        bool needsBattlemaster = !RemoteQueueUnlocked(player, unlockStage);

        // Group queueing checks the leader *and* all online members:
        // a WotLK leader must not grant remote queue access to Vanilla
        // or TBC members solely by inviting them to the group.
        if (joinAsGroup && player->GetGroup())
        {
            for (GroupReference* ref = player->GetGroup()->GetFirstMember();
                 ref; ref = ref->next())
            {
                Player* member = ref->GetSource();
                if (member && !RemoteQueueUnlocked(member, unlockStage))
                {
                    needsBattlemaster = true;
                    break;
                }
            }
        }

        if (!needsBattlemaster ||
            HasValidBattlemaster(player, battlemasterGuid, bgType))
            return true;

        // The queue hook runs before AzerothCore actually inserts the queue.
        // Suppress the incorrect native BG error and send our explanation.
        err = ERR_BATTLEGROUND_NONE;

        if (player->GetSession())
            ChatHandler(player->GetSession()).SendSysMessage(
                "Remote Battleground queueing is unavailable at your current "
                "Individual Progression stage. Visit a Battlemaster to queue. "
                "Remote queueing unlocks when you enter Wrath of the Lich King.");

        return false;
    }
};

void AddBattlemasterQueueProgressionScripts()
{
    new NaxxramasCoreBattlemasterQueueProgression();
}
