/*
 * Naxxramas Core
 * Racials - Troll - Berserking
 *
 * 26297 - Berserking
 *
 * Keeps the WotLK 20% haste baseline while restoring
 * health-based scaling up to 30% at 10% health or lower.
 */

#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "Unit.h"

class spell_custom_troll_berserking : public AuraScript
{
    PrepareAuraScript(spell_custom_troll_berserking);

    void CalculateAmount(
        AuraEffect const* /*aurEff*/,
        int32& amount,
        bool& canBeRecalculated)
    {
        Unit* target = GetUnitOwner();
        if (!target)
            return;

        float healthPct = target->GetHealthPct();

        // Healthy Trolls retain the normal WotLK 20% Berserking.
        if (healthPct >= 50.0f)
        {
            amount = 20;
        }
        // At 10% health or lower, Berserking reaches 30%.
        else if (healthPct <= 10.0f)
        {
            amount = 30;
        }
        // Between 50% and 10% health, scale progressively
        // from 20% to 30%.
        else
        {
            float scaledAmount =
                20.0f + ((50.0f - healthPct) / 40.0f) * 10.0f;

            amount = static_cast<int32>(scaledAmount + 0.5f);
        }

        // Snapshot the haste amount when Berserking is activated.
        canBeRecalculated = false;
    }

    void Register() override
    {
        DoEffectCalcAmount += AuraEffectCalcAmountFn(
            spell_custom_troll_berserking::CalculateAmount,
            EFFECT_0,
            SPELL_AURA_ANY);
    }
};

void AddTrollBerserkingScripts()
{
    RegisterSpellScript(spell_custom_troll_berserking);
}