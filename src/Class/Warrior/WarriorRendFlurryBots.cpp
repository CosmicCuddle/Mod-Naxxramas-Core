/*
 * Naxxramas Core
 * Class - Warrior - Rend Flurry Playerbot support
 *
 * Keeps Rend Flurry integration inside Mod-Naxxramas-Core instead of
 * modifying mod-playerbots itself.
 *
 * Behaviour:
 * - Only Arms Playerbots that actually know Rend Flurry can use it.
 * - Activates Rend Flurry when the current target has at least one other
 *   suitable hostile target within 8 yards.
 * - A bleed-immune primary target is also considered a valid opportunity,
 *   allowing the existing Rend Flurry Strike replacement mechanic to work.
 * - Battle Stance and Defensive Stance are supported.
 * - Berserker Stance is deliberately excluded.
 * - The normal Playerbot Rend action remains responsible for casting Rend.
 */

#include "AiFactory.h"
#include "AiObjectContext.h"
#include "Cell.h"
#include "CellImpl.h"
#include "Creature.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "Spell.h"
#include "Unit.h"

#include <list>
#include <unordered_map>

namespace NaxxramasRendFlurryBots
{
    constexpr uint32 SPELL_REND_FLURRY = 90054;

    constexpr uint32 SPELL_BATTLE_STANCE = 2457;
    constexpr uint32 SPELL_DEFENSIVE_STANCE = 71;

    constexpr float REND_FLURRY_RADIUS = 8.0f;
    constexpr uint32 UPDATE_INTERVAL_MS = 200;
    constexpr uint8 MIN_PRIMARY_TARGET_HEALTH_PCT = 20;

    std::unordered_map<ObjectGuid::LowType, uint32> UpdateTimers;

    bool IsBleedImmune(Unit* target)
    {
        if (!target)
            return false;

        if (Creature* creature = target->ToCreature())
        {
            if (creature->HasMechanicTemplateImmunity(
                    1ULL << MECHANIC_BLEED))
            {
                return true;
            }
        }

        auto const& mechanicImmunities =
            target->m_spellImmune[IMMUNITY_MECHANIC];

        return mechanicImmunities.find(
            MECHANIC_BLEED) !=
            mechanicImmunities.end();
    }

    bool HasNearbyAdditionalTarget(
        Player* bot,
        Unit* primaryTarget)
    {
        if (!bot || !primaryTarget)
            return false;

        std::list<Unit*> nearbyTargets;

        Acore::AnyUnfriendlyUnitInObjectRangeCheck check(
            primaryTarget,
            bot,
            REND_FLURRY_RADIUS);

        Acore::UnitListSearcher<
            Acore::AnyUnfriendlyUnitInObjectRangeCheck>
            searcher(
                primaryTarget,
                nearbyTargets,
                check);

        Cell::VisitObjects(
            primaryTarget,
            searcher,
            REND_FLURRY_RADIUS);

        for (Unit* target : nearbyTargets)
        {
            if (!target ||
                target == primaryTarget ||
                !target->IsAlive() ||
                !bot->IsValidAttackTarget(target) ||
                !primaryTarget->IsWithinLOSInMap(target))
            {
                continue;
            }

            return true;
        }

        return false;
    }

    bool HasRendFlurryOpportunity(
        Player* bot,
        Unit* primaryTarget)
    {
        if (!bot || !primaryTarget)
            return false;

        // On bleed-immune enemies Rend Flurry converts Rend attempts into
        // the 150% weapon-damage replacement strike.
        if (IsBleedImmune(primaryTarget))
            return true;

        // Normal use: primary target plus at least one nearby hostile target.
        return HasNearbyAdditionalTarget(
            bot,
            primaryTarget);
    }

    bool ShouldActivateRendFlurry(
        Player* bot,
        PlayerbotAI* botAI,
        Unit* target)
    {
        if (!bot ||
            !botAI ||
            !target ||
            !bot->IsAlive() ||
            !bot->IsInCombat() ||
            bot->getClass() != CLASS_WARRIOR ||
            !bot->HasSpell(SPELL_REND_FLURRY))
        {
            return false;
        }

        if (AiFactory::GetPlayerSpecTab(bot) !=
            WARRIOR_TAB_ARMS)
        {
            return false;
        }

        if (!target->IsAlive() ||
            !bot->IsValidAttackTarget(target) ||
            !target->HealthAbovePct(
                MIN_PRIMARY_TARGET_HEALTH_PCT))
        {
            return false;
        }

        // Rend itself is still cast by the normal Arms Playerbot rotation.
        if (!botAI->HasSpell("rend"))
            return false;

        // Do not interfere with another spell that is already underway.
        if (bot->GetCurrentSpell(
                CURRENT_GENERIC_SPELL) ||
            bot->GetCurrentSpell(
                CURRENT_CHANNELED_SPELL))
        {
            return false;
        }

        // Rend Flurry is intended for Battle/Defensive Stance only.
        if (!bot->HasAura(SPELL_BATTLE_STANCE) &&
            !bot->HasAura(SPELL_DEFENSIVE_STANCE))
        {
            return false;
        }

        if (bot->HasAura(SPELL_REND_FLURRY) ||
            bot->HasSpellCooldown(SPELL_REND_FLURRY))
        {
            return false;
        }

        if (!bot->IsWithinMeleeRange(target))
            return false;

        if (!HasRendFlurryOpportunity(
                bot,
                target))
        {
            return false;
        }

        return botAI->CanCastSpell(
            SPELL_REND_FLURRY,
            bot);
    }

    void UpdateRendFlurryBot(
        Player* bot,
        uint32 diff)
    {
        if (!bot ||
            bot->getClass() != CLASS_WARRIOR)
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

        if (!bot->HasSpell(SPELL_REND_FLURRY))
            return;

        Unit* target =
            botAI->
                GetAiObjectContext()->
                GetValue<Unit*>(
                    "current target")->
                Get();

        if (!ShouldActivateRendFlurry(
                bot,
                botAI,
                target))
        {
            return;
        }

        botAI->CastSpell(
            SPELL_REND_FLURRY,
            bot);
    }
}

class NaxxramasCoreWarriorRendFlurryBots :
    public PlayerScript
{
public:
    NaxxramasCoreWarriorRendFlurryBots()
        : PlayerScript(
            "NaxxramasCoreWarriorRendFlurryBots",
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
        NaxxramasRendFlurryBots::
            UpdateRendFlurryBot(
                player,
                diff);
    }

    void OnPlayerLogout(
        Player* player) override
    {
        if (!player)
            return;

        NaxxramasRendFlurryBots::
            UpdateTimers.erase(
                player->
                    GetGUID().
                    GetCounter());
    }
};

void AddWarriorRendFlurryBotScripts()
{
    new NaxxramasCoreWarriorRendFlurryBots();
}
