/*
 * Naxxramas Core - progression-aware mount cast times (optional)
 *
 * AzerothCore computes cast time before OnSpellPrepare/OnPlayerSpellCast.
 * The optional OnAfterCalcSpellCastTime core hook must be installed BEFORE
 * enabling this feature. Unpatched cores compile the module with this
 * script disabled and leave ALL mount casts unchanged.
 *
 * Never mutate SpellInfo/Spell.dbc globally: players at different
 * Individual Progression stages can be online at the same time.
 */

#include "Config.h"
#include "GlobalScript.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SpellInfo.h"

#if defined(AC_HAS_AFTER_CALC_SPELL_CAST_TIME)
#include "AccountMgr.h"
#include "SpellAuraDefines.h"
#include "WorldSession.h"

#include <algorithm>
#include <regex>
#include <string>

namespace
{
    constexpr uint32 WOTLK_ENTRY_STAGE = 13;
    constexpr uint32 FINAL_IP_STAGE = 18;
    constexpr uint32 QUEST_ID_OFFSET = 66000;

    bool IsExemptPlayerbot(Player* player)
    {
        if (!sConfigMgr->GetOption<bool>(
                "NaxxramasCore.EraMountCast.ExemptPlayerbots", true))
            return false;

        if (!player || !player->GetSession())
            return false;

        std::string name;
        if (!AccountMgr::GetName(player->GetSession()->GetAccountId(), name))
            return false;

        std::string pattern = sConfigMgr->GetOption<std::string>(
            "IndividualProgression.BotAccountsRegex", "^RNDBOT.*");

        try
        {
            return !pattern.empty() &&
                std::regex_match(name, std::regex(pattern));
        }
        catch (std::regex_error const&)
        {
            // Invalid administrator regex must not interrupt spell casting.
            return false;
        }
    }

    bool IsAtOrBeyondStage(Player* player, uint32 stage)
    {
        // Match modern Individual Progression's rewarded hidden milestones.
        // The progression cap also applies if the player has older quest
        // rewards from before the server administrator lowered that cap.
        uint32 limit = sConfigMgr->GetOption<uint32>(
            "IndividualProgression.ProgressionLimit", 0);
        if (limit && limit < stage)
            return false;

        for (uint32 s = stage; s <= FINAL_IP_STAGE; ++s)
            if (player->GetQuestStatus(QUEST_ID_OFFSET + s) ==
                QUEST_STATUS_REWARDED)
                return true;

        return false;
    }

    uint32 CheckedTime(char const* key, uint32 defaultValue)
    {
        return std::clamp(
            sConfigMgr->GetOption<uint32>(key, defaultValue),
            uint32(500), uint32(10000));
    }
}

class NaxxramasEraMountCastScript : public GlobalScript
{
public:
    NaxxramasEraMountCastScript()
        : GlobalScript("NaxxramasEraMountCastScript",
            { GLOBALHOOK_ON_AFTER_CALC_SPELL_CAST_TIME }) { }

    void OnAfterCalcSpellCastTime(WorldObject* caster,
        SpellInfo const* spellInfo, int32& castTime) override
    {
        if (!sConfigMgr->GetOption<bool>(
                "NaxxramasCore.EraMountCast.Enabled", false))
            return;

        if (!caster || !spellInfo || castTime <= 0 ||
            spellInfo->IsChanneled() ||
            !spellInfo->CastTimeEntry ||
            spellInfo->CastTimeEntry->CastTime <= 0 ||
            !spellInfo->HasAura(SPELL_AURA_MOUNTED))
            return;

        // Only the actual player caster: never a pet, scripted NPC or bot
        // proxy. Preserve all instant mounts / Druid travel transformations.
        Player* player = caster->ToPlayer();
        if (!player || !player->IsInWorld() || IsExemptPlayerbot(player))
            return;

        // If IP is off, fall back to the server's native WotLK mount time.
        if (!sConfigMgr->GetOption<bool>(
                "IndividualProgression.Enable", true))
            return;

        uint32 unlockStage = sConfigMgr->GetOption<uint32>(
            "NaxxramasCore.EraMountCast.UnlockStage", WOTLK_ENTRY_STAGE);
        if (unlockStage < WOTLK_ENTRY_STAGE || unlockStage > FINAL_IP_STAGE)
            unlockStage = WOTLK_ENTRY_STAGE;

        uint32 intendedMs = IsAtOrBeyondStage(player, unlockStage)
            ? CheckedTime("NaxxramasCore.EraMountCast.ModernCastTimeMs", 1500)
            : CheckedTime("NaxxramasCore.EraMountCast.ClassicCastTimeMs", 3000);

        // Authoritative server calculation, *before* SPELL_START and cast
        // timer creation. One player cannot change another's mount time.
        castTime = int32(intendedMs);
    }
};
#endif

void AddEraMountCastScripts()
{
#if defined(AC_HAS_AFTER_CALC_SPELL_CAST_TIME)
    new NaxxramasEraMountCastScript();
#endif
}
