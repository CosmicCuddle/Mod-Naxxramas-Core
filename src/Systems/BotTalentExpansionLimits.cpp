/*
 * Naxxramas Core
 * Systems - Playerbot manual talent expansion limits
 *
 * Playerbots' AiPlayerbot.LimitTalentsExpansion setting already filters
 * automatic talent templates, but manually selected premade specs and
 * imported talent links use separate assignment paths.
 *
 * Use AzerothCore's pre-learn hook to apply the same restriction to those
 * paths without modifying mod-playerbots or changing talent point totals.
 */

#include "Player.h"
#include "PlayerbotAIConfig.h"
#include "PlayerbotMgr.h"
#include "ScriptMgr.h"

// Public helper implemented entirely by the Naxxramas Core importer.
namespace NaxxramasBotTalentImport
{
    bool IsImportOffCentreCapstone(Player const* bot, TalentEntry const* talent);
}

namespace
{
    bool IsTalentWithinExpansionLimit(uint8 level, TalentEntry const* talent)
    {
        if (level <= 60)
        {
            // Vanilla: first six rows and middle talent of the seventh.
            return talent->Row < 6 ||
                (talent->Row == 6 && talent->Col == 1);
        }

        if (level <= 70)
        {
            // TBC: first eight rows and middle talent of the ninth.
            return talent->Row < 8 ||
                (talent->Row == 8 && talent->Col == 1);
        }

        // WotLK: full talent tree.
        return true;
    }
}

class NaxxramasCoreBotTalentExpansionLimits : public PlayerScript
{
public:
    NaxxramasCoreBotTalentExpansionLimits()
        : PlayerScript(
            "NaxxramasCoreBotTalentExpansionLimits",
            {
                PLAYERHOOK_CAN_LEARN_TALENT
            })
    {
    }

    bool OnPlayerCanLearnTalent(
        Player* player,
        TalentEntry const* talent,
        uint32 /*rank*/) override
    {
        if (!player ||
            !talent ||
            !sPlayerbotAIConfig.limitTalentsExpansion)
        {
            return true;
        }

        // This safeguard must not restrict real players or other systems.
        if (!PlayerbotsMgr::instance().GetPlayerbotAI(player))
            return true;

        // Allow only the three off-centre calculator capstones, and only
        // during the explicit scoped NT1 apply. Normal Playerbots builds
        // retain their existing expansion row policy.
        if (NaxxramasBotTalentImport::IsImportOffCentreCapstone(player, talent))
            return true;

        return IsTalentWithinExpansionLimit(
            player->GetLevel(),
            talent);
    }
};

void AddBotTalentExpansionLimitsScripts()
{
    new NaxxramasCoreBotTalentExpansionLimits();
}
