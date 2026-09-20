/*
 * Naxxramas Core
 * Class - Warrior - Improved Rend
 *
 * 90057 - Improved Rend Rank 3
 *
 * Each valid Rend periodic damage tick has a 3% chance
 * to generate 25 Rage for the Warrior.
 */

#include "Random.h"
#include "ScriptMgr.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "Unit.h"

enum ImprovedRendSpells
{
    SPELL_WARRIOR_REND_RANK_1           = 772,
    SPELL_WARRIOR_IMPROVED_REND_RANK_3  = 90057
};

constexpr int32 IMPROVED_REND_RAGE_GAIN = 250; // 25 Rage; Rage is stored internally x10.

class spell_custom_warr_improved_rend : public UnitScript
{
public:
    spell_custom_warr_improved_rend()
        : UnitScript(
            "spell_custom_warr_improved_rend",
            true,
            { UNITHOOK_MODIFY_PERIODIC_DAMAGE_AURAS_TICK })
    {
    }

    void ModifyPeriodicDamageAurasTick(
        Unit* /*target*/,
        Unit* attacker,
        uint32& damage,
        SpellInfo const* spellInfo) override
    {
        if (!attacker || !spellInfo || damage == 0)
            return;

        // Only Rend, including every rank of Rend.
        if (sSpellMgr->GetFirstSpellInChain(spellInfo->Id) != SPELL_WARRIOR_REND_RANK_1)
            return;

        // Only Warriors with Improved Rend Rank 3.
        if (!attacker->HasAura(SPELL_WARRIOR_IMPROVED_REND_RANK_3))
            return;

        // 3% chance per valid Rend periodic damage tick.
        if (!roll_chance_i(3))
            return;

        // Add 25 Rage.
        int32 const rageGained = attacker->ModifyPower(
            POWER_RAGE,
            IMPROVED_REND_RAGE_GAIN);

        // Show the Rage gain in the combat log.
        if (rageGained > 0)
        {
            attacker->SendEnergizeSpellLog(
                attacker,
                SPELL_WARRIOR_IMPROVED_REND_RANK_3,
                uint32(rageGained),
                POWER_RAGE);
        }
    }
};

void AddWarriorImprovedRendScripts()
{
    new spell_custom_warr_improved_rend();
}