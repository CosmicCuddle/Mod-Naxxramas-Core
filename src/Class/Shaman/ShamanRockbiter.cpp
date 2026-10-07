/*
 * Naxxramas Core
 * Class - Shaman - Rockbiter Weapon
 *
 * Restores Classic / WoW Forever Rockbiter behaviour on AzerothCore 3.3.5:
 *
 * - Ranks 1-7 use the restored Rockbiter enchant IDs.
 * - The WotLK enchant's DPS-style bonus is suppressed.
 * - Rockbiter grants the original level-scaled melee attack power.
 * - Elemental Weapons modifies Rockbiter by 7% / 13% / 20% (Forever values).
 * - Successful melee auto attacks with the imbued weapon add the original
 *   rank-based Rockbiter threat.
 *
 * Spell.dbc supplies:
 *   90059 - hidden Rockbiter threat proc aura
 *   90060-90066 - hidden Rockbiter AP scaler spells, ranks 1-7
 *
 * SpellItemEnchantment.dbc is intentionally NOT modified.
 */

#include "Item.h"
#include "Player.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "SpellInfo.h"
#include "SpellMgr.h"
#include "SpellScript.h"
#include "SpellScriptLoader.h"
#include "ThreatManager.h"
#include "Unit.h"

#include <cmath>

namespace NaxxramasRockbiter
{
    constexpr uint32 SPELL_ROCKBITER_THREAT_AURA = 90059;

    constexpr uint32 SPELL_ROCKBITER_AP_RANK_1 = 90060;
    constexpr uint32 SPELL_ROCKBITER_AP_RANK_7 = 90066;

    constexpr uint32 SPELL_ELEMENTAL_WEAPONS_RANK_1 = 16266;
    constexpr uint32 SPELL_ELEMENTAL_WEAPONS_RANK_2 = 29079;
    constexpr uint32 SPELL_ELEMENTAL_WEAPONS_RANK_3 = 29080;

    /*
     * While AzerothCore is removing an enchant, the item still contains
     * the old enchant ID until Player::ApplyEnchantment() returns.
     *
     * Temporarily ignoring that item lets the AP recalculation see the
     * post-removal state without touching AzerothCore itself.
     */
    thread_local Item const* ignoredRockbiterItem = nullptr;

    uint8 GetRockbiterRank(uint32 enchantId)
    {
        switch (enchantId)
        {
            case 29:   return 1;
            case 6:    return 2;
            case 1:    return 3;
            case 503:  return 4;
            case 1663: return 5;
            case 683:  return 6;
            case 1664: return 7;
            default:   return 0;
        }
    }

    uint32 GetAttackPowerHelperSpell(uint8 rank)
    {
        if (rank < 1 || rank > 7)
            return 0;

        return SPELL_ROCKBITER_AP_RANK_1 + (rank - 1);
    }

    uint32 GetElementalWeaponsBonusPct(Player const* player)
    {
        if (!player)
            return 0;

        if (player->HasAura(SPELL_ELEMENTAL_WEAPONS_RANK_3))
            return 20;

        if (player->HasAura(SPELL_ELEMENTAL_WEAPONS_RANK_2))
            return 13;

        if (player->HasAura(SPELL_ELEMENTAL_WEAPONS_RANK_1))
            return 7;

        return 0;
    }

    int32 GetAttackPowerForRank(Player* player, uint8 rank)
    {
        if (!player)
            return 0;

        uint32 helperSpellId = GetAttackPowerHelperSpell(rank);
        SpellInfo const* helperSpell = sSpellMgr->GetSpellInfo(helperSpellId);

        if (!helperSpell)
            return 0;

        /*
         * The hidden helper spell contains the original Rockbiter
         * BasePoints / RealPointsPerLevel / MaxLevel values.
         *
         * Using CalcValue() means the same DBC data drives both the
         * tooltip and the server-side AP calculation.
         */
        int32 attackPower =
            helperSpell->Effects[EFFECT_0].CalcValue(player);

        uint32 elementalWeaponsPct =
            GetElementalWeaponsBonusPct(player);

        if (elementalWeaponsPct)
        {
            attackPower += static_cast<int32>(
                std::lround(
                    float(attackPower) *
                    float(elementalWeaponsPct) /
                    100.0f));
        }

        return attackPower;
    }

    Item* GetWeapon(Player* player, WeaponAttackType attackType)
    {
        if (!player)
            return nullptr;

        return player->GetWeaponForAttack(attackType, true);
    }

    uint8 GetWeaponRockbiterRank(
        Player* player,
        WeaponAttackType attackType,
        Item const* ignoredItem = nullptr)
    {
        Item* weapon = GetWeapon(player, attackType);

        if (!weapon || weapon == ignoredItem)
            return 0;

        return GetRockbiterRank(
            weapon->GetEnchantmentId(TEMP_ENCHANTMENT_SLOT));
    }

    bool HasAnyRockbiter(
        Player* player,
        Item const* ignoredItem = nullptr)
    {
        return
            GetWeaponRockbiterRank(
                player,
                BASE_ATTACK,
                ignoredItem) != 0 ||
            GetWeaponRockbiterRank(
                player,
                OFF_ATTACK,
                ignoredItem) != 0;
    }

    int32 GetTotalRockbiterAttackPower(
        Player* player,
        Item const* ignoredItem = nullptr)
    {
        if (!player ||
            player->getClass() != CLASS_SHAMAN)
        {
            return 0;
        }

        int32 total = 0;

        uint8 mainHandRank =
            GetWeaponRockbiterRank(
                player,
                BASE_ATTACK,
                ignoredItem);

        if (mainHandRank)
            total += GetAttackPowerForRank(player, mainHandRank);

        uint8 offHandRank =
            GetWeaponRockbiterRank(
                player,
                OFF_ATTACK,
                ignoredItem);

        if (offHandRank)
            total += GetAttackPowerForRank(player, offHandRank);

        return total;
    }

    float GetThreatPerSecond(uint8 rank)
    {
        switch (rank)
        {
            case 1: return 6.0f;
            case 2: return 10.0f;
            case 3: return 16.0f;
            case 4: return 27.0f;
            case 5: return 41.0f;
            case 6: return 55.0f;
            case 7: return 72.0f;
            default: return 0.0f;
        }
    }

    void SyncThreatAura(
        Player* player,
        Item const* ignoredItem = nullptr)
    {
        if (!player ||
            player->getClass() != CLASS_SHAMAN)
        {
            return;
        }

        bool shouldHaveAura =
            HasAnyRockbiter(player, ignoredItem);

        bool hasAura =
            player->HasAura(SPELL_ROCKBITER_THREAT_AURA);

        if (shouldHaveAura && !hasAura)
        {
            player->CastSpell(
                player,
                SPELL_ROCKBITER_THREAT_AURA,
                TRIGGERED_FULL_MASK);

            return;
        }

        if (!shouldHaveAura && hasAura)
        {
            player->RemoveAurasDueToSpell(
                SPELL_ROCKBITER_THREAT_AURA);
        }
    }

    /*
     * Returning false from PLAYERHOOK_CAN_APPLY_ENCHANTMENT prevents
     * AzerothCore from applying the WotLK ITEM_ENCHANTMENT_TYPE_TOTEM
     * damage bonus.
     *
     * Player::ApplyEnchantment() would normally do the visual/duration
     * bookkeeping after processing the enchant effects, so reproduce only
     * that bookkeeping here before returning false.
     */
    void MirrorEnchantBookkeeping(
        Player* player,
        Item* item,
        EnchantmentSlot slot,
        bool apply,
        bool applyDuration)
    {
        if (!player || !item)
            return;

        if (slot == TEMP_ENCHANTMENT_SLOT)
        {
            player->SetUInt16Value(
                PLAYER_VISIBLE_ITEM_1_ENCHANTMENT +
                    (item->GetSlot() * 2),
                1,
                apply ?
                    item->GetEnchantmentId(slot) :
                    0);
        }

        if (!applyDuration)
            return;

        if (apply)
        {
            uint32 duration =
                item->GetEnchantmentDuration(slot);

            if (duration > 0)
            {
                player->AddEnchantmentDuration(
                    item,
                    slot,
                    duration);
            }
        }
        else
        {
            player->AddEnchantmentDuration(
                item,
                slot,
                0);
        }
    }

    void RefreshRockbiter(Player* player)
    {
        if (!player ||
            player->getClass() != CLASS_SHAMAN)
        {
            return;
        }

        SyncThreatAura(player);

        player->UpdateAttackPowerAndDamage(false);
    }

    bool IsElementalWeaponsSpell(uint32 spellId)
    {
        return
            spellId == SPELL_ELEMENTAL_WEAPONS_RANK_1 ||
            spellId == SPELL_ELEMENTAL_WEAPONS_RANK_2 ||
            spellId == SPELL_ELEMENTAL_WEAPONS_RANK_3;
    }
}

/*
 * 90059 - hidden proc aura.
 *
 * Classic Rockbiter's extra threat is a fixed threat-per-second value.
 * On each successful swing:
 *
 *     bonus threat = rank TPS * base weapon speed
 *
 * Miss, dodge, parry, evade, immune and deflect do not generate the
 * Rockbiter bonus threat. Blocks/absorbs still count as landed attacks.
 */
class spell_custom_sha_rockbiter_threat : public AuraScript
{
    PrepareAuraScript(spell_custom_sha_rockbiter_threat);

    bool CheckProc(ProcEventInfo& eventInfo)
    {
        if (!(eventInfo.GetTypeMask() &
              PROC_FLAG_DONE_MELEE_AUTO_ATTACK))
        {
            return false;
        }

        DamageInfo* damageInfo =
            eventInfo.GetDamageInfo();

        if (!damageInfo)
            return false;

        WeaponAttackType attackType =
            damageInfo->GetAttackType();

        if (attackType != BASE_ATTACK &&
            attackType != OFF_ATTACK)
        {
            return false;
        }

        uint32 avoidedMask =
            PROC_HIT_MISS |
            PROC_HIT_DODGE |
            PROC_HIT_PARRY |
            PROC_HIT_EVADE |
            PROC_HIT_IMMUNE |
            PROC_HIT_DEFLECT;

        if (eventInfo.GetHitMask() & avoidedMask)
            return false;

        Player* player =
            GetTarget()->ToPlayer();

        if (!player ||
            player->getClass() != CLASS_SHAMAN)
        {
            return false;
        }

        return
            NaxxramasRockbiter::
                GetWeaponRockbiterRank(
                    player,
                    attackType) != 0;
    }

    void HandleProc(
        AuraEffect const* /*aurEff*/,
        ProcEventInfo& eventInfo)
    {
        PreventDefaultAction();

        Player* player =
            GetTarget()->ToPlayer();

        DamageInfo* damageInfo =
            eventInfo.GetDamageInfo();

        if (!player || !damageInfo)
            return;

        WeaponAttackType attackType =
            damageInfo->GetAttackType();

        Item* weapon =
            NaxxramasRockbiter::
                GetWeapon(
                    player,
                    attackType);

        if (!weapon)
            return;

        uint8 rank =
            NaxxramasRockbiter::
                GetRockbiterRank(
                    weapon->GetEnchantmentId(
                        TEMP_ENCHANTMENT_SLOT));

        if (!rank)
            return;

        Unit* victim =
            damageInfo->GetVictim();

        if (!victim)
            return;

        float threatPerSecond =
            NaxxramasRockbiter::
                GetThreatPerSecond(rank);

        if (threatPerSecond <= 0.0f)
            return;

        float weaponSpeedSeconds =
            float(weapon->GetTemplate()->Delay) /
            1000.0f;

        float bonusThreat =
            threatPerSecond *
            weaponSpeedSeconds;

        if (bonusThreat <= 0.0f)
            return;

        /*
         * Do not ignore threat modifiers here.
         *
         * This deliberately allows normal threat modifiers to affect
         * Rockbiter's bonus threat, which also leaves room for the
         * Forever Spirit Weapons rework to interact correctly later.
         */
        victim->GetThreatMgr().AddThreat(
            player,
            bonusThreat,
            GetSpellInfo());
    }

    void Register() override
    {
        DoCheckProc += AuraCheckProcFn(
            spell_custom_sha_rockbiter_threat::
                CheckProc);

        OnEffectProc += AuraEffectProcFn(
            spell_custom_sha_rockbiter_threat::
                HandleProc,
            EFFECT_0,
            SPELL_AURA_DUMMY);
    }
};

class NaxxramasCoreShamanRockbiter : public PlayerScript
{
public:
    NaxxramasCoreShamanRockbiter()
        : PlayerScript(
            "NaxxramasCoreShamanRockbiter",
            {
                PLAYERHOOK_ON_LOGIN,
                PLAYERHOOK_ON_LEVEL_CHANGED,
                PLAYERHOOK_ON_AFTER_SPEC_SLOT_CHANGED,
                PLAYERHOOK_ON_FORGOT_SPELL,
                PLAYERHOOK_ON_PLAYER_LEARN_TALENTS,
                PLAYERHOOK_ON_AFTER_UPDATE_ATTACK_POWER_AND_DAMAGE,
                PLAYERHOOK_CAN_APPLY_ENCHANTMENT
            })
    {
    }

    void OnPlayerLogin(Player* player) override
    {
        NaxxramasRockbiter::
            RefreshRockbiter(player);
    }

    void OnPlayerLevelChanged(
        Player* player,
        uint8 /*oldLevel*/) override
    {
        NaxxramasRockbiter::
            RefreshRockbiter(player);
    }

    void OnPlayerAfterSpecSlotChanged(
        Player* player,
        uint8 /*newSlot*/) override
    {
        NaxxramasRockbiter::
            RefreshRockbiter(player);
    }

    void OnPlayerForgotSpell(
        Player* player,
        uint32 spellId) override
    {
        if (!NaxxramasRockbiter::
                IsElementalWeaponsSpell(spellId))
        {
            return;
        }

        NaxxramasRockbiter::
            RefreshRockbiter(player);
    }

    void OnPlayerLearnTalents(
        Player* player,
        uint32 /*talentId*/,
        uint32 /*talentRank*/,
        uint32 spellId) override
    {
        if (!NaxxramasRockbiter::
                IsElementalWeaponsSpell(spellId))
        {
            return;
        }

        NaxxramasRockbiter::
            RefreshRockbiter(player);
    }

    void OnPlayerAfterUpdateAttackPowerAndDamage(
        Player* player,
        float& /*level*/,
        float& /*baseAttackPower*/,
        float& attackPowerMod,
        float& /*attackPowerMultiplier*/,
        bool ranged) override
    {
        if (!player ||
            player->getClass() != CLASS_SHAMAN ||
            ranged)
        {
            return;
        }

        attackPowerMod +=
            float(
                NaxxramasRockbiter::
                    GetTotalRockbiterAttackPower(
                        player,
                        NaxxramasRockbiter::
                            ignoredRockbiterItem));
    }

    bool OnPlayerCanApplyEnchantment(
        Player* player,
        Item* item,
        EnchantmentSlot slot,
        bool apply,
        bool applyDuration,
        bool /*ignoreCondition*/) override
    {
        if (!player ||
            !item ||
            player->getClass() != CLASS_SHAMAN ||
            slot != TEMP_ENCHANTMENT_SLOT)
        {
            return true;
        }

        uint8 rank =
            NaxxramasRockbiter::
                GetRockbiterRank(
                    item->GetEnchantmentId(slot));

        if (!rank)
            return true;

        /*
         * Keep the client-visible enchant and its timer, but suppress
         * AzerothCore's WotLK DPS-style Rockbiter enchant effect.
         */
        NaxxramasRockbiter::
            MirrorEnchantBookkeeping(
                player,
                item,
                slot,
                apply,
                applyDuration);

        if (apply)
        {
            NaxxramasRockbiter::
                SyncThreatAura(player);

            player->UpdateAttackPowerAndDamage(false);
        }
        else
        {
            Item const* previousIgnored =
                NaxxramasRockbiter::
                    ignoredRockbiterItem;

            NaxxramasRockbiter::
                ignoredRockbiterItem = item;

            NaxxramasRockbiter::
                SyncThreatAura(
                    player,
                    item);

            player->UpdateAttackPowerAndDamage(false);

            NaxxramasRockbiter::
                ignoredRockbiterItem =
                    previousIgnored;
        }

        return false;
    }
};

void AddShamanRockbiterScripts()
{
    RegisterSpellScript(
        spell_custom_sha_rockbiter_threat);

    new NaxxramasCoreShamanRockbiter();
}
