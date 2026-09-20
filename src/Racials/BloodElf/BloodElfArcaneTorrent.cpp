/*
 * Naxxramas Core
 * Racials - Blood Elf - Arcane Torrent
 *
 * 28730 - Arcane Torrent (Mana)
 * 25046 - Arcane Torrent (Energy)
 *
 * 28734 - Mana Tap
 * 28733 - Arcane Torrent Mana Restore
 * 25048 - Arcane Torrent Energy Restore
 *
 * Keeps the WotLK Arcane Torrent silence while restoring
 * the original Mana Tap charge interaction.
 */

#include "Define.h"
#include "SpellAuras.h"
#include "SpellInfo.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "Unit.h"

enum BloodElfArcaneTorrentSpells
{
    SPELL_MANA_TAP                       = 28734,
    SPELL_ARCANE_TORRENT_MANA            = 28730,
    SPELL_ARCANE_TORRENT_ENERGY          = 25046,
    SPELL_ARCANE_TORRENT_MANA_RESTORE    = 28733,
    SPELL_ARCANE_TORRENT_ENERGY_RESTORE  = 25048
};

class spell_custom_blood_elf_arcane_torrent : public SpellScript
{
    PrepareSpellScript(spell_custom_blood_elf_arcane_torrent);

    bool Validate(SpellInfo const* /*spellInfo*/) override
    {
        return ValidateSpellInfo(
        {
            SPELL_MANA_TAP,
            SPELL_ARCANE_TORRENT_MANA,
            SPELL_ARCANE_TORRENT_ENERGY,
            SPELL_ARCANE_TORRENT_MANA_RESTORE,
            SPELL_ARCANE_TORRENT_ENERGY_RESTORE
        });
    }

    void PreventWrathResourceRestore(SpellEffIndex effIndex)
    {
        // Prevent the normal WotLK flat resource restoration.
        //
        // The 2-second silence remains completely untouched.
        PreventHitDefaultEffect(effIndex);
    }

    void RestoreManaTapResource()
    {
        Unit* caster = GetCaster();
        if (!caster)
            return;

        Aura* manaTap = caster->GetAura(SPELL_MANA_TAP);
        if (!manaTap)
            return;

        uint8 stacks = manaTap->GetStackAmount();
        if (!stacks)
            return;

        switch (GetSpellInfo()->Id)
        {
            case SPELL_ARCANE_TORRENT_MANA:
            {
                // Original Mana Tap-era Arcane Torrent formula:
                //
                // (2.17 * level + 9.136) * Mana Tap stacks
                //
                // Example at level 70:
                // 1 stack  = ~161 Mana
                // 3 stacks = ~483 Mana

                int32 amount = static_cast<int32>(
                    (2.17f * caster->GetLevel() + 9.136f) * stacks);

                caster->CastCustomSpell(
                    SPELL_ARCANE_TORRENT_MANA_RESTORE,
                    SPELLVALUE_BASE_POINT0,
                    amount,
                    caster,
                    TRIGGERED_FULL_MASK);

                break;
            }

            case SPELL_ARCANE_TORRENT_ENERGY:
            {
                // Original Rogue version:
                // 10 Energy per Mana Tap charge.

                int32 amount = 10 * stacks;

                caster->CastCustomSpell(
                    SPELL_ARCANE_TORRENT_ENERGY_RESTORE,
                    SPELLVALUE_BASE_POINT0,
                    amount,
                    caster,
                    TRIGGERED_FULL_MASK);

                break;
            }

            default:
                return;
        }

        // Arcane Torrent consumes all Mana Tap charges.
        caster->RemoveAurasDueToSpell(SPELL_MANA_TAP);
    }

    void Register() override
    {
        // Effect 1 in C++ = Effect_2 in the DBC.
        // We suppress only the WotLK resource restoration.
        OnEffectHitTarget += SpellEffectFn(
            spell_custom_blood_elf_arcane_torrent::PreventWrathResourceRestore,
            EFFECT_1,
            SPELL_EFFECT_ANY);

        AfterCast += SpellCastFn(
            spell_custom_blood_elf_arcane_torrent::RestoreManaTapResource);
    }
};

void AddBloodElfArcaneTorrentScripts()
{
    RegisterSpellScript(spell_custom_blood_elf_arcane_torrent);
}