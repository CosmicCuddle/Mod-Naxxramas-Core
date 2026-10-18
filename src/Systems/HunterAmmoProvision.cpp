/*
 * Naxxramas Core / Bot Consumables - Hunter ammunition top-up
 *
 * Off by default. Inventory only; does NOT equip, SetAmmo, change weapons,
 * use mail, grant rare/quest/PvP ammunition, or bypass the command cooldown.
 * Caller is an already-scoped, human-master-invoked dungeon/raid preparation.
 */
#include "HunterAmmoProvision.h"
#include "HunterAmmoSelection.h"

#include "Config.h"
#include "Item.h"
#include "ItemTemplate.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "PlayerbotAI.h"
#include "PlayerbotMgr.h"

#include <algorithm>
#include <cstdint>

namespace NaxxramasHunterAmmo
{
    Result TopUpHunterAmmo(Player* bot, uint32_t effectiveLevel)
    {
        // The user must explicitly enable this separately from ordinary
        // consumable auras; never grant on module install or login.
        if (!sConfigMgr->GetOption<bool>(
                "NaxxramasCore.BotConsumables.HunterAmmo.Enabled", false))
            return {0, 0, Status::Disabled};

        if (!bot || !bot->IsInWorld() || !bot->IsAlive() ||
            bot->getClass() != CLASS_HUNTER)
            return {0, 0, Status::SkippedNotEligible};

        PlayerbotAI* ai = PlayerbotsMgr::instance().GetPlayerbotAI(bot);
        // The first rollout is intentionally confined to controlled Altbots:
        // NEVER give free ammo to human characters or global Random Bots.
        if (!ai || !ai->IsAltBot())
            return {0, 0, Status::SkippedNotEligible};

        Item* weapon = bot->GetWeaponForAttack(RANGED_ATTACK);
        if (!weapon || weapon->IsBroken())
            return {0, 0, Status::NoCompatibleRangedWeapon};

        ItemTemplate const* weaponTemplate = weapon->GetTemplate();
        if (!weaponTemplate ||
            weaponTemplate->Class != ITEM_CLASS_WEAPON)
            return {0, 0, Status::NoCompatibleRangedWeapon};

        // Use both the owner's actual level and the selected dungeon/IP
        // preparation cap; never grant out-of-era ammo to a higher-level bot.
        uint32_t const level = std::min<uint32_t>(
            std::min<uint32_t>(bot->GetLevel(), effectiveLevel), 60);

        uint32_t const selected = bot->GetUInt32Value(PLAYER_AMMO_ID);
        // Non-vendor selected ammo can represent earned quest or crafted
        // supplies. Selected status alone does NOT grant infinite free ammo.
        // This second explicit opt-in is independent from overall enablement.
        bool const allowSelectedNonVendor = sConfigMgr->GetOption<bool>(
            "NaxxramasCore.BotConsumables.HunterAmmo.AllowSelectedNonVendor", false);
        Selection const chosen = ChooseAmmo(
            weaponTemplate->SubClass, selected, level,
            allowSelectedNonVendor);

        if (!chosen.itemId)
        {
            return {0, 0, chosen.decision == Decision::UnsupportedWeapon
                ? Status::NoCompatibleRangedWeapon : Status::UnsupportedSelection};
        }

        ItemTemplate const* ammo = sObjectMgr->GetItemTemplate(chosen.itemId);
        if (!ammo ||
            ammo->Class != ITEM_CLASS_PROJECTILE ||
            ammo->SubClass != chosen.projectileSubclass ||
            ammo->InventoryType != INVTYPE_AMMO ||
            ammo->RequiredLevel > level ||
            ammo->ItemLevel > 60 ||
            ammo->Quality > ITEM_QUALITY_UNCOMMON ||
            ammo->Stackable <= 0 ||
            !bot->CheckAmmoCompatibility(ammo) ||
            bot->CanUseAmmo(chosen.itemId) != EQUIP_ERR_OK)
        {
            return {0, chosen.itemId, Status::ItemRejected};
        }

        uint32_t target = static_cast<uint32_t>(
            std::clamp<int32>(
                sConfigMgr->GetOption<int32>(
                    "NaxxramasCore.BotConsumables.HunterAmmo.TargetCount", 600),
                1, 1000));

        if (ammo->MaxCount > 0)
            target = std::min<uint32_t>(
                target, static_cast<uint32_t>(ammo->MaxCount));

        uint32_t const before = bot->GetItemCount(chosen.itemId, false);
        if (before >= target)
            return {0, chosen.itemId, Status::AlreadySupplied};

        uint32_t const needed = target - before;

        // Unlike the general TopUpToCount helper, do not risk a partial
        // bag-space grant. Native AddItem may add only SOME requested ammo;
        // always count the actual before/after delta as well.
        ItemPosCountVec destination;
        uint32 noSpace = 0;
        InventoryResult const capacity = bot->CanStoreNewItem(
            NULL_BAG, NULL_SLOT, destination, chosen.itemId, needed, &noSpace);

        if (capacity != EQUIP_ERR_OK || noSpace || destination.empty())
            return {0, chosen.itemId, Status::NoBagSpace};

        // Only the command explicitly grants items; no timers or per-tick
        // restock. Do not change PLAYER_AMMO_ID or ammo bag/equipment.
        bot->AddItem(chosen.itemId, needed);
        uint32_t const after = bot->GetItemCount(chosen.itemId, false);
        uint32_t const added = after > before
            ? std::min<uint32_t>(after - before, needed) : 0;

        if (!added)
            return {0, chosen.itemId, Status::NoBagSpace};

        return {added, chosen.itemId,
                selected ? Status::AddedSelectedAmmo
                         : Status::AddedVendorAmmoNeedsSelection};
    }
}
