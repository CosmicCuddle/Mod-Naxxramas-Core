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
#include "Item.h"
#include "ItemTemplate.h"
#include "Map.h"
#include "ObjectMgr.h"
#include "Pet.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"
#include "ScriptMgr.h"
#include "SharedDefines.h"
#include "WorldSession.h"

#include <algorithm>
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

    constexpr uint32 MAP_MOLTEN_CORE = 409;

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

    constexpr uint32 ITEM_MAJOR_HEALING_POTION = 13446;
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
    constexpr uint32 ITEM_GREATER_ARCANE_ELIXIR = 13454;
    constexpr uint32 ITEM_ELIXIR_OF_THE_SAGES = 13447;
    constexpr uint32 ITEM_ELIXIR_OF_GREATER_INTELLECT = 9179;

    constexpr uint32 ITEM_ELIXIR_OF_SHADOW_POWER = 9264;
    constexpr uint32 ITEM_ELIXIR_OF_FROST_POWER = 17708;

    constexpr uint32 ITEM_ELIXIR_OF_GIANTS = 9206;
    constexpr uint32 ITEM_ELIXIR_OF_FORTITUDE = 3825;
    constexpr uint32 ITEM_ELIXIR_OF_SUPERIOR_DEFENSE = 13445;

    // =========================================================
    // Protection / defensive potion effects
    // Applied as auras rather than supplied as potion items.
    // =========================================================

    constexpr uint32 ITEM_GREATER_FIRE_PROTECTION_POTION = 13457;
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

    // =========================================================
    // Tracking
    // =========================================================

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
        std::vector<TrackedAura> Auras;
        std::vector<TimedAura> TimedAuras;
    };

    struct PreparationStats
    {
        uint32 BotsPrepared = 0;
        uint32 UnsupportedBots = 0;
        uint32 AurasApplied = 0;
        uint32 AuraFailures = 0;
        uint32 ItemsAdded = 0;
        uint32 ItemFailures = 0;
        uint32 CachesAdded = 0;
        uint32 ReagentsAdded = 0;
        uint32 PetBuffsSkipped = 0;
    };

    std::unordered_map<ObjectGuid::LowType, RaidConsumableTracker>
        RaidConsumableTrackers;

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
            case ITEM_MAJOR_HEALING_POTION:
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
        bool warnOnMissing = true)
    {
        if (!bot || !target || !spellId)
        {
            ++stats.AuraFailures;
            return false;
        }

        target->RemoveAurasDueToSpell(spellId);

        if (!bot->AddAura(spellId, target))
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
        bool warnOnMissing = true)
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
            warnOnMissing);
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
                topUp(ITEM_ANKH, 10);
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
            stats);
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
            stats);
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
            stats);
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
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_LUNG_JUICE_COCKTAIL,
            "Lung Juice Cocktail",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_RUMSEY_RUM_BLACK_LABEL,
            "Rumsey Rum Black Label",
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
            ITEM_ELIXIR_OF_GIANTS,
            "Elixir of Giants",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_ROIDS,
            "R.O.I.D.S.",
            false, tracker, stats);

        ApplyItemAura(
            bot, bot,
            ITEM_RUMSEY_RUM_BLACK_LABEL,
            "Rumsey Rum Black Label",
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
                manager->GetPlayerBot(
                    timed.BotGuid);

            // A bot that is temporarily unavailable, dead, or no
            // longer in the master's preparation scope is retried
            // shortly instead of consuming one of the three uses.
            if (!bot ||
                !bot->IsInWorld() ||
                !bot->IsAlive() ||
                (tracker.RequiredMapId != 0 &&
                    (master->GetMapId() != tracker.RequiredMapId ||
                     bot->GetMapId() != tracker.RequiredMapId)) ||
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
            manager->GetPlayerBot(
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
                manager->GetPlayerBot(
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
        static ChatCommandTable
            consumablesCommandTable =
        {
            {
                "mc",
                HandleMoltenCoreCommand,
                SEC_PLAYER,
                Console::No
            },
            {
                "status",
                HandleStatusCommand,
                SEC_PLAYER,
                Console::No
            },
            {
                "clear",
                HandleClearCommand,
                SEC_PLAYER,
                Console::No
            }
        };

        static ChatCommandTable
            botCommandTable =
        {
            {
                "consumables",
                consumablesCommandTable
            }
        };

        static ChatCommandTable
            commandTable =
        {
            {
                "bot",
                botCommandTable
            }
        };

        return commandTable;
    }

    static bool HandleMoltenCoreCommand(
        ChatHandler* handler)
    {
        if (!handler ||
            !handler->GetSession())
        {
            return false;
        }

        Player* master =
            handler->GetSession()->
                GetPlayer();

        if (!master)
            return false;

        if (master->GetMapId() != MAP_MOLTEN_CORE)
        {
            handler->SendSysMessage(
                "[Bot Consumables] The Molten Core profile can only be used inside Molten Core.");
            return true;
        }

        PlayerbotMgr* manager =
            PlayerbotsMgr::instance().
                GetPlayerbotMgr(master);

        if (!manager)
        {
            handler->SendSysMessage(
                "[Bot Consumables] No Playerbot manager was found.");

            return false;
        }

        ObjectGuid::LowType masterGuid =
            master->GetGUID().
                GetCounter();

        auto oldTracker =
            RaidConsumableTrackers.find(masterGuid);

        if (oldTracker != RaidConsumableTrackers.end())
            ClearTrackedAuras(master, oldTracker->second);

        RaidConsumableTracker& tracker =
            RaidConsumableTrackers[masterGuid];

        tracker.Profile = "mc";
        tracker.UpdateTimer = 0;
        tracker.RequiredMapId = MAP_MOLTEN_CORE;
        tracker.Auras.clear();
        tracker.TimedAuras.clear();

        PreparationStats stats;

        for (PlayerBotMap::const_iterator itr =
                 manager->GetPlayerBotsBegin();
             itr != manager->GetPlayerBotsEnd();
             ++itr)
        {
            Player* bot =
                itr->second;

            if (!BotIsInPreparationScope(
                    master,
                    bot))
            {
                continue;
            }

            PrepareMoltenCoreBot(
                bot,
                tracker,
                stats);
        }

        if (stats.BotsPrepared == 0)
        {
            handler->SendSysMessage(
                "[Bot Consumables] No supported controlled bots were found in your current group/raid.");

            return true;
        }

        handler->SendSysMessage(
            "[Bot Consumables] Molten Core preparation complete.");

        handler->PSendSysMessage(
            "{} bots prepared.",
            stats.BotsPrepared);

        handler->PSendSysMessage(
            "{} consumable aura effects applied or refreshed.",
            stats.AurasApplied);

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
                "{} bot(s) had no Molten Core consumable profile and were left unchanged.",
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

        return true;
    }

    static bool HandleStatusCommand(
        ChatHandler* handler)
    {
        if (!handler ||
            !handler->GetSession())
        {
            return false;
        }

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
                "[Bot Consumables] No raid consumable profile is currently being tracked.");

            return true;
        }

        RaidConsumableTracker const& tracker =
            itr->second;

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
                "All currently available tracked bot auras are present.");
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
        if (!handler ||
            !handler->GetSession())
        {
            return false;
        }

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
            "[Bot Consumables] Tracked raid consumable auras have been removed and tracking has been cleared.");

        return true;
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

        if (tracker.RequiredMapId != 0 &&
            player->GetMapId() != tracker.RequiredMapId)
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

        RaidConsumableTrackers.erase(
            player->GetGUID().
                GetCounter());
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