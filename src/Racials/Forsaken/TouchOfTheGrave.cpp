/*
 * Naxxramas Core
 * Racials - Forsaken - Touch of the Grave
 *
 * 90052 - Touch of the Grave (Passive)
 * 90053 - Touch of the Grave (Health Leech)
 *
 * Custom level scaling with Individual Progression
 * damage and healing compensation.
 *
 * Intended final damage:
 *
 * Level 1  =   5
 * Level 20 =  35
 * Level 40 =  70
 * Level 60 = 150
 * Level 70 = 300
 * Level 80 = 600
 */

#include "Config.h"
#include "Define.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "SpellInfo.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "Unit.h"

#include <cmath>

namespace NaxxramasTouchOfTheGrave
{
    constexpr uint32 SPELL_TOUCH_OF_THE_GRAVE_DAMAGE = 90053;

    constexpr uint8 PROGRESSION_PRE_TBC = 8;
    constexpr uint8 PROGRESSION_TBC_TIER_5 = 13;

    uint8 GetProgression(Player* player)
    {
        if (!player || !player->IsInWorld())
            return 0;

        uint8 progression = 0;

        /*
         * Individual Progression stores progression using
         * rewarded hidden quests 66001 through 66018.
         */
        for (uint8 i = 1; i <= 18; ++i)
        {
            uint32 questId = 66000 + i;

            if (player->GetQuestStatus(questId) == QUEST_STATUS_REWARDED)
                progression = i;
        }

        return progression;
    }

    bool HasPassedProgression(
        uint8 progression,
        uint8 requiredProgression,
        uint8 progressionLimit)
    {
        if (!requiredProgression)
            return false;

        if (progressionLimit &&
            requiredProgression > progressionLimit)
        {
            return false;
        }

        return progression >= requiredProgression;
    }

    float GetProgressionMultiplier(
        Player* player,
        float vanillaAdjustment,
        float tbcAdjustment)
    {
        if (!player)
            return 1.0f;

        /*
         * Individual Progression itself defaults Enable to true,
         * so we mirror that behaviour here.
         */
        bool enabled =
            sConfigMgr->GetOption<bool>(
                "IndividualProgression.Enable",
                true);

        if (!enabled)
            return 1.0f;

        uint8 progressionLimit =
            sConfigMgr->GetOption<uint8>(
                "IndividualProgression.ProgressionLimit",
                0);

        uint8 progression =
            GetProgression(player);

        /*
         * Vanilla progression
         */
        if (!HasPassedProgression(
                progression,
                PROGRESSION_PRE_TBC,
                progressionLimit))
        {
            uint8 level = player->GetLevel();

            if (level <= 10)
                return 1.0f;

            /*
             * Same Vanilla adjustment formula used by
             * Individual Progression:
             *
             * adjustmentApplyPercent =
             *     (level - 10) / 50
             *
             * result =
             *     1 - ((1 - configuredAdjustment)
             *     * adjustmentApplyPercent)
             */
            float adjustmentApplyPercent =
                (float(level) - 10.0f) / 50.0f;

            return 1.0f -
                ((1.0f - vanillaAdjustment) *
                 adjustmentApplyPercent);
        }

        /*
         * TBC progression
         */
        if (!HasPassedProgression(
                progression,
                PROGRESSION_TBC_TIER_5,
                progressionLimit))
        {
            return tbcAdjustment;
        }

        /*
         * WotLK progression
         */
        return 1.0f;
    }

    float GetPowerMultiplier(Player* player)
    {
        float vanillaAdjustment =
            sConfigMgr->GetOption<float>(
                "IndividualProgression.VanillaPowerAdjustment",
                1.0f);

        float tbcAdjustment =
            sConfigMgr->GetOption<float>(
                "IndividualProgression.TBCPowerAdjustment",
                1.0f);

        return GetProgressionMultiplier(
            player,
            vanillaAdjustment,
            tbcAdjustment);
    }

    float GetHealingMultiplier(Player* player)
    {
        float vanillaAdjustment =
            sConfigMgr->GetOption<float>(
                "IndividualProgression.VanillaHealingAdjustment",
                1.0f);

        float tbcAdjustment =
            sConfigMgr->GetOption<float>(
                "IndividualProgression.TBCHealingAdjustment",
                1.0f);

        return GetProgressionMultiplier(
            player,
            vanillaAdjustment,
            tbcAdjustment);
    }

    int32 GetDesiredDamage(uint8 level)
    {
        if (level > 80)
            level = 80;

        int32 amount = 5;

        if (level <= 20)
        {
            amount =
                5 +
                ((level - 1) * 30 / 19);
        }
        else if (level <= 40)
        {
            amount =
                35 +
                ((level - 20) * 35 / 20);
        }
        else if (level <= 60)
        {
            amount =
                70 +
                ((level - 40) * 80 / 20);
        }
        else if (level <= 70)
        {
            amount =
                150 +
                ((level - 60) * 15);
        }
        else
        {
            amount =
                300 +
                ((level - 70) * 30);
        }

        return amount;
    }

    int32 CompensateAmount(
        int32 amount,
        float multiplier)
    {
        if (amount <= 0)
            return amount;

        if (multiplier <= 0.0f)
            return amount;

        if (std::fabs(multiplier - 1.0f) < 0.0001f)
            return amount;

        return static_cast<int32>(
            std::ceil(
                float(amount) /
                multiplier));
    }
}

// =========================================================
// 90053 - Touch of the Grave
// Damage scaling and power-adjustment compensation
// =========================================================

class spell_naxxramas_touch_of_the_grave : public SpellScript
{
    PrepareSpellScript(spell_naxxramas_touch_of_the_grave);

    void RecalculateDamage()
    {
        Unit* caster = GetCaster();

        if (!caster)
            return;

        uint8 level = caster->GetLevel();

        int32 desiredDamage =
            NaxxramasTouchOfTheGrave::
                GetDesiredDamage(level);

        float multiplier = 1.0f;

        if (Player* player = caster->ToPlayer())
        {
            multiplier =
                NaxxramasTouchOfTheGrave::
                    GetPowerMultiplier(player);
        }

        /*
         * Individual Progression applies its normal
         * spell-damage adjustment later.
         *
         * Increase the starting value just enough so
         * the final damage remains at our intended value.
         */
        int32 amount =
            NaxxramasTouchOfTheGrave::
                CompensateAmount(
                    desiredDamage,
                    multiplier);

        SetHitDamage(amount);
    }

    void Register() override
    {
        OnHit += SpellHitFn(
            spell_naxxramas_touch_of_the_grave::
                RecalculateDamage);
    }
};

// =========================================================
// 90053 - Touch of the Grave
// Healing-adjustment compensation
// =========================================================

class NaxxramasTouchOfTheGraveHealingScript : public UnitScript
{
public:
    NaxxramasTouchOfTheGraveHealingScript()
        : UnitScript(
            "NaxxramasTouchOfTheGraveHealingScript")
    {
    }

    void ModifyHealReceived(
        Unit* /*target*/,
        Unit* healer,
        uint32& heal,
        SpellInfo const* spellInfo) override
    {
        if (!spellInfo ||
            spellInfo->Id !=
                NaxxramasTouchOfTheGrave::
                    SPELL_TOUCH_OF_THE_GRAVE_DAMAGE)
        {
            return;
        }

        if (!healer || !heal)
            return;

        Player* player = healer->ToPlayer();

        if (!player)
            return;

        float multiplier =
            NaxxramasTouchOfTheGrave::
                GetHealingMultiplier(player);

        int32 compensatedHeal =
            NaxxramasTouchOfTheGrave::
                CompensateAmount(
                    static_cast<int32>(heal),
                    multiplier);

        if (compensatedHeal > 0)
        {
            heal =
                static_cast<uint32>(
                    compensatedHeal);
        }
    }
};

void AddTouchOfTheGraveScripts()
{
    RegisterSpellScript(
        spell_naxxramas_touch_of_the_grave);

    new NaxxramasTouchOfTheGraveHealingScript();
}