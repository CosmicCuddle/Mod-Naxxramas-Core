/*
 * Naxxramas Core
 * Racials - Orc - Blood Fury
 *
 * Blood Fury variants:
 * 20572 - Blood Fury
 * 33697 - Blood Fury
 * 33702 - Blood Fury
 *
 * 23230 - Blood Fury healing reduction
 *
 * Keeps the WotLK Blood Fury offensive bonuses while restoring
 * the 50% healing-received penalty for 25 seconds.
 */

#include "SpellAuras.h"
#include "SpellInfo.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "Unit.h"

enum OrcBloodFurySpells
{
    SPELL_BLOOD_FURY_HEALING_REDUCTION = 23230
};

class spell_custom_orc_blood_fury_healing_reduction : public SpellScript
{
    PrepareSpellScript(spell_custom_orc_blood_fury_healing_reduction);

    bool Validate(SpellInfo const* /*spellInfo*/) override
    {
        return ValidateSpellInfo({ SPELL_BLOOD_FURY_HEALING_REDUCTION });
    }

    void HandleAfterCast()
    {
        Unit* caster = GetCaster();
        if (!caster)
            return;

        // Apply the preserved pre-Wrath Blood Fury healing penalty.
        caster->CastSpell(
            caster,
            SPELL_BLOOD_FURY_HEALING_REDUCTION,
            TRIGGERED_FULL_MASK);

        // The restored penalty lasts 25 seconds, independently of
        // the duration of the WotLK offensive Blood Fury buff.
        if (Aura* aura = caster->GetAura(SPELL_BLOOD_FURY_HEALING_REDUCTION))
        {
            aura->SetMaxDuration(25 * IN_MILLISECONDS);
            aura->SetDuration(25 * IN_MILLISECONDS);
        }
    }

    void Register() override
    {
        AfterCast += SpellCastFn(
            spell_custom_orc_blood_fury_healing_reduction::HandleAfterCast);
    }
};

void AddOrcBloodFuryScripts()
{
    RegisterSpellScript(spell_custom_orc_blood_fury_healing_reduction);
}