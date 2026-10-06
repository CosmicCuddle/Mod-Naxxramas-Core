/*
 * Naxxramas Core
 *
 * Bot Consumables
 *
 * Provides instance-scoped raid and dungeon consumables to controlled Playerbots.
 *
 * Initial profile:
 *   Molten Core
 *
 * Command:
 *   .bot consumables mc
 *   .bot consumables status
 *   .bot consumables clear
 *
 * Behaviour:
 * - Applies long-duration consumable effects directly as auras.
 * - Uses explicit Vanilla-era stack targets for supplied inventory items.
 * - Supplies Cache of Mau'ari automatically when Juju buffs are required.
 * - Supplies sharpening stones or weightstones based on equipped weapon type.
 * - Supports Alliance and Horde bots.
 * - Tracks consumable auras applied by this system.
 * - Warns the player when tracked consumable buffs expire or disappear.
 */

#include "AiFactory.h"
#include "Chat.h"
#include "CommandScript.h"
#include "DBCStores.h"
#include "GameTime.h"
#include "Group.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "Map.h"
#include "ObjectMgr.h"
#include "Pet.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "RandomPlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "SpellAuras.h"
#include "WorldSession.h"

#include <algorithm>
#include <cctype>
#include <initializer_list>
#include <string>
#include <unordered_map>
#include <vector>

using namespace Acore::ChatCommands;

namespace
{
    // =========================================================
    // General settings
    // =========================================================

    constexpr uint32 AURA_CHECK_INTERVAL = 10 * IN_MILLISECONDS;
    constexpr uint32 CONSUMABLE_COMMAND_COOLDOWN_SECONDS =
        10 * 60;

    constexpr int32 CONSUMABLE_REFRESH_THRESHOLD_MS =
        10 * 60 * IN_MILLISECONDS;

    constexpr int32 FOOD_REFRESH_THRESHOLD_MS =
        5 * 60 * IN_MILLISECONDS;

    // =========================================================
    // Important prerequisite items
    // =========================================================

    constexpr uint32 ITEM_CACHE_OF_MAUARI = 12384;

    // Vanilla class reagents. Raid profiles only.
    constexpr uint32 ITEM_IRONWOOD_SEED = 17038;
    constexpr uint32 ITEM_WILD_THORNROOT = 17026;
    constexpr uint32 ITEM_RUNE_OF_TELEPORTATION = 17031;
    constexpr uint32 ITEM_RUNE_OF_PORTALS = 17032;
    constexpr uint32 ITEM_ARCANE_POWDER = 17020;
    constexpr uint32 ITEM_LIGHT_FEATHER = 17056;
    constexpr uint32 ITEM_SYMBOL_OF_KINGS = 21177;
    constexpr uint32 ITEM_SYMBOL_OF_DIVINITY = 17033;
    constexpr uint32 ITEM_SACRED_CANDLE = 17029;
    constexpr uint32 ITEM_EARTH_TOTEM = 5175;
    constexpr uint32 ITEM_FIRE_TOTEM = 5176;
    constexpr uint32 ITEM_WATER_TOTEM = 5177;
    constexpr uint32 ITEM_AIR_TOTEM = 5178;
    constexpr uint32 ITEM_ANKH = 17030;
    constexpr uint32 ITEM_SHINY_FISH_SCALES = 17057;
    constexpr uint32 ITEM_FISH_OIL = 17058;
    constexpr uint32 ITEM_FLASH_POWDER = 5140;
    constexpr uint32 ITEM_BLINDING_POWDER = 5530;
    constexpr uint32 ITEM_SOUL_SHARD = 6265;

    // =========================================================
    // General inventory consumables
    // =========================================================

    constexpr uint32 ITEM_MINOR_HEALING_POTION = 118;
    constexpr uint32 ITEM_LESSER_HEALING_POTION = 858;
    constexpr uint32 ITEM_HEALING_POTION = 929;
    constexpr uint32 ITEM_GREATER_HEALING_POTION = 1710;
    constexpr uint32 ITEM_SUPERIOR_HEALING_POTION = 3928;
    constexpr uint32 ITEM_MAJOR_HEALING_POTION = 13446;

    constexpr uint32 ITEM_MINOR_MANA_POTION = 2455;
    constexpr uint32 ITEM_LESSER_MANA_POTION = 3385;
    constexpr uint32 ITEM_MANA_POTION = 3827;
    constexpr uint32 ITEM_GREATER_MANA_POTION = 6149;
    constexpr uint32 ITEM_SUPERIOR_MANA_POTION = 13443;
    constexpr uint32 ITEM_MAJOR_MANA_POTION = 13444;

    constexpr uint32 ITEM_HEAVY_RUNECLOTH_BANDAGE = 14530;
    constexpr uint32 ITEM_LIMITED_INVULNERABILITY_POTION = 3387;

    // =========================================================
    // Weapon consumables
    // =========================================================

    constexpr uint32 ITEM_ELEMENTAL_SHARPENING_STONE = 18262;
    constexpr uint32 ITEM_DENSE_WEIGHTSTONE = 12643;

    constexpr uint32 ITEM_BRILLIANT_WIZARD_OIL = 20749;
    constexpr uint32 ITEM_BRILLIANT_MANA_OIL = 20748;

    // =========================================================
    // Rogue poisons
    // =========================================================

    constexpr uint32 ITEM_INSTANT_POISON_VI = 8928;
    constexpr uint32 ITEM_DEADLY_POISON_IV = 8985;

    // =========================================================
    // Flask / Elixir items
    //
    // The module reads the actual on-use spell from the
    // AzerothCore ItemTemplate rather than hard-coding the aura.
    // =========================================================

    constexpr uint32 ITEM_FLASK_OF_THE_TITANS = 13510;
    constexpr uint32 ITEM_FLASK_OF_DISTILLED_WISDOM = 13511;
    constexpr uint32 ITEM_FLASK_OF_SUPREME_POWER = 13512;

    constexpr uint32 ITEM_ELIXIR_OF_THE_MONGOOSE = 13452;
    constexpr uint32 ITEM_ELIXIR_OF_GREATER_AGILITY = 9187;
    constexpr uint32 ITEM_ELIXIR_OF_AGILITY = 8949;
    constexpr uint32 ITEM_ELIXIR_OF_LESSER_AGILITY = 3390;
    constexpr uint32 ITEM_ELIXIR_OF_MINOR_AGILITY = 2457;

    constexpr uint32 ITEM_ELIXIR_OF_GIANTS = 9206;
    constexpr uint32 ITEM_ELIXIR_OF_OGRES_STRENGTH = 3391;
    constexpr uint32 ITEM_ELIXIR_OF_LIONS_STRENGTH = 2454;

    constexpr uint32 ITEM_GREATER_ARCANE_ELIXIR = 13454;
    constexpr uint32 ITEM_ARCANE_ELIXIR = 9155;
    constexpr uint32 ITEM_ELIXIR_OF_THE_SAGES = 13447;
    constexpr uint32 ITEM_ELIXIR_OF_GREATER_INTELLECT = 9179;
    constexpr uint32 ITEM_ELIXIR_OF_WISDOM = 3383;

    constexpr uint32 ITEM_ELIXIR_OF_SHADOW_POWER = 9264;
    constexpr uint32 ITEM_ELIXIR_OF_FROST_POWER = 17708;
    constexpr uint32 ITEM_ELIXIR_OF_GREATER_FIREPOWER = 21546;
    constexpr uint32 ITEM_ELIXIR_OF_FIREPOWER = 6373;

    constexpr uint32 ITEM_ELIXIR_OF_FORTITUDE = 3825;
    constexpr uint32 ITEM_ELIXIR_OF_SUPERIOR_DEFENSE = 13445;
    constexpr uint32 ITEM_ELIXIR_OF_GREATER_DEFENSE = 8951;
    constexpr uint32 ITEM_ELIXIR_OF_DEFENSE = 3389;
    constexpr uint32 ITEM_ELIXIR_OF_MINOR_FORTITUDE = 2458;

    // =========================================================
    // Protection / defensive potion effects
    // Applied as auras rather than supplied as potion items.
    // =========================================================

    constexpr uint32 ITEM_FIRE_PROTECTION_POTION = 6049;
    constexpr uint32 ITEM_GREATER_FIRE_PROTECTION_POTION = 13457;
    constexpr uint32 ITEM_NATURE_PROTECTION_POTION = 6052;
    constexpr uint32 ITEM_GREATER_NATURE_PROTECTION_POTION = 13458;
    constexpr uint32 ITEM_SHADOW_PROTECTION_POTION = 6048;
    constexpr uint32 ITEM_GREATER_SHADOW_PROTECTION_POTION = 13459;
    constexpr uint32 ITEM_GREATER_STONESHIELD_POTION = 13455;

    // =========================================================
    // Juju items
    // Cache of Mau'ari is automatically supplied first.
    // =========================================================

    constexpr uint32 ITEM_JUJU_POWER = 12451;
    constexpr uint32 ITEM_JUJU_FLURRY = 12450;
    constexpr uint32 ITEM_JUJU_ESCAPE = 12459;
    constexpr uint32 ITEM_JUJU_MIGHT = 12460;

    // =========================================================
    // Other long-duration consumables
    // =========================================================

    constexpr uint32 ITEM_RUMSEY_RUM_BLACK_LABEL = 21151;

    // Blasted Lands consumables
    constexpr uint32 ITEM_ROIDS = 8410;
    constexpr uint32 ITEM_LUNG_JUICE_COCKTAIL = 8411;
    constexpr uint32 ITEM_GROUND_SCORPOK_ASSAY = 8412;
    constexpr uint32 ITEM_CEREBRAL_CORTEX_COMPOUND = 8423;

    // =========================================================
    // Food buff aura spell IDs
    //
    // Food items themselves are NOT added to inventory.
    // We apply only the final beneficial aura.
    // =========================================================

    constexpr uint32 SPELL_BLESSED_SUNFRUIT = 18125;
    constexpr uint32 SPELL_GRILLED_SQUID = 18192;
    constexpr uint32 SPELL_NIGHTFIN_SOUP = 18194;

    constexpr uint32 SPELL_WELL_FED_2 = 19705;
    constexpr uint32 SPELL_WELL_FED_4 = 19706;
    constexpr uint32 SPELL_WELL_FED_6 = 19708;
    constexpr uint32 SPELL_WELL_FED_8 = 19709;
    constexpr uint32 SPELL_WELL_FED_12 = 19710;

    // Scroll item ranks I-IV.
    constexpr uint32 ITEM_SCROLL_STRENGTH_I = 954;
    constexpr uint32 ITEM_SCROLL_STRENGTH_II = 2289;
    constexpr uint32 ITEM_SCROLL_STRENGTH_III = 4426;
    constexpr uint32 ITEM_SCROLL_STRENGTH_IV = 10310;

    constexpr uint32 ITEM_SCROLL_AGILITY_I = 3012;
    constexpr uint32 ITEM_SCROLL_AGILITY_II = 1477;
    constexpr uint32 ITEM_SCROLL_AGILITY_III = 4425;
    constexpr uint32 ITEM_SCROLL_AGILITY_IV = 10309;

    constexpr uint32 ITEM_SCROLL_INTELLECT_I = 955;
    constexpr uint32 ITEM_SCROLL_INTELLECT_II = 2290;
    constexpr uint32 ITEM_SCROLL_INTELLECT_III = 4419;
    constexpr uint32 ITEM_SCROLL_INTELLECT_IV = 10308;

    constexpr uint32 ITEM_SCROLL_SPIRIT_I = 1181;
    constexpr uint32 ITEM_SCROLL_SPIRIT_II = 1712;
    constexpr uint32 ITEM_SCROLL_SPIRIT_III = 4424;
    constexpr uint32 ITEM_SCROLL_SPIRIT_IV = 10306;

    constexpr uint32 ITEM_SCROLL_PROTECTION_I = 3013;
    constexpr uint32 ITEM_SCROLL_PROTECTION_II = 1478;
    constexpr uint32 ITEM_SCROLL_PROTECTION_III = 4421;
    constexpr uint32 ITEM_SCROLL_PROTECTION_IV = 10305;

    // =========================================================
    // Tracking
    // =========================================================

    enum class ProfileArea : uint8
    {
        Any,
        StratholmeUndead,
        DireMaulEast,
        DireMaulWest,
        DireMaulNorth,
        BlackrockLower,
        BlackrockUpper
    };

    enum class BotConsumableRole : uint8
    {
        Unsupported,
        Tank,
        StrengthDps,
        AgilityDps,
        Healer,
        Caster
    };

    enum class CasterSchool : uint8
    {
        General,
        Shadow,
        Frost,
        Fire
    };

    enum class ProtectionSchool : uint8
    {
        None,
        Fire,
        Nature,
        Shadow
    };

    struct TrackedAura
    {
        ObjectGuid::LowType BotGuid = 0;
        uint32 SpellId = 0;
        std::string BotName;
        std::string AuraName;
        bool IsPetAura = false;
        bool WarnOnMissing = true;
        bool MissingNotified = false;
    };

    struct TimedAura
    {
        ObjectGuid::LowType BotGuid = 0;
        uint32 SpellId = 0;
        std::string BotName;
        std::string AuraName;
        uint32 ApplicationsUsed = 0;
        uint32 MaxApplications = 0;
        uint32 NextApplicationTimer = 0;
    };

    struct RaidConsumableTracker
    {
        std::string Profile;
        uint32 UpdateTimer = 0;
        uint32 RequiredMapId = 0;
        ProfileArea RequiredArea = ProfileArea::Any;
        std::vector<TrackedAura> Auras;
        std::vector<TimedAura> TimedAuras;
    };

    struct PreparationStats
    {
        uint32 BotsPrepared = 0;
        uint32 UnsupportedBots = 0;
        uint32 AurasApplied = 0;
        uint32 AurasPreserved = 0;
        uint32 AuraFailures = 0;
        uint32 ItemsAdded = 0;
        uint32 ItemFailures = 0;
        uint32 CachesAdded = 0;
        uint32 ReagentsAdded = 0;
        uint32 PetBuffsSkipped = 0;
    };

    std::unordered_map<ObjectGuid::LowType, RaidConsumableTracker>
        RaidConsumableTrackers;

    std::unordered_map<ObjectGuid::LowType, uint64>
        ConsumableCooldownUntil;

    std::unordered_map<ObjectGuid::LowType, bool>
        ConsumableAliveState;

    uint64 GetConsumableNow()
    {
        return static_cast<uint64>(
            GameTime::GetGameTime().
                count());
    }

    uint32 GetConsumableCooldownRemaining(
        Player* player)
    {
        if (!player)
            return 0;

        ObjectGuid::LowType guid =
            player->GetGUID().
                GetCounter();

        auto itr =
            ConsumableCooldownUntil.find(
                guid);

        if (itr ==
            ConsumableCooldownUntil.end())
        {
            return 0;
        }

        uint64 now =
            GetConsumableNow();

        if (itr->second <= now)
        {
            ConsumableCooldownUntil.erase(
                itr);
            return 0;
        }

        return static_cast<uint32>(
            itr->second - now);
    }

    void StartConsumableCooldown(
        Player* player)
    {
        if (!player)
            return;

        ConsumableCooldownUntil[
            player->GetGUID().
                GetCounter()] =
            GetConsumableNow() +
            CONSUMABLE_COMMAND_COOLDOWN_SECONDS;
    }

    void ResetConsumableCooldownForGroup(
        Player* deadPlayer)
    {
        if (!deadPlayer)
            return;

        Group* group =
            deadPlayer->GetGroup();

        if (!group)
        {
            ConsumableCooldownUntil.erase(
                deadPlayer->GetGUID().
                    GetCounter());
            return;
        }

        for (GroupReference* itr =
                 group->GetFirstMember();
             itr != nullptr;
             itr = itr->next())
        {
            Player* member =
                itr->GetSource();

            if (!member)
                continue;

            ConsumableCooldownUntil.erase(
                member->GetGUID().
                    GetCounter());
        }
    }

    bool CheckConsumableCooldown(
        ChatHandler* handler,
        Player* player)
    {
        uint32 remaining =
            GetConsumableCooldownRemaining(
                player);

        if (!remaining)
            return true;

        handler->PSendSysMessage(
            "[Bot Consumables] Preparation is on cooldown for {}m {}s. A party/raid death or wipe resets this cooldown.",
            remaining / 60,
            remaining % 60);

        return false;
    }

    // =========================================================
    // Item helpers
    // =========================================================

    uint32 GetItemUseSpell(uint32 itemId)
    {
        ItemTemplate const* itemTemplate =
            sObjectMgr->GetItemTemplate(itemId);

        if (!itemTemplate)
            return 0;

        for (uint8 i = 0; i < MAX_ITEM_PROTO_SPELLS; ++i)
        {
            if (itemTemplate->Spells[i].SpellId <= 0)
                continue;

            if (itemTemplate->Spells[i].SpellTrigger !=
                ITEM_SPELLTRIGGER_ON_USE)
            {
                continue;
            }

            return static_cast<uint32>(
                itemTemplate->Spells[i].SpellId);
        }

        return 0;
    }

    bool TopUpToCount(
        Player* bot,
        uint32 itemId,
        uint32 targetCount,
        PreparationStats& stats,
        bool raidReagent = false)
    {
        if (!bot || !targetCount)
            return false;

        ItemTemplate const* itemTemplate =
            sObjectMgr->GetItemTemplate(itemId);

        if (!itemTemplate)
        {
            ++stats.ItemFailures;
            return false;
        }

        if (itemTemplate->MaxCount > 0)
        {
            targetCount =
                std::min<uint32>(
                    targetCount,
                    static_cast<uint32>(itemTemplate->MaxCount));
        }

        uint32 currentCount =
            bot->GetItemCount(itemId, false);

        if (currentCount >= targetCount)
            return true;

        uint32 amountToAdd =
            targetCount - currentCount;

        if (!bot->AddItem(itemId, amountToAdd))
        {
            ++stats.ItemFailures;
            return false;
        }

        stats.ItemsAdded += amountToAdd;

        if (raidReagent)
            stats.ReagentsAdded += amountToAdd;

        return true;
    }

    uint32 GetVanillaStackTarget(uint32 itemId)
    {
        switch (itemId)
        {
            case ITEM_MINOR_HEALING_POTION:
            case ITEM_LESSER_HEALING_POTION:
            case ITEM_HEALING_POTION:
            case ITEM_GREATER_HEALING_POTION:
            case ITEM_SUPERIOR_HEALING_POTION:
            case ITEM_MAJOR_HEALING_POTION:
            case ITEM_MINOR_MANA_POTION:
            case ITEM_LESSER_MANA_POTION:
            case ITEM_MANA_POTION:
            case ITEM_GREATER_MANA_POTION:
            case ITEM_SUPERIOR_MANA_POTION:
            case ITEM_MAJOR_MANA_POTION:
            case ITEM_LIMITED_INVULNERABILITY_POTION:
                return 5;

            case ITEM_HEAVY_RUNECLOTH_BANDAGE:
            case ITEM_ELEMENTAL_SHARPENING_STONE:
            case ITEM_DENSE_WEIGHTSTONE:
            case ITEM_INSTANT_POISON_VI:
            case ITEM_DEADLY_POISON_IV:
                return 20;

            case ITEM_BRILLIANT_WIZARD_OIL:
            case ITEM_BRILLIANT_MANA_OIL:
                return 1;

            default:
                return 1;
        }
    }

    bool TopUpVanillaStack(
        Player* bot,
        uint32 itemId,
        PreparationStats& stats)
    {
        return TopUpToCount(
            bot,
            itemId,
            GetVanillaStackTarget(itemId),
            stats);
    }

    bool EnsureCacheOfMauari(
        Player* bot,
        PreparationStats& stats)
    {
        if (!bot)
            return false;

        if (bot->GetItemCount(
                ITEM_CACHE_OF_MAUARI,
                false) > 0)
        {
            return true;
        }

        if (!bot->AddItem(
                ITEM_CACHE_OF_MAUARI,
                1))
        {
            ++stats.ItemFailures;
            return false;
        }

        ++stats.ItemsAdded;
        ++stats.CachesAdded;

        return true;
    }

    // =========================================================
    // Aura helpers
    // =========================================================

    void AddTrackedAura(
        RaidConsumableTracker& tracker,
        Player* bot,
        uint32 spellId,
        std::string const& auraName,
        bool isPetAura,
        bool warnOnMissing = true)
    {
        if (!bot || !spellId)
            return;

        ObjectGuid::LowType botGuid =
            bot->GetGUID().GetCounter();

        for (TrackedAura& existing : tracker.Auras)
        {
            if (existing.BotGuid == botGuid &&
                existing.SpellId == spellId &&
                existing.IsPetAura == isPetAura)
            {
                existing.AuraName = auraName;
                existing.WarnOnMissing = warnOnMissing;
                existing.MissingNotified = false;
                return;
            }
        }

        TrackedAura aura;
        aura.BotGuid = botGuid;
        aura.SpellId = spellId;
        aura.BotName = bot->GetName();
        aura.AuraName = auraName;
        aura.IsPetAura = isPetAura;
        aura.WarnOnMissing = warnOnMissing;
        aura.MissingNotified = false;

        tracker.Auras.push_back(aura);
    }

    bool ApplyTrackedAura(
        Player* bot,
        Unit* target,
        uint32 spellId,
        std::string const& auraName,
        bool isPetAura,
        RaidConsumableTracker& tracker,
        PreparationStats& stats,
        bool warnOnMissing = true,
        int32 refreshThresholdMs =
            CONSUMABLE_REFRESH_THRESHOLD_MS)
    {
        if (!bot || !target || !spellId)
        {
            ++stats.AuraFailures;
            return false;
        }

        // Preserve a healthy existing aura instead of resetting it.
        // Normal consumables refresh at 10 minutes remaining;
        // food effects use a shorter 5-minute threshold.
        if (Aura* existingAura =
                target->GetAura(spellId))
        {
            int32 remaining =
                existingAura->GetDuration();

            if (remaining < 0 ||
                remaining >
                    refreshThresholdMs)
            {
                AddTrackedAura(
                    tracker,
                    bot,
                    spellId,
                    auraName,
                    isPetAura,
                    warnOnMissing);

                ++stats.AurasPreserved;
                return true;
            }
        }

        target->RemoveAurasDueToSpell(
            spellId);

        if (!bot->AddAura(
                spellId,
                target))
        {
            ++stats.AuraFailures;
            return false;
        }

        AddTrackedAura(
            tracker,
            bot,
            spellId,
            auraName,
            isPetAura,
            warnOnMissing);

        ++stats.AurasApplied;
        return true;
    }

    bool ApplyItemAura(
        Player* bot,
        Unit* target,
        uint32 itemId,
        std::string const& auraName,
        bool isPetAura,
        RaidConsumableTracker& tracker,
        PreparationStats& stats,
        bool warnOnMissing = true,
        int32 refreshThresholdMs =
            CONSUMABLE_REFRESH_THRESHOLD_MS)
    {
        uint32 spellId =
            GetItemUseSpell(itemId);

        if (!spellId)
        {
            ++stats.AuraFailures;
            return false;
        }

        return ApplyTrackedAura(
            bot,
            target,
            spellId,
            auraName,
            isPetAura,
            tracker,
            stats,
            warnOnMissing,
            refreshThresholdMs);
    }

    void ApplyJuju(
        Player* bot,
        Unit* target,
        uint32 jujuItemId,
        std::string const& name,
        bool isPetAura,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        if (!EnsureCacheOfMauari(bot, stats))
            return;

        ApplyItemAura(
            bot,
            target,
            jujuItemId,
            name,
            isPetAura,
            tracker,
            stats);
    }

    void ApplyJujuTactical(
        Player* bot,
        Unit* target,
        uint32 jujuItemId,
        std::string const& name,
        bool isPetAura,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        if (!bot ||
            !target ||
            !EnsureCacheOfMauari(bot, stats))
        {
            return;
        }

        ApplyItemAura(
            bot,
            target,
            jujuItemId,
            name,
            isPetAura,
            tracker,
            stats,
            false);
    }

    void ApplyTimedJujuFlurry(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        if (!bot ||
            !EnsureCacheOfMauari(bot, stats))
        {
            return;
        }

        uint32 spellId =
            GetItemUseSpell(ITEM_JUJU_FLURRY);

        if (!spellId)
        {
            ++stats.AuraFailures;
            return;
        }

        bot->RemoveAurasDueToSpell(spellId);

        if (!bot->AddAura(spellId, bot))
        {
            ++stats.AuraFailures;
            return;
        }

        TimedAura timed;
        timed.BotGuid =
            bot->GetGUID().GetCounter();
        timed.SpellId = spellId;
        timed.BotName = bot->GetName();
        timed.AuraName = "Juju Flurry";
        timed.ApplicationsUsed = 1;
        timed.MaxApplications = 3;
        timed.NextApplicationTimer =
            60 * IN_MILLISECONDS;

        tracker.TimedAuras.push_back(timed);
        ++stats.AurasApplied;
    }

    // =========================================================
    // Weapon consumables
    // =========================================================

    bool IsSharpWeapon(Item* weapon)
    {
        if (!weapon)
            return false;

        ItemTemplate const* itemTemplate =
            weapon->GetTemplate();

        if (!itemTemplate ||
            itemTemplate->Class != ITEM_CLASS_WEAPON)
        {
            return false;
        }

        switch (itemTemplate->SubClass)
        {
            case ITEM_SUBCLASS_WEAPON_AXE:
            case ITEM_SUBCLASS_WEAPON_AXE2:
            case ITEM_SUBCLASS_WEAPON_SWORD:
            case ITEM_SUBCLASS_WEAPON_SWORD2:
            case ITEM_SUBCLASS_WEAPON_DAGGER:
            case ITEM_SUBCLASS_WEAPON_POLEARM:
                return true;

            default:
                return false;
        }
    }

    bool IsBluntWeapon(Item* weapon)
    {
        if (!weapon)
            return false;

        ItemTemplate const* itemTemplate =
            weapon->GetTemplate();

        if (!itemTemplate ||
            itemTemplate->Class != ITEM_CLASS_WEAPON)
        {
            return false;
        }

        switch (itemTemplate->SubClass)
        {
            case ITEM_SUBCLASS_WEAPON_MACE:
            case ITEM_SUBCLASS_WEAPON_MACE2:
            case ITEM_SUBCLASS_WEAPON_STAFF:
                return true;

            default:
                return false;
        }
    }

    void SupplyWeaponConsumables(
        Player* bot,
        PreparationStats& stats)
    {
        if (!bot)
            return;

        bool needsSharpeningStone = false;
        bool needsWeightstone = false;

        Item* mainHand =
            bot->GetItemByPos(
                INVENTORY_SLOT_BAG_0,
                EQUIPMENT_SLOT_MAINHAND);

        Item* offHand =
            bot->GetItemByPos(
                INVENTORY_SLOT_BAG_0,
                EQUIPMENT_SLOT_OFFHAND);

        if (IsSharpWeapon(mainHand) ||
            IsSharpWeapon(offHand))
        {
            needsSharpeningStone = true;
        }

        if (IsBluntWeapon(mainHand) ||
            IsBluntWeapon(offHand))
        {
            needsWeightstone = true;
        }

        if (needsSharpeningStone)
        {
            TopUpVanillaStack(
                bot,
                ITEM_ELEMENTAL_SHARPENING_STONE,
                stats);
        }

        if (needsWeightstone)
        {
            TopUpVanillaStack(
                bot,
                ITEM_DENSE_WEIGHTSTONE,
                stats);
        }
    }

    // =========================================================
    // Raid-only class reagents
    // =========================================================

    void SupplyRaidReagents(
        Player* bot,
        PreparationStats& stats)
    {
        if (!bot)
            return;

        auto topUp =
            [&](uint32 itemId, uint32 target)
            {
                TopUpToCount(
                    bot,
                    itemId,
                    target,
                    stats,
                    true);
            };

        switch (bot->getClass())
        {
            case CLASS_DRUID:
                topUp(ITEM_IRONWOOD_SEED, 20);
                topUp(ITEM_WILD_THORNROOT, 20);
                break;
            case CLASS_MAGE:
                topUp(ITEM_RUNE_OF_TELEPORTATION, 10);
                topUp(ITEM_RUNE_OF_PORTALS, 10);
                topUp(ITEM_ARCANE_POWDER, 20);
                topUp(ITEM_LIGHT_FEATHER, 20);
                break;
            case CLASS_PALADIN:
                topUp(ITEM_SYMBOL_OF_KINGS, 100);
                topUp(ITEM_SYMBOL_OF_DIVINITY, 5);
                break;
            case CLASS_PRIEST:
                topUp(ITEM_SACRED_CANDLE, 20);
                topUp(ITEM_LIGHT_FEATHER, 20);
                break;
            case CLASS_ROGUE:
                topUp(ITEM_FLASH_POWDER, 20);
                topUp(ITEM_BLINDING_POWDER, 20);
                break;
            case CLASS_SHAMAN:
                topUp(ITEM_EARTH_TOTEM, 1);
                topUp(ITEM_FIRE_TOTEM, 1);
                topUp(ITEM_WATER_TOTEM, 1);
                topUp(ITEM_AIR_TOTEM, 1);
                topUp(ITEM_ANKH, 5);
                topUp(ITEM_SHINY_FISH_SCALES, 20);
                topUp(ITEM_FISH_OIL, 20);
                break;
            case CLASS_WARLOCK:
                topUp(ITEM_SOUL_SHARD, 5);
                break;
            default:
                break;
        }
    }

    // =========================================================
    // Common Molten Core preparation
    // =========================================================

    void PrepareMoltenCoreCommon(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        // Greater Fire Protection is applied directly.
        ApplyItemAura(
            bot,
            bot,
            ITEM_GREATER_FIRE_PROTECTION_POTION,
            "Greater Fire Protection",
            false,
            tracker,
            stats);

        // Playerbots already understands these inventory items.
        TopUpVanillaStack(
            bot,
            ITEM_MAJOR_HEALING_POTION,
            stats);

        TopUpVanillaStack(
            bot,
            ITEM_HEAVY_RUNECLOTH_BANDAGE,
            stats);

        TopUpVanillaStack(
            bot,
            ITEM_LIMITED_INVULNERABILITY_POTION,
            stats);
    }

void PrepareManaUser(
    Player* bot,
    RaidConsumableTracker& tracker,
    PreparationStats& stats)
{
    TopUpVanillaStack(
        bot,
        ITEM_MAJOR_MANA_POTION,
        stats);

    ApplyItemAura(
        bot,
        bot,
        ITEM_ELIXIR_OF_GREATER_INTELLECT,
        "Elixir of Greater Intellect",
        false,
        tracker,
        stats);

    ApplyItemAura(
        bot,
        bot,
        ITEM_ELIXIR_OF_THE_SAGES,
        "Elixir of the Sages",
        false,
        tracker,
        stats);
}

    void ApplyNightfin(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        ApplyTrackedAura(
            bot,
            bot,
            SPELL_NIGHTFIN_SOUP,
            "Nightfin Soup",
            false,
            tracker,
            stats,
            true,
            FOOD_REFRESH_THRESHOLD_MS);
    }

    void ApplyGrilledSquid(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        ApplyTrackedAura(
            bot,
            bot,
            SPELL_GRILLED_SQUID,
            "Grilled Squid",
            false,
            tracker,
            stats,
            true,
            FOOD_REFRESH_THRESHOLD_MS);
    }

    void ApplyBlessedSunfruit(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        ApplyTrackedAura(
            bot,
            bot,
            SPELL_BLESSED_SUNFRUIT,
            "Blessed Sunfruit",
            false,
            tracker,
            stats,
            true,
            FOOD_REFRESH_THRESHOLD_MS);
    }

    // =========================================================
    // Warrior
    // =========================================================

    void PrepareWarriorTank(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        ApplyItemAura(
            bot, bot,
            ITEM_FLASK_OF_THE_TITANS,
            "Flask of the Titans",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_THE_MONGOOSE,
            "Elixir of the Mongoose",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_FORTITUDE,
            "Elixir of Fortitude",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_SUPERIOR_DEFENSE,
            "Elixir of Superior Defense",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_GREATER_STONESHIELD_POTION,
            "Greater Stoneshield",
            false, tracker, stats, false);

        ApplyItemAura(
            bot, bot,
            ITEM_LUNG_JUICE_COCKTAIL,
            "Lung Juice Cocktail",
            false, tracker, stats);

        ApplyBlessedSunfruit(
            bot,
            tracker,
            stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_POWER,
            "Juju Power",
            false, tracker, stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_MIGHT,
            "Juju Might",
            false, tracker, stats);

        ApplyJujuTactical(
            bot,
            bot,
            ITEM_JUJU_ESCAPE,
            "Juju Escape",
            false,
            tracker,
            stats);

        SupplyWeaponConsumables(
            bot,
            stats);
    }

    void PrepareWarriorDps(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        ApplyItemAura(
            bot, bot,
            ITEM_FLASK_OF_THE_TITANS,
            "Flask of the Titans",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_THE_MONGOOSE,
            "Elixir of the Mongoose",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ROIDS,
            "R.O.I.D.S.",
            false, tracker, stats);

        ApplyBlessedSunfruit(
            bot,
            tracker,
            stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_POWER,
            "Juju Power",
            false, tracker, stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_MIGHT,
            "Juju Might",
            false, tracker, stats);

        ApplyTimedJujuFlurry(
            bot,
            tracker,
            stats);

        SupplyWeaponConsumables(
            bot,
            stats);
    }

    // =========================================================
    // Paladin
    // =========================================================

    void PrepareHolyPaladin(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        PrepareManaUser(
            bot,
            tracker,
            stats);

        ApplyItemAura(
            bot, bot,
            ITEM_FLASK_OF_DISTILLED_WISDOM,
            "Flask of Distilled Wisdom",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_CEREBRAL_CORTEX_COMPOUND,
            "Cerebral Cortex Compound",
            false, tracker, stats);

        ApplyNightfin(
            bot,
            tracker,
            stats);

        TopUpVanillaStack(
            bot,
            ITEM_BRILLIANT_MANA_OIL,
            stats);
    }

    void PrepareRetributionPaladin(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        PrepareManaUser(
            bot,
            tracker,
            stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_THE_MONGOOSE,
            "Elixir of the Mongoose",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_GIANTS,
            "Elixir of Giants",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ROIDS,
            "R.O.I.D.S.",
            false, tracker, stats);

        ApplyBlessedSunfruit(
            bot,
            tracker,
            stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_POWER,
            "Juju Power",
            false, tracker, stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_MIGHT,
            "Juju Might",
            false, tracker, stats);

        ApplyTimedJujuFlurry(
            bot,
            tracker,
            stats);

        SupplyWeaponConsumables(
            bot,
            stats);
    }

    // =========================================================
    // Hunter
    // =========================================================

    void PrepareHunter(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        PrepareManaUser(
            bot,
            tracker,
            stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_THE_MONGOOSE,
            "Elixir of the Mongoose",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_GROUND_SCORPOK_ASSAY,
            "Ground Scorpok Assay",
            false, tracker, stats);

        ApplyGrilledSquid(
            bot,
            tracker,
            stats);

        Pet* pet = bot->GetPet();

        if (!pet)
        {
            ++stats.PetBuffsSkipped;
            return;
        }

        ApplyJuju(
            bot, pet,
            ITEM_JUJU_POWER,
            "Pet - Juju Power",
            true, tracker, stats);

        ApplyJuju(
            bot, pet,
            ITEM_JUJU_MIGHT,
            "Pet - Juju Might",
            true, tracker, stats);
    }

    // =========================================================
    // Rogue
    // =========================================================

    void PrepareRogue(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_THE_MONGOOSE,
            "Elixir of the Mongoose",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_GROUND_SCORPOK_ASSAY,
            "Ground Scorpok Assay",
            false, tracker, stats);

        ApplyGrilledSquid(
            bot,
            tracker,
            stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_POWER,
            "Juju Power",
            false, tracker, stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_MIGHT,
            "Juju Might",
            false, tracker, stats);

        ApplyTimedJujuFlurry(
            bot,
            tracker,
            stats);

        TopUpVanillaStack(
            bot,
            ITEM_INSTANT_POISON_VI,
            stats);

        TopUpVanillaStack(
            bot,
            ITEM_DEADLY_POISON_IV,
            stats);
    }

    // =========================================================
    // Healer caster profile
    // =========================================================

    void PrepareHealerCaster(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        PrepareManaUser(
            bot,
            tracker,
            stats);

        ApplyItemAura(
            bot, bot,
            ITEM_FLASK_OF_DISTILLED_WISDOM,
            "Flask of Distilled Wisdom",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_CEREBRAL_CORTEX_COMPOUND,
            "Cerebral Cortex Compound",
            false, tracker, stats);

        ApplyNightfin(
            bot,
            tracker,
            stats);

        TopUpVanillaStack(
            bot,
            ITEM_BRILLIANT_MANA_OIL,
            stats);
    }

    // =========================================================
    // Magic DPS base
    // =========================================================

    void PrepareCasterDps(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        PrepareManaUser(
            bot,
            tracker,
            stats);

        ApplyItemAura(
            bot, bot,
            ITEM_FLASK_OF_SUPREME_POWER,
            "Flask of Supreme Power",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_GREATER_ARCANE_ELIXIR,
            "Greater Arcane Elixir",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_CEREBRAL_CORTEX_COMPOUND,
            "Cerebral Cortex Compound",
            false, tracker, stats);

        ApplyNightfin(
            bot,
            tracker,
            stats);

        TopUpVanillaStack(
            bot,
            ITEM_BRILLIANT_WIZARD_OIL,
            stats);
    }

    // =========================================================
    // Shaman
    // =========================================================

    void PrepareEnhancementShaman(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        PrepareManaUser(
            bot,
            tracker,
            stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_THE_MONGOOSE,
            "Elixir of the Mongoose",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ROIDS,
            "R.O.I.D.S.",
            false, tracker, stats);

        ApplyNightfin(
            bot,
            tracker,
            stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_POWER,
            "Juju Power",
            false, tracker, stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_MIGHT,
            "Juju Might",
            false, tracker, stats);
    }

    // =========================================================
    // Feral Druid
    // =========================================================

    void PrepareFeralTank(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        ApplyItemAura(
            bot, bot,
            ITEM_FLASK_OF_THE_TITANS,
            "Flask of the Titans",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_THE_MONGOOSE,
            "Elixir of the Mongoose",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_LUNG_JUICE_COCKTAIL,
            "Lung Juice Cocktail",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_GREATER_STONESHIELD_POTION,
            "Greater Stoneshield",
            false, tracker, stats, false);

        ApplyBlessedSunfruit(
            bot,
            tracker,
            stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_POWER,
            "Juju Power",
            false, tracker, stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_MIGHT,
            "Juju Might",
            false, tracker, stats);
    }

    void PrepareFeralDps(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        PrepareManaUser(
            bot,
            tracker,
            stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ELIXIR_OF_THE_MONGOOSE,
            "Elixir of the Mongoose",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_GROUND_SCORPOK_ASSAY,
            "Ground Scorpok Assay",
            false, tracker, stats);

        ApplyGrilledSquid(
            bot,
            tracker,
            stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_POWER,
            "Juju Power",
            false, tracker, stats);

        ApplyJuju(
            bot, bot,
            ITEM_JUJU_MIGHT,
            "Juju Might",
            false, tracker, stats);
    }

    // =========================================================
    // Dungeon consumable helpers
    // =========================================================

    struct ItemAuraChoice
    {
        uint32 ItemId;
        char const* Name;
    };

    bool IsItemUsableAtLevel(
        uint32 itemId,
        uint32 level)
    {
        ItemTemplate const* itemTemplate =
            sObjectMgr->GetItemTemplate(itemId);

        return itemTemplate &&
            itemTemplate->RequiredLevel <= level;
    }

    bool ApplyFirstUsableItemAura(
        Player* bot,
        uint32 level,
        std::initializer_list<ItemAuraChoice> choices,
        RaidConsumableTracker& tracker,
        PreparationStats& stats,
        bool warnOnMissing = true)
    {
        for (ItemAuraChoice const& choice : choices)
        {
            if (!IsItemUsableAtLevel(
                    choice.ItemId,
                    level))
            {
                continue;
            }

            return ApplyItemAura(
                bot,
                bot,
                choice.ItemId,
                choice.Name,
                false,
                tracker,
                stats,
                warnOnMissing);
        }

        return false;
    }

    uint32 GetFirstUsableItem(
        uint32 level,
        std::initializer_list<uint32> choices)
    {
        for (uint32 itemId : choices)
        {
            if (IsItemUsableAtLevel(
                    itemId,
                    level))
            {
                return itemId;
            }
        }

        return 0;
    }

    bool ClassUsesMana(Player* bot)
    {
        if (!bot)
            return false;

        return bot->getClass() != CLASS_WARRIOR &&
            bot->getClass() != CLASS_ROGUE;
    }

    BotConsumableRole GetBotConsumableRole(
        Player* bot,
        CasterSchool& school)
    {
        school = CasterSchool::General;

        if (!bot)
            return BotConsumableRole::Unsupported;

        uint8 spec =
            AiFactory::GetPlayerSpecTab(bot);

        switch (bot->getClass())
        {
            case CLASS_WARRIOR:
                return (spec == WARRIOR_TAB_PROTECTION ||
                        PlayerbotAI::IsTank(bot))
                    ? BotConsumableRole::Tank
                    : BotConsumableRole::StrengthDps;

            case CLASS_PALADIN:
                if (spec == PALADIN_TAB_PROTECTION ||
                    PlayerbotAI::IsTank(bot))
                {
                    return BotConsumableRole::Tank;
                }
                if (spec == PALADIN_TAB_HOLY)
                    return BotConsumableRole::Healer;
                return BotConsumableRole::StrengthDps;

            case CLASS_HUNTER:
            case CLASS_ROGUE:
                return BotConsumableRole::AgilityDps;

            case CLASS_PRIEST:
                if (spec == PRIEST_TAB_SHADOW)
                {
                    school = CasterSchool::Shadow;
                    return BotConsumableRole::Caster;
                }
                return BotConsumableRole::Healer;

            case CLASS_SHAMAN:
                if (spec == SHAMAN_TAB_ENHANCEMENT)
                    return BotConsumableRole::StrengthDps;
                if (spec == SHAMAN_TAB_ELEMENTAL)
                    return BotConsumableRole::Caster;
                return BotConsumableRole::Healer;

            case CLASS_MAGE:
                if (spec == MAGE_TAB_FROST)
                    school = CasterSchool::Frost;
                else if (spec == MAGE_TAB_FIRE)
                    school = CasterSchool::Fire;
                return BotConsumableRole::Caster;

            case CLASS_WARLOCK:
                if (spec == WARLOCK_TAB_DESTRUCTION)
                    school = CasterSchool::Fire;
                else
                    school = CasterSchool::Shadow;
                return BotConsumableRole::Caster;

            case CLASS_DRUID:
                if (spec == DRUID_TAB_FERAL)
                {
                    return PlayerbotAI::IsTank(bot)
                        ? BotConsumableRole::Tank
                        : BotConsumableRole::AgilityDps;
                }
                if (spec == DRUID_TAB_BALANCE)
                    return BotConsumableRole::Caster;
                return BotConsumableRole::Healer;

            default:
                return BotConsumableRole::Unsupported;
        }
    }

    void ApplyRoleElixir(
        Player* bot,
        uint32 level,
        BotConsumableRole role,
        CasterSchool school,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        switch (role)
        {
            case BotConsumableRole::Tank:
                ApplyFirstUsableItemAura(
                    bot,
                    level,
                    {
                        {ITEM_ELIXIR_OF_SUPERIOR_DEFENSE, "Elixir of Superior Defense"},
                        {ITEM_ELIXIR_OF_GREATER_DEFENSE, "Elixir of Greater Defense"},
                        {ITEM_ELIXIR_OF_DEFENSE, "Elixir of Defense"},
                        {ITEM_ELIXIR_OF_MINOR_FORTITUDE, "Elixir of Minor Fortitude"}
                    },
                    tracker,
                    stats);
                break;

            case BotConsumableRole::StrengthDps:
                ApplyFirstUsableItemAura(
                    bot,
                    level,
                    {
                        {ITEM_ELIXIR_OF_THE_MONGOOSE, "Elixir of the Mongoose"},
                        {ITEM_ELIXIR_OF_GIANTS, "Elixir of Giants"},
                        {ITEM_ELIXIR_OF_OGRES_STRENGTH, "Elixir of Ogre's Strength"},
                        {ITEM_ELIXIR_OF_LIONS_STRENGTH, "Elixir of Lion's Strength"}
                    },
                    tracker,
                    stats);
                break;

            case BotConsumableRole::AgilityDps:
                ApplyFirstUsableItemAura(
                    bot,
                    level,
                    {
                        {ITEM_ELIXIR_OF_THE_MONGOOSE, "Elixir of the Mongoose"},
                        {ITEM_ELIXIR_OF_GREATER_AGILITY, "Elixir of Greater Agility"},
                        {ITEM_ELIXIR_OF_AGILITY, "Elixir of Agility"},
                        {ITEM_ELIXIR_OF_LESSER_AGILITY, "Elixir of Lesser Agility"},
                        {ITEM_ELIXIR_OF_MINOR_AGILITY, "Elixir of Minor Agility"}
                    },
                    tracker,
                    stats);
                break;

            case BotConsumableRole::Healer:
                ApplyFirstUsableItemAura(
                    bot,
                    level,
                    {
                        {ITEM_ELIXIR_OF_THE_SAGES, "Elixir of the Sages"},
                        {ITEM_ELIXIR_OF_GREATER_INTELLECT, "Elixir of Greater Intellect"},
                        {ITEM_ELIXIR_OF_WISDOM, "Elixir of Wisdom"}
                    },
                    tracker,
                    stats);
                break;

            case BotConsumableRole::Caster:
            {
                bool applied = false;

                if (school == CasterSchool::Shadow)
                {
                    applied = ApplyFirstUsableItemAura(
                        bot,
                        level,
                        {
                            {ITEM_ELIXIR_OF_SHADOW_POWER, "Elixir of Shadow Power"}
                        },
                        tracker,
                        stats);
                }
                else if (school == CasterSchool::Frost)
                {
                    applied = ApplyFirstUsableItemAura(
                        bot,
                        level,
                        {
                            {ITEM_ELIXIR_OF_FROST_POWER, "Elixir of Frost Power"}
                        },
                        tracker,
                        stats);
                }
                else if (school == CasterSchool::Fire)
                {
                    applied = ApplyFirstUsableItemAura(
                        bot,
                        level,
                        {
                            {ITEM_ELIXIR_OF_GREATER_FIREPOWER, "Elixir of Greater Firepower"},
                            {ITEM_ELIXIR_OF_FIREPOWER, "Elixir of Firepower"}
                        },
                        tracker,
                        stats);
                }

                if (!applied)
                {
                    ApplyFirstUsableItemAura(
                        bot,
                        level,
                        {
                            {ITEM_GREATER_ARCANE_ELIXIR, "Greater Arcane Elixir"},
                            {ITEM_ARCANE_ELIXIR, "Arcane Elixir"},
                            {ITEM_ELIXIR_OF_WISDOM, "Elixir of Wisdom"}
                        },
                        tracker,
                        stats);
                }

                break;
            }

            default:
                break;
        }
    }

    void ApplyRoleScroll(
        Player* bot,
        uint32 level,
        BotConsumableRole role,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        // Scrolls are cleanup-tracked but do not generate missing warnings,
        // because a normal class buff may replace them.
        switch (role)
        {
            case BotConsumableRole::Tank:
                ApplyFirstUsableItemAura(
                    bot, level,
                    {
                        {ITEM_SCROLL_PROTECTION_IV, "Scroll of Protection IV"},
                        {ITEM_SCROLL_PROTECTION_III, "Scroll of Protection III"},
                        {ITEM_SCROLL_PROTECTION_II, "Scroll of Protection II"},
                        {ITEM_SCROLL_PROTECTION_I, "Scroll of Protection"}
                    },
                    tracker, stats, false);
                break;

            case BotConsumableRole::StrengthDps:
                ApplyFirstUsableItemAura(
                    bot, level,
                    {
                        {ITEM_SCROLL_STRENGTH_IV, "Scroll of Strength IV"},
                        {ITEM_SCROLL_STRENGTH_III, "Scroll of Strength III"},
                        {ITEM_SCROLL_STRENGTH_II, "Scroll of Strength II"},
                        {ITEM_SCROLL_STRENGTH_I, "Scroll of Strength"}
                    },
                    tracker, stats, false);
                break;

            case BotConsumableRole::AgilityDps:
                ApplyFirstUsableItemAura(
                    bot, level,
                    {
                        {ITEM_SCROLL_AGILITY_IV, "Scroll of Agility IV"},
                        {ITEM_SCROLL_AGILITY_III, "Scroll of Agility III"},
                        {ITEM_SCROLL_AGILITY_II, "Scroll of Agility II"},
                        {ITEM_SCROLL_AGILITY_I, "Scroll of Agility"}
                    },
                    tracker, stats, false);
                break;

            case BotConsumableRole::Healer:
                ApplyFirstUsableItemAura(
                    bot, level,
                    {
                        {ITEM_SCROLL_SPIRIT_IV, "Scroll of Spirit IV"},
                        {ITEM_SCROLL_SPIRIT_III, "Scroll of Spirit III"},
                        {ITEM_SCROLL_SPIRIT_II, "Scroll of Spirit II"},
                        {ITEM_SCROLL_SPIRIT_I, "Scroll of Spirit"}
                    },
                    tracker, stats, false);
                break;

            case BotConsumableRole::Caster:
                ApplyFirstUsableItemAura(
                    bot, level,
                    {
                        {ITEM_SCROLL_INTELLECT_IV, "Scroll of Intellect IV"},
                        {ITEM_SCROLL_INTELLECT_III, "Scroll of Intellect III"},
                        {ITEM_SCROLL_INTELLECT_II, "Scroll of Intellect II"},
                        {ITEM_SCROLL_INTELLECT_I, "Scroll of Intellect"}
                    },
                    tracker, stats, false);
                break;

            default:
                break;
        }
    }

    void ApplyGenericWellFed(
        Player* bot,
        uint32 level,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        uint32 spellId = SPELL_WELL_FED_2;
        char const* name = "Well Fed (+2)";

        if (level >= 35)
        {
            spellId = SPELL_WELL_FED_12;
            name = "Well Fed (+12)";
        }
        else if (level >= 25)
        {
            spellId = SPELL_WELL_FED_8;
            name = "Well Fed (+8)";
        }
        else if (level >= 15)
        {
            spellId = SPELL_WELL_FED_6;
            name = "Well Fed (+6)";
        }
        else if (level >= 5)
        {
            spellId = SPELL_WELL_FED_4;
            name = "Well Fed (+4)";
        }

        ApplyTrackedAura(
            bot,
            bot,
            spellId,
            name,
            false,
            tracker,
            stats,
            true,
            FOOD_REFRESH_THRESHOLD_MS);
    }

    void ApplyRoleFood(
        Player* bot,
        uint32 level,
        BotConsumableRole role,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        if (level >= 35 &&
            role == BotConsumableRole::AgilityDps)
        {
            ApplyGrilledSquid(
                bot,
                tracker,
                stats);
            return;
        }

        if (level >= 35 &&
            (role == BotConsumableRole::Caster ||
             role == BotConsumableRole::Healer))
        {
            ApplyNightfin(
                bot,
                tracker,
                stats);
            return;
        }

        ApplyGenericWellFed(
            bot,
            level,
            tracker,
            stats);
    }

    void SupplyLevelPotions(
        Player* bot,
        uint32 level,
        PreparationStats& stats)
    {
        uint32 healing =
            GetFirstUsableItem(
                level,
                {
                    ITEM_MAJOR_HEALING_POTION,
                    ITEM_SUPERIOR_HEALING_POTION,
                    ITEM_GREATER_HEALING_POTION,
                    ITEM_HEALING_POTION,
                    ITEM_LESSER_HEALING_POTION,
                    ITEM_MINOR_HEALING_POTION
                });

        if (healing)
            TopUpToCount(bot, healing, 5, stats);

        if (!ClassUsesMana(bot))
            return;

        uint32 mana =
            GetFirstUsableItem(
                level,
                {
                    ITEM_MAJOR_MANA_POTION,
                    ITEM_SUPERIOR_MANA_POTION,
                    ITEM_GREATER_MANA_POTION,
                    ITEM_MANA_POTION,
                    ITEM_LESSER_MANA_POTION,
                    ITEM_MINOR_MANA_POTION
                });

        if (mana)
            TopUpToCount(bot, mana, 5, stats);
    }

    void ApplyProtectionForDungeon(
        Player* bot,
        uint32 level,
        ProtectionSchool school,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        switch (school)
        {
            case ProtectionSchool::Fire:
                ApplyFirstUsableItemAura(
                    bot, level,
                    {
                        {ITEM_GREATER_FIRE_PROTECTION_POTION, "Greater Fire Protection"},
                        {ITEM_FIRE_PROTECTION_POTION, "Fire Protection"}
                    },
                    tracker, stats);
                break;

            case ProtectionSchool::Nature:
                ApplyFirstUsableItemAura(
                    bot, level,
                    {
                        {ITEM_GREATER_NATURE_PROTECTION_POTION, "Greater Nature Protection"},
                        {ITEM_NATURE_PROTECTION_POTION, "Nature Protection"}
                    },
                    tracker, stats);
                break;

            case ProtectionSchool::Shadow:
                ApplyFirstUsableItemAura(
                    bot, level,
                    {
                        {ITEM_GREATER_SHADOW_PROTECTION_POTION, "Greater Shadow Protection"},
                        {ITEM_SHADOW_PROTECTION_POTION, "Shadow Protection"}
                    },
                    tracker, stats);
                break;

            default:
                break;
        }
    }

    void SupplyEnhancedDungeonExtras(
        Player* bot,
        uint32 level,
        BotConsumableRole role,
        PreparationStats& stats)
    {
        if (IsItemUsableAtLevel(
                ITEM_HEAVY_RUNECLOTH_BANDAGE,
                level))
        {
            TopUpToCount(
                bot,
                ITEM_HEAVY_RUNECLOTH_BANDAGE,
                20,
                stats);
        }

        if (IsItemUsableAtLevel(
                ITEM_LIMITED_INVULNERABILITY_POTION,
                level))
        {
            TopUpToCount(
                bot,
                ITEM_LIMITED_INVULNERABILITY_POTION,
                5,
                stats);
        }

        if (role == BotConsumableRole::Caster)
        {
            if (IsItemUsableAtLevel(
                    ITEM_BRILLIANT_WIZARD_OIL,
                    level))
            {
                TopUpToCount(
                    bot,
                    ITEM_BRILLIANT_WIZARD_OIL,
                    1,
                    stats);
            }
        }
        else if (role == BotConsumableRole::Healer)
        {
            if (IsItemUsableAtLevel(
                    ITEM_BRILLIANT_MANA_OIL,
                    level))
            {
                TopUpToCount(
                    bot,
                    ITEM_BRILLIANT_MANA_OIL,
                    1,
                    stats);
            }
        }
        else if (bot->getClass() == CLASS_ROGUE)
        {
            if (IsItemUsableAtLevel(
                    ITEM_INSTANT_POISON_VI,
                    level))
            {
                TopUpToCount(
                    bot,
                    ITEM_INSTANT_POISON_VI,
                    20,
                    stats);
            }

            if (IsItemUsableAtLevel(
                    ITEM_DEADLY_POISON_IV,
                    level))
            {
                TopUpToCount(
                    bot,
                    ITEM_DEADLY_POISON_IV,
                    20,
                    stats);
            }
        }
    }

    bool PrepareDungeonBot(
        Player* bot,
        uint32 effectiveLevel,
        ProtectionSchool protection,
        bool enhanced,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        CasterSchool school =
            CasterSchool::General;

        BotConsumableRole role =
            GetBotConsumableRole(
                bot,
                school);

        if (role ==
            BotConsumableRole::Unsupported)
        {
            ++stats.UnsupportedBots;
            return false;
        }

        ApplyRoleElixir(
            bot,
            effectiveLevel,
            role,
            school,
            tracker,
            stats);

        ApplyRoleFood(
            bot,
            effectiveLevel,
            role,
            tracker,
            stats);

        ApplyRoleScroll(
            bot,
            effectiveLevel,
            role,
            tracker,
            stats);

        SupplyLevelPotions(
            bot,
            effectiveLevel,
            stats);

        ApplyProtectionForDungeon(
            bot,
            effectiveLevel,
            protection,
            tracker,
            stats);

        if (enhanced)
        {
            SupplyEnhancedDungeonExtras(
                bot,
                effectiveLevel,
                role,
                stats);
        }

        ++stats.BotsPrepared;
        return true;
    }

    // =========================================================
    // Main Molten Core class/spec dispatcher
    // =========================================================

    bool PrepareMoltenCoreBot(
        Player* bot,
        RaidConsumableTracker& tracker,
        PreparationStats& stats)
    {
        if (!bot)
            return false;

        uint8 playerClass =
            bot->getClass();

        uint8 spec =
            AiFactory::GetPlayerSpecTab(bot);

        // Protection Paladin intentionally has no automatic
        // Classic Molten Core profile yet.
        if (playerClass == CLASS_PALADIN &&
            spec == PALADIN_TAB_PROTECTION)
        {
            ++stats.UnsupportedBots;
            return false;
        }

        // Death Knights did not exist in Vanilla and currently
        // have no Molten Core profile.
        if (playerClass == CLASS_DEATH_KNIGHT)
        {
            ++stats.UnsupportedBots;
            return false;
        }

        PrepareMoltenCoreCommon(
            bot,
            tracker,
            stats);

        SupplyRaidReagents(
            bot,
            stats);

        switch (playerClass)
        {
            case CLASS_WARRIOR:
            {
                if (spec == WARRIOR_TAB_PROTECTION ||
                    PlayerbotAI::IsTank(bot))
                {
                    PrepareWarriorTank(
                        bot,
                        tracker,
                        stats);
                }
                else
                {
                    // Arms deliberately inherits Fury/DPS.
                    PrepareWarriorDps(
                        bot,
                        tracker,
                        stats);
                }

                break;
            }

            case CLASS_PALADIN:
            {
                if (spec == PALADIN_TAB_HOLY)
                {
                    PrepareHolyPaladin(
                        bot,
                        tracker,
                        stats);
                }
                else
                {
                    PrepareRetributionPaladin(
                        bot,
                        tracker,
                        stats);
                }

                break;
            }

            case CLASS_HUNTER:
            {
                PrepareHunter(
                    bot,
                    tracker,
                    stats);

                break;
            }

            case CLASS_ROGUE:
            {
                PrepareRogue(
                    bot,
                    tracker,
                    stats);

                break;
            }

            case CLASS_PRIEST:
            {
                if (spec == PRIEST_TAB_SHADOW)
                {
                    PrepareCasterDps(
                        bot,
                        tracker,
                        stats);

                    ApplyItemAura(
                        bot, bot,
                        ITEM_ELIXIR_OF_SHADOW_POWER,
                        "Elixir of Shadow Power",
                        false, tracker, stats);
                }
                else
                {
                    PrepareHealerCaster(
                        bot,
                        tracker,
                        stats);
                }

                break;
            }

            case CLASS_SHAMAN:
            {
                if (spec == SHAMAN_TAB_ENHANCEMENT)
                {
                    PrepareEnhancementShaman(
                        bot,
                        tracker,
                        stats);
                }
                else if (spec == SHAMAN_TAB_ELEMENTAL)
                {
                    PrepareCasterDps(
                        bot,
                        tracker,
                        stats);
                }
                else
                {
                    PrepareHealerCaster(
                        bot,
                        tracker,
                        stats);
                }

                break;
            }

            case CLASS_MAGE:
            {
                PrepareCasterDps(
                    bot,
                    tracker,
                    stats);

                if (spec == MAGE_TAB_FROST)
                {
                    ApplyItemAura(
                        bot, bot,
                        ITEM_ELIXIR_OF_FROST_POWER,
                        "Elixir of Frost Power",
                        false, tracker, stats);
                }

                break;
            }

            case CLASS_WARLOCK:
            {
                PrepareCasterDps(
                    bot,
                    tracker,
                    stats);

                ApplyItemAura(
                    bot, bot,
                    ITEM_ELIXIR_OF_SHADOW_POWER,
                    "Elixir of Shadow Power",
                    false, tracker, stats);

                break;
            }

            case CLASS_DRUID:
            {
                if (spec == DRUID_TAB_FERAL)
                {
                    if (PlayerbotAI::IsTank(bot))
                    {
                        PrepareFeralTank(
                            bot,
                            tracker,
                            stats);
                    }
                    else
                    {
                        PrepareFeralDps(
                            bot,
                            tracker,
                            stats);
                    }
                }
                else if (spec == DRUID_TAB_BALANCE)
                {
                    PrepareCasterDps(
                        bot,
                        tracker,
                        stats);
                }
                else
                {
                    PrepareHealerCaster(
                        bot,
                        tracker,
                        stats);
                }

                break;
            }

            default:
            {
                ++stats.UnsupportedBots;
                return false;
            }
        }

        ++stats.BotsPrepared;
        return true;
    }

    // =========================================================
    // Scope
    //
    // If the master is grouped/raiding, only prepare controlled
    // bots in that same group.
    //
    // If the master is not grouped, prepare all controlled bots
    // currently in the world.
    // =========================================================

    bool BotIsInPreparationScope(
        Player* master,
        Player* bot)
    {
        if (!master ||
            !bot ||
            !bot->IsInWorld())
        {
            return false;
        }

        if (master->GetGroup())
        {
            return bot->GetGroup() ==
                master->GetGroup();
        }

        return true;
    }

    bool IsBlackrockUpper(
        Player const* player)
    {
        if (!player ||
            player->GetMapId() !=
                MAP_BLACKROCK_SPIRE)
        {
            return false;
        }

        float x = player->GetPositionX();
        float y = player->GetPositionY();
        float z = player->GetPositionZ();

        // LBRS occupies the predominantly negative-X side of map 229.
        // The major UBRS rooms are on the positive-X side:
        // Hall of Blackhand, Emberseer, Rookery, Stadium, Beast and
        // Drakkisath. Keep the older deep/high test as a fallback for
        // transitional Upper Spire spaces that briefly cross X < 0.
        if (x >= 0.0f)
            return true;

        return y <= -315.0f &&
            z >= 60.0f;
    }

    ProfileArea GetDireMaulArea(
        Player const* player)
    {
        if (!player ||
            player->GetMapId() != MAP_DIRE_MAUL)
        {
            return ProfileArea::Any;
        }

        if (player->GetPositionX() > 120.0f)
            return ProfileArea::DireMaulNorth;

        if (player->GetPositionY() > 0.0f)
            return ProfileArea::DireMaulWest;

        return ProfileArea::DireMaulEast;
    }

    bool IsStratholmeUndeadSide(
        Player const* player)
    {
        if (!player ||
            player->GetMapId() !=
                MAP_STRATHOLME)
        {
            return false;
        }

        float x = player->GetPositionX();
        float y = player->GetPositionY();

        float mainDx = x - 3395.09f;
        float mainDy = y + 3380.25f;
        float serviceDx = x - 3593.15f;
        float serviceDy = y + 3646.56f;

        float mainDistanceSq =
            mainDx * mainDx +
            mainDy * mainDy;

        float serviceDistanceSq =
            serviceDx * serviceDx +
            serviceDy * serviceDy;

        return serviceDistanceSq <
            mainDistanceSq;
    }

    bool IsProfileLocationValid(
        Player const* player,
        uint32 requiredMapId,
        ProfileArea area)
    {
        if (!player)
            return false;

        if (requiredMapId != 0 &&
            player->GetMapId() !=
                requiredMapId)
        {
            return false;
        }

        switch (area)
        {
            case ProfileArea::Any:
                return true;
            case ProfileArea::StratholmeUndead:
                return IsStratholmeUndeadSide(player);
            case ProfileArea::DireMaulEast:
            case ProfileArea::DireMaulWest:
            case ProfileArea::DireMaulNorth:
                return GetDireMaulArea(player) == area;
            case ProfileArea::BlackrockUpper:
                return IsBlackrockUpper(player);
            case ProfileArea::BlackrockLower:
                return player->GetMapId() ==
                        MAP_BLACKROCK_SPIRE &&
                    !IsBlackrockUpper(player);
        }

        return false;
    }

    uint32 GetGenericDungeonLevelCap(
        Player* player)
    {
        if (!player)
            return 1;

        LFGDungeonEntry const* dungeon =
            GetLFGDungeon(
                player->GetMapId(),
                DUNGEON_DIFFICULTY_NORMAL);

        uint32 cap = 0;

        if (dungeon)
        {
            cap = dungeon->TargetLevelMax;

            if (!cap)
                cap = dungeon->MaxLevel;

            if (!cap)
                cap = dungeon->TargetLevel;
        }

        // If the map has no LFG row, use the player's own level as
        // a conservative fallback rather than granting level-54 buffs.
        if (!cap)
            cap = player->GetLevel();

        return std::max<uint32>(
            1,
            std::min<uint32>(
                cap,
                54));
    }

    bool RandomBotIsInPreparationScope(
        Player* master,
        Player* bot)
    {
        // Random bots are never swept globally. They are eligible
        // only while explicitly grouped/raided with the player.
        return master &&
            master->GetGroup() &&
            bot &&
            bot->IsInWorld() &&
            bot->GetGroup() ==
                master->GetGroup();
    }

    Player* ResolvePreparedBot(
        PlayerbotMgr* manager,
        ObjectGuid::LowType botGuid)
    {
        if (manager)
        {
            if (Player* bot =
                    manager->GetPlayerBot(
                        botGuid))
            {
                return bot;
            }
        }

        return sRandomPlayerbotMgr.
            GetPlayerBot(botGuid);
    }

    // =========================================================
    // Timed consumable effects
    // =========================================================

    void ProcessTimedAuras(
        Player* master,
        RaidConsumableTracker& tracker,
        uint32 diff)
    {
        if (!master)
            return;

        PlayerbotMgr* manager =
            PlayerbotsMgr::instance().
                GetPlayerbotMgr(master);

        if (!manager)
            return;

        for (TimedAura& timed :
             tracker.TimedAuras)
        {
            if (timed.ApplicationsUsed >=
                timed.MaxApplications)
            {
                continue;
            }

            if (timed.NextApplicationTimer >
                diff)
            {
                timed.NextApplicationTimer -=
                    diff;

                continue;
            }

            Player* bot =
                ResolvePreparedBot(
                    manager,
                    timed.BotGuid);

            // A bot that is temporarily unavailable, dead, or no
            // longer in the master's preparation scope is retried
            // shortly instead of consuming one of the three uses.
            if (!bot ||
                !bot->IsInWorld() ||
                !bot->IsAlive() ||
                !IsProfileLocationValid(
                    master,
                    tracker.RequiredMapId,
                    tracker.RequiredArea) ||
                !IsProfileLocationValid(
                    bot,
                    tracker.RequiredMapId,
                    tracker.RequiredArea) ||
                !BotIsInPreparationScope(
                    master,
                    bot))
            {
                timed.NextApplicationTimer =
                    5 * IN_MILLISECONDS;

                continue;
            }

            // Do not duplicate the aura if another source has
            // already restored it. Retry shortly after it ends.
            if (bot->HasAura(
                    timed.SpellId))
            {
                timed.NextApplicationTimer =
                    5 * IN_MILLISECONDS;

                continue;
            }

            if (!bot->AddAura(
                    timed.SpellId,
                    bot))
            {
                timed.NextApplicationTimer =
                    5 * IN_MILLISECONDS;

                continue;
            }

            ++timed.ApplicationsUsed;

            if (timed.ApplicationsUsed <
                timed.MaxApplications)
            {
                timed.NextApplicationTimer =
                    60 * IN_MILLISECONDS;
            }
            else
            {
                timed.NextApplicationTimer = 0;
            }
        }
    }

    // =========================================================
    // Tracker checks
    // =========================================================

    Unit* ResolveTrackedAuraTarget(
        PlayerbotMgr* manager,
        TrackedAura const& tracked)
    {
        if (!manager)
            return nullptr;

        Player* bot =
            ResolvePreparedBot(
                manager,
                tracked.BotGuid);

        if (!bot ||
            !bot->IsInWorld())
        {
            return nullptr;
        }

        if (!tracked.IsPetAura)
            return bot;

        return bot->GetPet();
    }

    uint32 CountMissingAuras(
        Player* master,
        RaidConsumableTracker const& tracker)
    {
        if (!master)
            return 0;

        PlayerbotMgr* manager =
            PlayerbotsMgr::instance().
                GetPlayerbotMgr(master);

        if (!manager)
            return 0;

        uint32 missing = 0;

        for (TrackedAura const& tracked :
             tracker.Auras)
        {
            if (!tracked.WarnOnMissing)
                continue;

            Unit* target =
                ResolveTrackedAuraTarget(
                    manager,
                    tracked);

            // Offline/dismissed bots/pets are not considered
            // expired raid buffs.
            if (!target)
                continue;

            if (!target->HasAura(
                    tracked.SpellId))
            {
                ++missing;
            }
        }

        return missing;
    }

    void CheckTrackedAuras(
        Player* master,
        RaidConsumableTracker& tracker)
    {
        if (!master ||
            !master->GetSession())
        {
            return;
        }

        PlayerbotMgr* manager =
            PlayerbotsMgr::instance().
                GetPlayerbotMgr(master);

        if (!manager)
            return;

        std::vector<std::string>
            newlyMissing;

        for (TrackedAura& tracked :
             tracker.Auras)
        {
            if (!tracked.WarnOnMissing)
                continue;

            Unit* target =
                ResolveTrackedAuraTarget(
                    manager,
                    tracked);

            if (!target)
                continue;

            bool hasAura =
                target->HasAura(
                    tracked.SpellId);

            // If something else restored the aura, allow a
            // future expiry to generate another warning.
            if (hasAura)
            {
                tracked.MissingNotified = false;
                continue;
            }

            if (tracked.MissingNotified)
                continue;

            tracked.MissingNotified = true;

            std::string line =
                tracked.BotName +
                " - " +
                tracked.AuraName;

            newlyMissing.push_back(line);
        }

        if (newlyMissing.empty())
            return;

        ChatHandler chat(
            master->GetSession());

        chat.SendSysMessage(
            "[Bot Consumables] Consumable buffs need refreshing.");

        constexpr std::size_t MAX_LINES = 8;

        std::size_t linesToShow =
            std::min<std::size_t>(
                newlyMissing.size(),
                MAX_LINES);

        for (std::size_t i = 0;
             i < linesToShow;
             ++i)
        {
            chat.PSendSysMessage(
                "{}",
                newlyMissing[i]);
        }

        if (newlyMissing.size() >
            MAX_LINES)
        {
            chat.PSendSysMessage(
                "...and {} more missing consumable buffs.",
                newlyMissing.size() -
                    MAX_LINES);
        }

        chat.PSendSysMessage(
            "Run .bot consumables {} to refresh them.",
            tracker.Profile);
    }

    // =========================================================
    // Clear tracker and applied auras
    // =========================================================

    void ClearTrackedAuras(
        Player* master,
        RaidConsumableTracker& tracker)
    {
        if (!master)
            return;

        PlayerbotMgr* manager =
            PlayerbotsMgr::instance().
                GetPlayerbotMgr(master);

        if (!manager)
            return;

        for (TrackedAura const& tracked :
             tracker.Auras)
        {
            Unit* target =
                ResolveTrackedAuraTarget(
                    manager,
                    tracked);

            if (!target)
                continue;

            target->RemoveAurasDueToSpell(
                tracked.SpellId);
        }

        for (TimedAura const& timed :
             tracker.TimedAuras)
        {
            Player* bot =
                ResolvePreparedBot(
                    manager,
                    timed.BotGuid);

            if (!bot ||
                !bot->IsInWorld())
            {
                continue;
            }

            bot->RemoveAurasDueToSpell(
                timed.SpellId);
        }

        tracker.TimedAuras.clear();
    }
}

// =============================================================
// Chat command
// =============================================================

class NaxxramasCoreBotRaidConsumablesCommand :
    public CommandScript
{
public:
    NaxxramasCoreBotRaidConsumablesCommand()
        : CommandScript(
            "NaxxramasCoreBotRaidConsumablesCommand")
    {
    }

    ChatCommandTable GetCommands() const override
    {
        static ChatCommandTable botCommandTable =
        {
            {
                "consumables",
                HandleConsumablesCommand,
                SEC_PLAYER,
                Console::No
            }
        };

        static ChatCommandTable commandTable =
        {
            {
                "bot",
                botCommandTable
            }
        };

        return commandTable;
    }

    static std::string NormalizeArgument(
        char const* args)
    {
        std::string value =
            args ? args : "";

        std::size_t first =
            value.find_first_not_of(
                " \t\r\n");

        if (first == std::string::npos)
            return "";

        std::size_t last =
            value.find_last_not_of(
                " \t\r\n");

        value =
            value.substr(
                first,
                last - first + 1);

        std::transform(
            value.begin(),
            value.end(),
            value.begin(),
            [](unsigned char ch)
            {
                return static_cast<char>(
                    std::tolower(ch));
            });

        return value;
    }

    static bool ParseRequestedLevel(
        std::string const& value,
        uint32& level)
    {
        if (value.empty())
            return false;

        uint32 result = 0;

        for (char ch : value)
        {
            if (!std::isdigit(
                    static_cast<unsigned char>(
                        ch)))
            {
                return false;
            }

            result =
                result * 10 +
                static_cast<uint32>(
                    ch - '0');

            if (result > 54)
                return false;
        }

        if (result < 1 ||
            result > 54)
        {
            return false;
        }

        level = result;
        return true;
    }

    static void SendUsage(
        ChatHandler* handler)
    {
        handler->SendSysMessage(
            "[Bot Consumables] Usage:");
        handler->SendSysMessage(
            ".bot consumables 1-54");
        handler->SendSysMessage(
            ".bot consumables mara | sunken | brd | scholo | stratud | dm | lbrs | ubrs | mc");
        handler->SendSysMessage(
            ".bot consumables status | clear");
    }

    static RaidConsumableTracker&
        ResetTracker(
            Player* master,
            std::string const& profile,
            uint32 mapId,
            ProfileArea area)
    {
        ObjectGuid::LowType masterGuid =
            master->GetGUID().
                GetCounter();

        auto oldTracker =
            RaidConsumableTrackers.find(
                masterGuid);

        if (oldTracker !=
            RaidConsumableTrackers.end())
        {
            ClearTrackedAuras(
                master,
                oldTracker->second);
        }

        RaidConsumableTracker& tracker =
            RaidConsumableTrackers[
                masterGuid];

        tracker.Profile = profile;
        tracker.UpdateTimer = 0;
        tracker.RequiredMapId = mapId;
        tracker.RequiredArea = area;
        tracker.Auras.clear();
        tracker.TimedAuras.clear();

        return tracker;
    }

    static void SendPreparationSummary(
        ChatHandler* handler,
        std::string const& label,
        PreparationStats const& stats)
    {
        handler->PSendSysMessage(
            "[Bot Consumables] {} preparation complete.",
            label);

        handler->PSendSysMessage(
            "{} bots prepared.",
            stats.BotsPrepared);

        handler->PSendSysMessage(
            "{} consumable aura effects applied or refreshed.",
            stats.AurasApplied);

        if (stats.AurasPreserved > 0)
        {
            handler->PSendSysMessage(
                "{} existing consumable aura effect(s) kept because they still had enough time remaining.",
                stats.AurasPreserved);
        }

        handler->PSendSysMessage(
            "{} consumable items supplied.",
            stats.ItemsAdded);

        if (stats.CachesAdded > 0)
        {
            handler->PSendSysMessage(
                "{} Cache of Mau'ari items supplied.",
                stats.CachesAdded);
        }

        if (stats.ReagentsAdded > 0)
        {
            handler->PSendSysMessage(
                "{} raid reagent items supplied.",
                stats.ReagentsAdded);
        }

        if (stats.PetBuffsSkipped > 0)
        {
            handler->PSendSysMessage(
                "{} Hunter pet buff set(s) skipped because no active pet was present.",
                stats.PetBuffsSkipped);
        }

        if (stats.UnsupportedBots > 0)
        {
            handler->PSendSysMessage(
                "{} bot(s) had no supported Classic consumable profile and were left unchanged.",
                stats.UnsupportedBots);
        }

        if (stats.ItemFailures > 0 ||
            stats.AuraFailures > 0)
        {
            handler->PSendSysMessage(
                "Warning: {} item top-up(s) and {} aura application(s) could not be completed.",
                stats.ItemFailures,
                stats.AuraFailures);
        }
    }

    static PlayerbotMgr* GetManager(
        ChatHandler* handler,
        Player* master)
    {
        PlayerbotMgr* manager =
            PlayerbotsMgr::instance().
                GetPlayerbotMgr(master);

        if (!manager)
        {
            handler->SendSysMessage(
                "[Bot Consumables] No Playerbot manager was found.");
        }

        return manager;
    }

    static bool HandleMoltenCoreCommand(
        ChatHandler* handler)
    {
        Player* master =
            handler->GetSession()->
                GetPlayer();

        if (!master)
            return false;

        if (master->GetMapId() !=
            MAP_MOLTEN_CORE)
        {
            handler->SendSysMessage(
                "[Bot Consumables] The Molten Core profile can only be used inside Molten Core.");
            return true;
        }

        PlayerbotMgr* manager =
            GetManager(
                handler,
                master);

        if (!manager)
            return false;

        RaidConsumableTracker& tracker =
            ResetTracker(
                master,
                "mc",
                MAP_MOLTEN_CORE,
                ProfileArea::Any);

        PreparationStats stats;

        for (PlayerBotMap::const_iterator itr =
                 manager->GetPlayerBotsBegin();
             itr != manager->GetPlayerBotsEnd();
             ++itr)
        {
            Player* bot = itr->second;

            if (!BotIsInPreparationScope(
                    master,
                    bot) ||
                !IsProfileLocationValid(
                    bot,
                    MAP_MOLTEN_CORE,
                    ProfileArea::Any))
            {
                continue;
            }

            PrepareMoltenCoreBot(
                bot,
                tracker,
                stats);
        }

        if (master->GetGroup())
        {
            for (PlayerBotMap::const_iterator itr =
                     sRandomPlayerbotMgr.
                         GetPlayerBotsBegin();
                 itr !=
                     sRandomPlayerbotMgr.
                         GetPlayerBotsEnd();
                 ++itr)
            {
                Player* bot = itr->second;

                if (!RandomBotIsInPreparationScope(
                        master,
                        bot) ||
                    !IsProfileLocationValid(
                        bot,
                        MAP_MOLTEN_CORE,
                        ProfileArea::Any))
                {
                    continue;
                }

                // Avoid a duplicate if a bot is somehow visible
                // through both holders.
                if (manager->GetPlayerBot(
                        bot->GetGUID().
                            GetCounter()))
                {
                    continue;
                }

                PrepareMoltenCoreBot(
                    bot,
                    tracker,
                    stats);
            }
        }

        if (stats.BotsPrepared == 0)
        {
            handler->SendSysMessage(
                "[Bot Consumables] No supported grouped/controlled bots were found in your current group/raid.");
            return true;
        }

        StartConsumableCooldown(
            master);

        SendPreparationSummary(
            handler,
            "Molten Core",
            stats);

        return true;
    }

    static bool HandleGenericLevelCommand(
        ChatHandler* handler,
        uint32 requestedLevel)
    {
        Player* master =
            handler->GetSession()->
                GetPlayer();

        if (!master ||
            !master->GetMap() ||
            !master->GetMap()->
                IsNonRaidDungeon())
        {
            handler->SendSysMessage(
                "[Bot Consumables] Level-scaled consumables can only be used inside a non-raid dungeon.");
            return true;
        }

        PlayerbotMgr* manager =
            GetManager(
                handler,
                master);

        if (!manager)
            return false;

        uint32 dungeonCap =
            GetGenericDungeonLevelCap(
                master);

        RaidConsumableTracker& tracker =
            ResetTracker(
                master,
                std::to_string(
                    requestedLevel),
                master->GetMapId(),
                ProfileArea::Any);

        PreparationStats stats;

        for (PlayerBotMap::const_iterator itr =
                 manager->GetPlayerBotsBegin();
             itr != manager->GetPlayerBotsEnd();
             ++itr)
        {
            Player* bot = itr->second;

            if (!BotIsInPreparationScope(
                    master,
                    bot) ||
                bot->GetMapId() !=
                    master->GetMapId())
            {
                continue;
            }

            uint32 effectiveLevel =
                std::min<uint32>(
                    requestedLevel,
                    std::min<uint32>(
                        bot->GetLevel(),
                        dungeonCap));

            PrepareDungeonBot(
                bot,
                effectiveLevel,
                ProtectionSchool::None,
                false,
                tracker,
                stats);
        }

        if (master->GetGroup())
        {
            for (PlayerBotMap::const_iterator itr =
                     sRandomPlayerbotMgr.
                         GetPlayerBotsBegin();
                 itr !=
                     sRandomPlayerbotMgr.
                         GetPlayerBotsEnd();
                 ++itr)
            {
                Player* bot = itr->second;

                if (!RandomBotIsInPreparationScope(
                        master,
                        bot) ||
                    bot->GetMapId() !=
                        master->GetMapId())
                {
                    continue;
                }

                if (manager->GetPlayerBot(
                        bot->GetGUID().
                            GetCounter()))
                {
                    continue;
                }

                uint32 effectiveLevel =
                    std::min<uint32>(
                        requestedLevel,
                        std::min<uint32>(
                            bot->GetLevel(),
                            dungeonCap));

                PrepareDungeonBot(
                    bot,
                    effectiveLevel,
                    ProtectionSchool::None,
                    false,
                    tracker,
                    stats);
            }
        }

        if (stats.BotsPrepared == 0)
        {
            handler->SendSysMessage(
                "[Bot Consumables] No supported grouped/controlled bots were found in this dungeon.");
            return true;
        }

        handler->PSendSysMessage(
            "[Bot Consumables] Requested level {}, dungeon cap {}.",
            requestedLevel,
            dungeonCap);

        StartConsumableCooldown(
            master);

        SendPreparationSummary(
            handler,
            "level-scaled dungeon",
            stats);

        return true;
    }

    static bool ResolveNamedProfile(
        Player* master,
        std::string const& command,
        uint32& mapId,
        uint32& levelCap,
        ProfileArea& area,
        ProtectionSchool& protection,
        bool& enhanced,
        std::string& label)
    {
        area = ProfileArea::Any;
        protection =
            ProtectionSchool::None;
        enhanced = false;

        if (command == "mara")
        {
            mapId = MAP_MARAUDON;
            levelCap = 54;
            protection =
                ProtectionSchool::Nature;
            label = "Maraudon";
        }
        else if (command == "sunken")
        {
            mapId = MAP_SUNKEN_TEMPLE;
            levelCap = 54;
            protection =
                ProtectionSchool::Nature;
            label = "Sunken Temple";
        }
        else if (command == "brd")
        {
            mapId = MAP_BLACKROCK_DEPTHS;
            levelCap = 60;
            protection =
                ProtectionSchool::Fire;
            label = "Blackrock Depths";
        }
        else if (command == "scholo")
        {
            mapId = MAP_SCHOLOMANCE;
            levelCap = 60;
            protection =
                ProtectionSchool::Shadow;
            label = "Scholomance";
        }
        else if (command == "stratud" ||
                 command == "strat")
        {
            mapId = MAP_STRATHOLME;
            levelCap = 60;
            area =
                ProfileArea::StratholmeUndead;
            protection =
                ProtectionSchool::Shadow;
            label =
                "Stratholme Undead";
        }
        else if (command == "lbrs")
        {
            mapId = MAP_BLACKROCK_SPIRE;
            levelCap = 60;
            area =
                ProfileArea::BlackrockLower;
            label =
                "Lower Blackrock Spire";
        }
        else if (command == "ubrs")
        {
            mapId = MAP_BLACKROCK_SPIRE;
            levelCap = 60;
            area =
                ProfileArea::BlackrockUpper;
            protection =
                ProtectionSchool::Fire;
            enhanced = true;
            label =
                "Upper Blackrock Spire";
        }
        else if (command == "dm")
        {
            mapId = MAP_DIRE_MAUL;
            levelCap = 60;

            area =
                GetDireMaulArea(
                    master);

            if (area ==
                ProfileArea::DireMaulEast)
            {
                protection =
                    ProtectionSchool::Nature;
                label =
                    "Dire Maul East";
            }
            else if (area ==
                     ProfileArea::DireMaulWest)
            {
                protection =
                    ProtectionSchool::Shadow;
                label =
                    "Dire Maul West";
            }
            else if (area ==
                     ProfileArea::DireMaulNorth)
            {
                enhanced = true;
                label =
                    "Dire Maul North";
            }
            else
            {
                return false;
            }
        }
        else
        {
            return false;
        }

        return true;
    }

    static bool HandleNamedDungeonCommand(
        ChatHandler* handler,
        std::string const& command)
    {
        Player* master =
            handler->GetSession()->
                GetPlayer();

        if (!master)
            return false;

        uint32 mapId = 0;
        uint32 levelCap = 60;
        ProfileArea area =
            ProfileArea::Any;
        ProtectionSchool protection =
            ProtectionSchool::None;
        bool enhanced = false;
        std::string label;

        if (!ResolveNamedProfile(
                master,
                command,
                mapId,
                levelCap,
                area,
                protection,
                enhanced,
                label))
        {
            SendUsage(handler);
            return true;
        }

        if (!IsProfileLocationValid(
                master,
                mapId,
                area))
        {
            handler->PSendSysMessage(
                "[Bot Consumables] The {} profile can only be used while you are physically inside that dungeon/wing.",
                label);
            return true;
        }

        PlayerbotMgr* manager =
            GetManager(
                handler,
                master);

        if (!manager)
            return false;

        std::string trackerCommand =
            (command == "strat")
                ? "stratud"
                : command;

        RaidConsumableTracker& tracker =
            ResetTracker(
                master,
                trackerCommand,
                mapId,
                area);

        PreparationStats stats;

        for (PlayerBotMap::const_iterator itr =
                 manager->GetPlayerBotsBegin();
             itr != manager->GetPlayerBotsEnd();
             ++itr)
        {
            Player* bot = itr->second;

            if (!BotIsInPreparationScope(
                    master,
                    bot) ||
                !IsProfileLocationValid(
                    bot,
                    mapId,
                    area))
            {
                continue;
            }

            uint32 effectiveLevel =
                std::min<uint32>(
                    bot->GetLevel(),
                    levelCap);

            PrepareDungeonBot(
                bot,
                effectiveLevel,
                protection,
                enhanced,
                tracker,
                stats);
        }

        if (master->GetGroup())
        {
            for (PlayerBotMap::const_iterator itr =
                     sRandomPlayerbotMgr.
                         GetPlayerBotsBegin();
                 itr !=
                     sRandomPlayerbotMgr.
                         GetPlayerBotsEnd();
                 ++itr)
            {
                Player* bot = itr->second;

                if (!RandomBotIsInPreparationScope(
                        master,
                        bot) ||
                    !IsProfileLocationValid(
                        bot,
                        mapId,
                        area))
                {
                    continue;
                }

                if (manager->GetPlayerBot(
                        bot->GetGUID().
                            GetCounter()))
                {
                    continue;
                }

                uint32 effectiveLevel =
                    std::min<uint32>(
                        bot->GetLevel(),
                        levelCap);

                PrepareDungeonBot(
                    bot,
                    effectiveLevel,
                    protection,
                    enhanced,
                    tracker,
                    stats);
            }
        }

        if (stats.BotsPrepared == 0)
        {
            handler->SendSysMessage(
                "[Bot Consumables] No supported grouped/controlled bots were found in this dungeon/wing.");
            return true;
        }

        StartConsumableCooldown(
            master);

        SendPreparationSummary(
            handler,
            label,
            stats);

        return true;
    }

    static bool HandleStatusCommand(
        ChatHandler* handler)
    {
        Player* master =
            handler->GetSession()->
                GetPlayer();

        if (!master)
            return false;

        auto itr =
            RaidConsumableTrackers.find(
                master->GetGUID().
                    GetCounter());

        if (itr ==
            RaidConsumableTrackers.end())
        {
            handler->SendSysMessage(
                "[Bot Consumables] No consumable profile is currently being tracked.");
            return true;
        }

        RaidConsumableTracker const& tracker =
            itr->second;

        uint32 cooldownRemaining =
            GetConsumableCooldownRemaining(
                master);

        if (cooldownRemaining > 0)
        {
            handler->PSendSysMessage(
                "[Bot Consumables] Preparation cooldown: {}m {}s remaining.",
                cooldownRemaining / 60,
                cooldownRemaining % 60);
        }
        else
        {
            handler->SendSysMessage(
                "[Bot Consumables] Preparation cooldown: ready.");
        }

        uint32 missing =
            CountMissingAuras(
                master,
                tracker);

        handler->PSendSysMessage(
            "[Bot Consumables] Active profile: {}.",
            tracker.Profile);

        handler->PSendSysMessage(
            "{} consumable auras are being tracked.",
            tracker.Auras.size());

        uint32 timedActive = 0;

        for (TimedAura const& timed :
             tracker.TimedAuras)
        {
            if (timed.ApplicationsUsed <
                timed.MaxApplications)
            {
                ++timedActive;
            }
        }

        if (timedActive > 0)
        {
            handler->PSendSysMessage(
                "{} timed consumable sequence(s) are still active.",
                timedActive);
        }

        if (missing == 0)
        {
            handler->SendSysMessage(
                "All warning-enabled tracked bot auras are present.");
        }
        else
        {
            handler->PSendSysMessage(
                "{} tracked consumable aura(s) are currently missing.",
                missing);
        }

        return true;
    }

    static bool HandleClearCommand(
        ChatHandler* handler)
    {
        Player* master =
            handler->GetSession()->
                GetPlayer();

        if (!master)
            return false;

        ObjectGuid::LowType masterGuid =
            master->GetGUID().
                GetCounter();

        auto itr =
            RaidConsumableTrackers.find(
                masterGuid);

        if (itr ==
            RaidConsumableTrackers.end())
        {
            handler->SendSysMessage(
                "[Bot Consumables] Nothing is currently being tracked.");
            return true;
        }

        ClearTrackedAuras(
            master,
            itr->second);

        RaidConsumableTrackers.erase(
            itr);

        handler->SendSysMessage(
            "[Bot Consumables] Tracked consumable auras have been removed and tracking has been cleared.");

        return true;
    }

    static bool HandleConsumablesCommand(
        ChatHandler* handler,
        char const* args)
    {
        if (!handler ||
            !handler->GetSession())
        {
            return false;
        }

        std::string command =
            NormalizeArgument(args);

        if (command.empty())
        {
            SendUsage(handler);
            return true;
        }

        if (command == "status")
            return HandleStatusCommand(handler);

        if (command == "clear")
            return HandleClearCommand(handler);

        uint32 requestedLevel = 0;

        bool isLevelCommand =
            ParseRequestedLevel(
                command,
                requestedLevel);

        bool isNamedCommand =
            command == "mara" ||
            command == "sunken" ||
            command == "brd" ||
            command == "scholo" ||
            command == "stratud" ||
            command == "strat" ||
            command == "dm" ||
            command == "lbrs" ||
            command == "ubrs";

        bool isPreparationCommand =
            command == "mc" ||
            isLevelCommand ||
            isNamedCommand;

        if (!isPreparationCommand)
        {
            SendUsage(handler);
            return true;
        }

        Player* master =
            handler->GetSession()->
                GetPlayer();

        if (!master)
            return false;

        if (!master->IsAlive())
        {
            ResetConsumableCooldownForGroup(
                master);

            handler->SendSysMessage(
                "[Bot Consumables] Your death has reset the preparation cooldown. Resurrect before preparing consumables.");
            return true;
        }

        if (!CheckConsumableCooldown(
                handler,
                master))
        {
            return true;
        }

        if (command == "mc")
            return HandleMoltenCoreCommand(handler);

        if (isLevelCommand)
        {
            return HandleGenericLevelCommand(
                handler,
                requestedLevel);
        }

        return HandleNamedDungeonCommand(
            handler,
            command);
    }
};

// =============================================================
// Aura expiry monitor
// =============================================================

class NaxxramasCoreBotRaidConsumablesTracker :
    public PlayerScript
{
public:
    NaxxramasCoreBotRaidConsumablesTracker()
        : PlayerScript(
            "NaxxramasCoreBotRaidConsumablesTracker",
            {
                PLAYERHOOK_ON_UPDATE,
                PLAYERHOOK_ON_LOGOUT
            })
    {
    }

    void OnPlayerUpdate(
        Player* player,
        uint32 diff) override
    {
        if (!player)
            return;

        ObjectGuid::LowType guid =
            player->GetGUID().
                GetCounter();

        bool alive =
            player->IsAlive();

        auto aliveItr =
            ConsumableAliveState.find(
                guid);

        if (aliveItr ==
            ConsumableAliveState.end())
        {
            ConsumableAliveState[
                guid] = alive;
        }
        else
        {
            if (aliveItr->second &&
                !alive)
            {
                ResetConsumableCooldownForGroup(
                    player);
            }

            aliveItr->second = alive;
        }

        auto itr =
            RaidConsumableTrackers.find(
                guid);

        if (itr ==
            RaidConsumableTrackers.end())
        {
            return;
        }

        RaidConsumableTracker& tracker =
            itr->second;

        if (!IsProfileLocationValid(
                player,
                tracker.RequiredMapId,
                tracker.RequiredArea))
        {
            ClearTrackedAuras(player, tracker);
            RaidConsumableTrackers.erase(itr);

            if (player->GetSession())
            {
                ChatHandler(player->GetSession()).
                    SendSysMessage(
                        "[Bot Consumables] Consumable profile cleared because you left its allowed instance.");
            }

            return;
        }

        ProcessTimedAuras(
            player,
            tracker,
            diff);

        tracker.UpdateTimer += diff;

        if (tracker.UpdateTimer <
            AURA_CHECK_INTERVAL)
        {
            return;
        }

        tracker.UpdateTimer = 0;

        CheckTrackedAuras(
            player,
            tracker);
    }

    void OnPlayerLogout(
        Player* player) override
    {
        if (!player)
            return;

        ObjectGuid::LowType guid =
            player->GetGUID().
                GetCounter();

        RaidConsumableTrackers.erase(
            guid);

        ConsumableAliveState.erase(
            guid);

        // Keep an unexpired cooldown across logout so relogging
        // cannot bypass the 10-minute restriction.
    }
};

// =============================================================
// Loader
// =============================================================

void AddBotRaidConsumablesScripts()
{
    new NaxxramasCoreBotRaidConsumablesCommand();
    new NaxxramasCoreBotRaidConsumablesTracker();
}