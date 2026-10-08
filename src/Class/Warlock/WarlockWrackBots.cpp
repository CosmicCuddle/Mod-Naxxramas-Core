/*
 * Naxxramas Core
 * Class - Warlock - Wrack Playerbot support
 *
 * Keeps Wrack integration inside Mod-Naxxramas-Core instead of modifying
 * mod-playerbots itself.
 *
 * Behaviour:
 * - Affliction Playerbots with Shadow Mastery 5/5 are kept in sync with Wrack.
 * - Wrack replaces ordinary Shadow Bolt filler once the Affliction setup is active.
 * - Nightfall / Shadow Trance instant Shadow Bolts are preserved.
 * - Drain Soul execute below 20% target health is preserved.
 * - Wrack is only started when the important Affliction effects have enough
 *   duration remaining to survive the six-second channel.
 */

#include "AiFactory.h"
#include "AiObjectContext.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "Spell.h"
#include "SpellAuras.h"
#include "Unit.h"

#include <array>
#include <string>
#include <string_view>
#include <unordered_map>

namespace NaxxramasWrackBots
{
    constexpr uint32 SPELL_SHADOW_MASTERY_RANK_5 = 18275;
    constexpr uint32 SPELL_WRACK = 90058;
    constexpr uint32 SPELL_SHADOW_TRANCE = 17941;

    constexpr uint32 UPDATE_INTERVAL_MS = 100;
    constexpr int32 MIN_AURA_REMAINING_MS = 7000;
    constexpr uint8 DRAIN_SOUL_EXECUTE_PCT = 20;

    std::unordered_map<ObjectGuid::LowType, uint32> UpdateTimers;

    bool AuraHasEnoughTime(
        PlayerbotAI* botAI,
        Unit* target,
        std::string_view spellName)
    {
        if (!botAI || !target)
            return false;

        Aura* aura =
            botAI->GetAura(
                std::string(spellName),
                target,
                true,
                false);

        if (!aura)
            return false;

        int32 duration = aura->GetDuration();

        return duration < 0 ||
            duration >= MIN_AURA_REMAINING_MS;
    }

    bool KnownAuraHasEnoughTime(
        PlayerbotAI* botAI,
        Unit* target,
        std::string_view spellName)
    {
        if (!botAI)
            return false;

        std::string name(spellName);

        // Progression-safe: if this Affliction spell is not available to the
        // bot at its current progression/level, do not require it before Wrack.
        if (!botAI->HasSpell(name))
            return true;

        return AuraHasEnoughTime(
            botAI,
            target,
            spellName);
    }

    bool HasMaintainedCurse(
        PlayerbotAI* botAI,
        Unit* target)
    {
        static constexpr std::array<std::string_view, 6> curses =
        {
            "curse of agony",
            "curse of doom",
            "curse of the elements",
            "curse of exhaustion",
            "curse of tongues",
            "curse of weakness"
        };

        bool knowsAnyCurse = false;

        for (std::string_view curse : curses)
        {
            std::string name(curse);

            if (!botAI->HasSpell(name))
                continue;

            knowsAnyCurse = true;

            if (AuraHasEnoughTime(
                    botAI,
                    target,
                    curse))
            {
                return true;
            }
        }

        // This should only matter at unusual low-level/custom progression
        // states. If no supported curse exists, do not block Wrack filler.
        return !knowsAnyCurse;
    }

    void SyncBotWrack(Player* bot)
    {
        if (!bot ||
            bot->getClass() != CLASS_WARLOCK)
        {
            return;
        }

        bool shouldKnowWrack =
            bot->HasTalent(
                SPELL_SHADOW_MASTERY_RANK_5,
                bot->GetActiveSpec());

        bool knowsWrack =
            bot->HasSpell(SPELL_WRACK);

        if (shouldKnowWrack && !knowsWrack)
        {
            bot->learnSpell(
                SPELL_WRACK,
                false);
            return;
        }

        if (!shouldKnowWrack && knowsWrack)
        {
            bot->removeSpell(
                SPELL_WRACK,
                bot->GetActiveSpecMask(),
                false);
        }
    }

    bool ShouldCastWrack(
        Player* bot,
        PlayerbotAI* botAI,
        Unit* target)
    {
        if (!bot ||
            !botAI ||
            !target ||
            !bot->IsAlive() ||
            !bot->IsInCombat() ||
            bot->getClass() != CLASS_WARLOCK ||
            !bot->HasSpell(SPELL_WRACK))
        {
            return false;
        }

        if (AiFactory::GetPlayerSpecTab(bot) !=
            WARLOCK_TAB_AFFLICTION)
        {
            return false;
        }

        if (!bot->HasTalent(
                SPELL_SHADOW_MASTERY_RANK_5,
                bot->GetActiveSpec()))
        {
            return false;
        }

        if (!target->IsAlive() ||
            !bot->IsValidAttackTarget(target) ||
            !target->HealthAbovePct(
                DRAIN_SOUL_EXECUTE_PCT))
        {
            return false;
        }

        // Do not interfere with an existing cast or channel.
        if (bot->GetCurrentSpell(
                CURRENT_GENERIC_SPELL) ||
            bot->GetCurrentSpell(
                CURRENT_CHANNELED_SPELL))
        {
            return false;
        }

        // Nightfall / Shadow Trance should still spend its free instant
        // Shadow Bolt instead of beginning another Wrack channel.
        if (bot->HasAura(
                SPELL_SHADOW_TRANCE))
        {
            return false;
        }

        // Corruption is the core effect Wrack is intended to amplify.
        if (!AuraHasEnoughTime(
                botAI,
                target,
                "corruption"))
        {
            return false;
        }

        // Require these only when the bot actually knows them. This keeps the
        // behaviour compatible with lower levels and progression restrictions.
        if (!KnownAuraHasEnoughTime(
                botAI,
                target,
                "unstable affliction"))
        {
            return false;
        }

        if (!KnownAuraHasEnoughTime(
                botAI,
                target,
                "haunt"))
        {
            return false;
        }

        // Give the normal Playerbot curse strategy its refresh window too.
        if (!HasMaintainedCurse(
                botAI,
                target))
        {
            return false;
        }

        return botAI->CanCastSpell(
            SPELL_WRACK,
            target);
    }

    void UpdateWrackBot(
        Player* bot,
        uint32 diff)
    {
        if (!bot ||
            bot->getClass() != CLASS_WARLOCK)
        {
            return;
        }

        PlayerbotAI* botAI =
            PlayerbotsMgr::instance().
                GetPlayerbotAI(bot);

        if (!botAI)
            return;

        ObjectGuid::LowType guid =
            bot->GetGUID().GetCounter();

        uint32& timer =
            UpdateTimers[guid];

        if (timer > diff)
        {
            timer -= diff;
            return;
        }

        timer = UPDATE_INTERVAL_MS;

        SyncBotWrack(bot);

        if (!bot->HasSpell(SPELL_WRACK))
            return;

        Unit* target =
            botAI->
                GetAiObjectContext()->
                GetValue<Unit*>(
                    "current target")->
                Get();

        if (!ShouldCastWrack(
                bot,
                botAI,
                target))
        {
            return;
        }

        botAI->CastSpell(
            SPELL_WRACK,
            target);
    }
}

class NaxxramasCoreWarlockWrackBots :
    public PlayerScript
{
public:
    NaxxramasCoreWarlockWrackBots()
        : PlayerScript(
            "NaxxramasCoreWarlockWrackBots",
            {
                PLAYERHOOK_ON_BEFORE_UPDATE,
                PLAYERHOOK_ON_LOGOUT
            })
    {
    }

    void OnPlayerBeforeUpdate(
        Player* player,
        uint32 diff) override
    {
        NaxxramasWrackBots::
            UpdateWrackBot(
                player,
                diff);
    }

    void OnPlayerLogout(
        Player* player) override
    {
        if (!player)
            return;

        NaxxramasWrackBots::
            UpdateTimers.erase(
                player->
                    GetGUID().
                    GetCounter());
    }
};

void AddWarlockWrackBotScripts()
{
    new NaxxramasCoreWarlockWrackBots();
}
