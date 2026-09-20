/*
 * Naxxramas Core
 * Class - Warrior - Rend / Flurry Customizations
 *
 * 90054 - Rend Flurry
 * 90055 - Rend Flurry Strike
 * 90056 - Rend Flurry Internal Cooldown
 */

#include "Cell.h"
#include "CellImpl.h"
#include "Creature.h"
#include "GridNotifiers.h"
#include "GridNotifiersImpl.h"
#include "Spell.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "Unit.h"

#include <list>

enum RendFlurrySpells
{
    SPELL_REND_FLURRY                   = 90054,
    SPELL_REND_FLURRY_STRIKE            = 90055,
    SPELL_REND_FLURRY_INTERNAL_COOLDOWN = 90056
};

constexpr float REND_FLURRY_RADIUS = 8.0f;
constexpr uint32 REND_FLURRY_EXTRA_TARGETS = 2;

/*
 * Returns true only when the target is specifically immune
 * to the BLEED mechanic.
 *
 * We deliberately do NOT use general spell immunity here.
 * A target being immune because of some unrelated mechanic
 * must not receive the 150% weapon-damage replacement hit.
 */
static bool IsRendFlurryBleedImmune(Unit* target)
{
    if (!target)
        return false;

    // Creature template mechanic immunity.
    if (Creature* creature = target->ToCreature())
    {
        if (creature->HasMechanicTemplateImmunity(1ULL << MECHANIC_BLEED))
            return true;
    }

    // Runtime mechanic immunity, such as an immunity applied by an aura/script.
    auto const& mechanicImmunities = target->m_spellImmune[IMMUNITY_MECHANIC];

    return mechanicImmunities.find(MECHANIC_BLEED) != mechanicImmunities.end();
}

/*
 * Attached to the entire Rend rank chain.
 *
 * The original player-cast Rend is left alone.
 * While Rend Flurry is active:
 *
 * - Primary target keeps its normal Rend.
 * - Up to 2 additional enemies within 8 yards are selected.
 * - Bleed-capable additional enemies receive the same Rend rank.
 * - Bleed-immune targets receive Rend Flurry Strike instead.
 * - The replacement strike has a 2-second internal cooldown.
 */
class spell_custom_warr_rend_flurry : public SpellScript
{
    PrepareSpellScript(spell_custom_warr_rend_flurry);

    bool Validate(SpellInfo const* /*spellInfo*/) override
    {
        return ValidateSpellInfo(
        {
            SPELL_REND_FLURRY,
            SPELL_REND_FLURRY_STRIKE,
            SPELL_REND_FLURRY_INTERNAL_COOLDOWN
        });
    }

    void HandleAfterCast()
    {
        Unit* caster = GetCaster();
        Unit* primaryTarget = GetExplTargetUnit();

        if (!caster || !primaryTarget)
            return;

        /*
         * Extra Rend applications are triggered casts.
         *
         * Without this check, an extra Rend could trigger Rend Flurry
         * again and continually spread to more enemies.
         */
        if (GetSpell()->IsTriggered())
            return;

        // Rend Flurry is not currently active.
        if (!caster->HasAura(SPELL_REND_FLURRY))
            return;

        uint32 rendSpellId = GetSpellInfo()->Id;

        /*
         * Take a snapshot of the internal cooldown BEFORE processing
         * the targets.
         *
         * This allows one Rend cast to replacement-strike multiple
         * bleed-immune targets, then starts one shared 2-second ICD.
         */
        bool replacementStrikeAvailable =
            !caster->HasAura(SPELL_REND_FLURRY_INTERNAL_COOLDOWN);

        bool replacementStrikeUsed = false;

        /*
         * PRIMARY TARGET
         *
         * Normal Rend has already attempted to apply to this target.
         * We only need to intervene when it is specifically bleed immune.
         */
        if (IsRendFlurryBleedImmune(primaryTarget))
        {
            if (replacementStrikeAvailable)
            {
                caster->CastSpell(
                    primaryTarget,
                    SPELL_REND_FLURRY_STRIKE,
                    TRIGGERED_FULL_MASK);

                replacementStrikeUsed = true;
            }
        }

        /*
         * Find hostile units within 8 yards of the PRIMARY target.
         */
        std::list<Unit*> nearbyTargets;

        Acore::AnyUnfriendlyUnitInObjectRangeCheck check(
            primaryTarget,
            caster,
            REND_FLURRY_RADIUS);

        Acore::UnitListSearcher<
            Acore::AnyUnfriendlyUnitInObjectRangeCheck>
            searcher(primaryTarget, nearbyTargets, check);

        Cell::VisitObjects(
            primaryTarget,
            searcher,
            REND_FLURRY_RADIUS);

        /*
         * Remove anything that should not become an additional target.
         */
        nearbyTargets.remove_if(
            [caster, primaryTarget, rendSpellId](Unit* target)
            {
                if (!target)
                    return true;

                // Primary target is already handled separately.
                if (target == primaryTarget)
                    return true;

                if (!target->IsAlive())
                    return true;

                // Must be a legitimate hostile target for Rend.
                if (!caster->IsValidAttackTarget(
                        target,
                        sSpellMgr->GetSpellInfo(rendSpellId)))
                    return true;

                // Prevent spreading through walls.
                if (!primaryTarget->IsWithinLOSInMap(target))
                    return true;

                return false;
            });

        /*
         * Nearest enemies to the primary target are chosen first.
         */
        nearbyTargets.sort(
            [primaryTarget](Unit* left, Unit* right)
            {
                return primaryTarget->GetDistance(left) <
                       primaryTarget->GetDistance(right);
            });

        /*
         * Maximum of 2 additional enemies.
         */
        if (nearbyTargets.size() > REND_FLURRY_EXTRA_TARGETS)
            nearbyTargets.resize(REND_FLURRY_EXTRA_TARGETS);

        /*
         * Process the two additional targets.
         */
        for (Unit* target : nearbyTargets)
        {
            if (IsRendFlurryBleedImmune(target))
            {
                /*
                 * Bleed immune:
                 * replace Rend with the 150% weapon-damage strike.
                 */
                if (replacementStrikeAvailable)
                {
                    caster->CastSpell(
                        target,
                        SPELL_REND_FLURRY_STRIKE,
                        TRIGGERED_FULL_MASK);

                    replacementStrikeUsed = true;
                }

                continue;
            }

            /*
             * Bleed capable:
             * cast the SAME Rend rank the player originally used.
             *
             * Triggered casting means:
             * - no extra rage cost
             * - no extra GCD
             *
             * Our IsTriggered() check above prevents recursion.
             */
            caster->CastSpell(
                target,
                rendSpellId,
                TRIGGERED_FULL_MASK);
        }

        /*
         * Only begin the 2-second ICD if at least one
         * replacement weapon strike actually fired.
         */
        if (replacementStrikeUsed)
        {
            caster->CastSpell(
                caster,
                SPELL_REND_FLURRY_INTERNAL_COOLDOWN,
                TRIGGERED_FULL_MASK);
        }
    }

    void Register() override
    {
        AfterCast += SpellCastFn(
            spell_custom_warr_rend_flurry::HandleAfterCast);
    }
};

void AddWarriorRendFlurryScripts()
{
    RegisterSpellScript(spell_custom_warr_rend_flurry);
}