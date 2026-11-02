/*
 * Naxxramas Core / Bot Consumables - Hunter ammunition top-up
 *
 * Off by default. Inventory only; does NOT equip, SetAmmo, change weapons,
 * use mail, grant arbitrary rare/quest/PvP ammo, or bypass the command cooldown.
 * A separate default-OFF owner option permits <=200 Doomshot per eligible bot.
 * Caller is an already-scoped, human-master-invoked dungeon/raid preparation.
 */
#include "HunterAmmoProvision.h"
#include "HunterAmmoSelection.h"

#include "Bag.h"
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
    // Place projectiles in the explicitly selected equipped quiver slot.
    // This is NOT a generic bag insertion and never moves existing items.
    static uint32_t StoreAmmoInQuiverSlot(Player* bot, uint8 bagSlot,
                                          uint8 itemSlot, uint32_t itemId,
                                          uint32_t count)
    {
        if (!count)
            return 0;

        ItemPosCountVec dest;
        uint32 noSpace = 0;
        if (bot->CanStoreNewItem(bagSlot, itemSlot, dest, itemId,
                                count, &noSpace) != EQUIP_ERR_OK ||
            noSpace || dest.empty())
            return 0;

        uint32 const before = bot->GetItemCount(itemId, false);
        Item* addedItem = bot->StoreNewItem(dest, itemId, true);
        if (!addedItem)
            return 0;

        uint32 const after = bot->GetItemCount(itemId, false);
        uint32 const added = ObservedAdded(before, after, count);
        if (added)
            bot->SendNewItem(addedItem, added, true, false);
        return added;
    }

    // Explicitly MC-only and default OFF. Restrict to a real equipped
    // 16-slot quiver or ammo pouch and to actual item_template stack sizes.
    // Existing items (including non-catalogue arrows) are never removed.
    static Result FillMoltenCoreQuiver(Player* bot, uint32_t level,
                                      uint32_t selected, uint32_t weaponSubclass,
                                      Selection chosen,
                                      ItemTemplate const* vendorTemplate)
    {
        uint32_t const wanted = ProjectileForWeapon(weaponSubclass);
        if (!wanted)
            return {0, 0, Status::NoCompatibleRangedWeapon};

        Bag* quiver = nullptr;
        uint8 quiverPos = NULL_BAG;
        for (uint8 slot = INVENTORY_SLOT_BAG_START;
             slot < INVENTORY_SLOT_BAG_END; ++slot)
        {
            Bag* equipped = bot->GetBagByPos(slot);
            ItemTemplate const* bagTemplate =
                equipped ? equipped->GetTemplate() : nullptr;
            if (!bagTemplate ||
                bagTemplate->Class != ITEM_CLASS_QUIVER ||
                bagTemplate->SubClass !=
                    (wanted == 2 ? ITEM_SUBCLASS_QUIVER
                                 : ITEM_SUBCLASS_AMMO_POUCH) ||
                equipped->GetBagSize() != MoltenCoreQuiverSlotCount)
                continue;
            quiver = equipped;
            quiverPos = slot;
            break;
        }

        // If there is no matching 16-slot quiver, do not grant several
        // thousand free projectiles through ordinary inventory bags.
        if (!quiver)
            return {0, chosen.itemId, Status::NoMatchingQuiver};

        uint32_t const fallbackSlotTarget =
            QuiverSlotTarget(vendorTemplate->Stackable);
        if (!fallbackSlotTarget)
            return {0, chosen.itemId, Status::ItemRejected};

        uint32_t rareAdded = 0;
        uint32_t vendorAdded = 0;
        bool const allowRare = sConfigMgr->GetOption<bool>(
            "NaxxramasCore.BotConsumables.HunterAmmo.AllowOneDoomshotAllocation",
            false);
        uint32_t const beforeRare = bot->GetItemCount(DoomshotItemId, false);
        uint32_t rareTarget = DoomshotAllocationTarget(
            MoltenCoreQuiverSlotCount * MoltenCoreQuiverSlotTarget,
            selected, weaponSubclass, level, beforeRare, allowRare);

        ItemTemplate const* rareTemplate =
            rareTarget ? sObjectMgr->GetItemTemplate(DoomshotItemId) : nullptr;
        if (!rareTemplate ||
            rareTemplate->Class != ITEM_CLASS_PROJECTILE ||
            rareTemplate->SubClass != wanted ||
            rareTemplate->InventoryType != INVTYPE_AMMO ||
            rareTemplate->RequiredLevel > level ||
            rareTemplate->ItemLevel > 60 ||
            rareTemplate->Quality != ITEM_QUALITY_RARE ||
            !(rareTemplate->BagFamily & BAG_FAMILY_MASK_ARROWS) ||
            !bot->CheckAmmoCompatibility(rareTemplate) ||
            bot->CanUseAmmo(DoomshotItemId) != EQUIP_ERR_OK)
            rareTarget = 0;
        else
            rareTarget = std::min<uint32_t>(
                rareTarget, QuiverSlotTarget(rareTemplate->Stackable));

        // A single rare quiver slot, with an absolute character-wide
        // cap of 200 Doomshot. Do not create Doomshot if none existed.
        if (rareTarget && beforeRare < rareTarget)
        {
            uint32_t const shortfall = Shortfall(beforeRare, rareTarget);
            for (uint8 i = 0; i < quiver->GetBagSize(); ++i)
            {
                Item* slotItem = bot->GetItemByPos(quiverPos, i);
                if (slotItem && slotItem->GetEntry() != DoomshotItemId)
                    continue;
                uint32_t const inSlot = slotItem ? slotItem->GetCount() : 0;
                uint32_t const amount = std::min<uint32_t>(
                    shortfall, Shortfall(inSlot, rareTarget));
                rareAdded = StoreAmmoInQuiverSlot(
                    bot, quiverPos, i, DoomshotItemId, amount);
                if (rareAdded)
                    break;
            }
        }

        // If the bot has a full Doomshot allocation outside the quiver,
        // never copy or move it. Instead reserve one empty quiver slot so
        // that legitimate stack can later be placed there by the owner/bot.
        bool rarePresentInQuiver = false;
        for (uint8 i = 0; i < quiver->GetBagSize(); ++i)
        {
            Item* slotItem = bot->GetItemByPos(quiverPos, i);
            if (slotItem && slotItem->GetEntry() == DoomshotItemId)
                rarePresentInQuiver = true;
        }
        bool reserveEmptyForOwnedRare = rareTarget && !rarePresentInQuiver;
        // Fill compatible vendor arrows/bullets into existing matching
        // stacks and remaining empty quiver slots. Keep unusual items as-is.
        for (uint8 i = 0; i < quiver->GetBagSize(); ++i)
        {
            Item* slotItem = bot->GetItemByPos(quiverPos, i);
            if (slotItem && slotItem->GetEntry() != chosen.itemId)
                continue;
            if (!slotItem && reserveEmptyForOwnedRare)
            {
                reserveEmptyForOwnedRare = false;
                continue;
            }
            uint32_t const current = slotItem ? slotItem->GetCount() : 0;
            uint32_t const toAdd = Shortfall(current, fallbackSlotTarget);
            vendorAdded += StoreAmmoInQuiverSlot(
                bot, quiverPos, i, chosen.itemId, toAdd);
        }

        uint32_t const totalAdded = vendorAdded + rareAdded;
        if (!totalAdded)
            return {0, chosen.itemId, Status::AlreadySupplied};

        return {totalAdded, chosen.itemId,
                vendorAdded && chosen.decision == Decision::VendorFallback
                    ? Status::AddedVendorAmmoNeedsSelection
                    : Status::AddedSelectedAmmo,
                rareAdded};
    }

    Result TopUpHunterAmmo(Player* bot, uint32_t effectiveLevel,
                           bool moltenCoreProfile)
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

        // A separate MC owner option may fill one *equipped* 16-slot
        // quiver in 200-arrow allotments; never use this in dungeons.
        // It does not change the original 600-arrow preparation elsewhere.
        bool const quiverMode = moltenCoreProfile &&
            bot->GetMapId() == 409 &&
            sConfigMgr->GetOption<bool>(
                "NaxxramasCore.BotConsumables.HunterAmmo.MoltenCore.FillQuiver.Enabled",
                false);
        if (quiverMode)
        {
            // Even when another independent flag permits selected Thorium,
            // the 16-slot quiver mode must NEVER multiply that nonvendor
            // item into thousands of free projectiles. Prefer the selected
            // vendor ammunition, otherwise the legal vendor fallback.
            Selection quiverChoice = chosen;
            if (!IsApprovedVendorAmmo(quiverChoice.itemId))
                quiverChoice = ChooseAmmo(
                    weaponTemplate->SubClass, 0, level);

            ItemTemplate const* quiverAmmo =
                sObjectMgr->GetItemTemplate(quiverChoice.itemId);
            if (!quiverChoice.itemId || !quiverAmmo ||
                quiverAmmo->Class != ITEM_CLASS_PROJECTILE ||
                quiverAmmo->SubClass != quiverChoice.projectileSubclass ||
                quiverAmmo->InventoryType != INVTYPE_AMMO ||
                quiverAmmo->RequiredLevel > level ||
                quiverAmmo->ItemLevel > 60 ||
                quiverAmmo->Quality > ITEM_QUALITY_UNCOMMON ||
                QuiverSlotTarget(quiverAmmo->Stackable) == 0 ||
                !bot->CheckAmmoCompatibility(quiverAmmo) ||
                bot->CanUseAmmo(quiverChoice.itemId) != EQUIP_ERR_OK)
                return {0, quiverChoice.itemId, Status::ItemRejected};

            return FillMoltenCoreQuiver(
                bot, level, selected, weaponTemplate->SubClass,
                quiverChoice, quiverAmmo);
        }

        uint32_t const totalTarget = TargetCount(
            sConfigMgr->GetOption<int32>(
                "NaxxramasCore.BotConsumables.HunterAmmo.TargetCount", 600), 0);
        uint32_t rareAdded = 0;
        uint32_t rareInBags = 0;

        // Explicitly owner-authorized Doomshot exception only. Require
        // pre-existing legitimately selected Doomshot in the bot's bags:
        // never invent this rare ammunition for a Hunter who had none.
        // Separate from the existing Thorium selection opt-in.
        uint32_t const beforeRare = bot->GetItemCount(DoomshotItemId, false);
        bool const allowDoomshot = sConfigMgr->GetOption<bool>(
            "NaxxramasCore.BotConsumables.HunterAmmo.AllowOneDoomshotAllocation", false);
        uint32_t rareTarget = DoomshotAllocationTarget(
            totalTarget, selected, weaponTemplate->SubClass,
            level, beforeRare, allowDoomshot);

        if (rareTarget && chosen.decision == Decision::VendorFallback)
        {
            ItemTemplate const* rareTemplate =
                sObjectMgr->GetItemTemplate(DoomshotItemId);

            // The separate owner setting explicitly permits this one item.
            // Doomshot itself is RARE; do not weaken the ordinary
            // uncommon-or-below vendor catalogue validation above.
            if (!rareTemplate ||
                rareTemplate->Class != ITEM_CLASS_PROJECTILE ||
                rareTemplate->SubClass != 2 ||
                rareTemplate->InventoryType != INVTYPE_AMMO ||
                rareTemplate->RequiredLevel > level ||
                rareTemplate->ItemLevel > 60 ||
                rareTemplate->Quality != ITEM_QUALITY_RARE ||
                rareTemplate->Stackable <= 0 ||
                !bot->CheckAmmoCompatibility(rareTemplate) ||
                bot->CanUseAmmo(DoomshotItemId) != EQUIP_ERR_OK)
            {
                rareTarget = 0;
            }
            else
            {
                // Respect actual server stack and maximum owned count.
                rareTarget = std::min<uint32_t>(
                    rareTarget, static_cast<uint32_t>(rareTemplate->Stackable));
                if (rareTemplate->MaxCount > 0)
                    rareTarget = std::min<uint32_t>(
                        rareTarget, static_cast<uint32_t>(rareTemplate->MaxCount));

                uint32_t const rareNeeded = Shortfall(beforeRare, rareTarget);
                if (rareNeeded)
                {
                    ItemPosCountVec rareDestination;
                    uint32 rareNoSpace = 0;
                    InventoryResult const rareCapacity = bot->CanStoreNewItem(
                        NULL_BAG, NULL_SLOT, rareDestination,
                        DoomshotItemId, rareNeeded, &rareNoSpace);

                    if (rareCapacity == EQUIP_ERR_OK && !rareNoSpace &&
                        !rareDestination.empty())
                    {
                        bot->AddItem(DoomshotItemId, rareNeeded);
                        uint32_t const afterRare =
                            bot->GetItemCount(DoomshotItemId, false);
                        rareAdded = ObservedAdded(
                            beforeRare, afterRare, rareNeeded);
                    }
                }
                rareInBags = std::min<uint32_t>(
                    bot->GetItemCount(DoomshotItemId, false), rareTarget);
            }
        }

        // Keep the total prepared supply within TargetCount, counting the
        // bot's existing permitted rare allocation against the allowance.
        // Vendor ammo still respects the normal item MaxCount.
        uint32_t target = TargetCount(
            sConfigMgr->GetOption<int32>(
                "NaxxramasCore.BotConsumables.HunterAmmo.TargetCount", 600),
            ammo->MaxCount);
        if (chosen.decision == Decision::VendorFallback && rareInBags)
            target = std::min<uint32_t>(
                target, totalTarget - rareInBags);

        uint32_t const before = bot->GetItemCount(chosen.itemId, false);
        uint32_t const needed = Shortfall(before, target);
        if (!needed)
            return rareAdded
                ? Result{rareAdded, DoomshotItemId, Status::AddedSelectedAmmo, rareAdded}
                : Result{0, chosen.itemId, Status::AlreadySupplied};

        // Unlike the general TopUpToCount helper, do not risk a partial
        // bag-space grant. Native AddItem may add only SOME requested ammo;
        // always count the actual before/after delta as well.
        ItemPosCountVec destination;
        uint32 noSpace = 0;
        InventoryResult const capacity = bot->CanStoreNewItem(
            NULL_BAG, NULL_SLOT, destination, chosen.itemId, needed, &noSpace);

        if (capacity != EQUIP_ERR_OK || noSpace || destination.empty())
            return rareAdded
                ? Result{rareAdded, DoomshotItemId, Status::AddedSelectedAmmo, rareAdded}
                : Result{0, chosen.itemId, Status::NoBagSpace};

        // Only the command explicitly grants items; no timers or per-tick
        // restock. Do not change PLAYER_AMMO_ID or ammo bag/equipment.
        bot->AddItem(chosen.itemId, needed);
        uint32_t const after = bot->GetItemCount(chosen.itemId, false);
        uint32_t const added = ObservedAdded(before, after, needed);

        if (!added)
            return rareAdded
                ? Result{rareAdded, DoomshotItemId, Status::AddedSelectedAmmo, rareAdded}
                : Result{0, chosen.itemId, Status::NoBagSpace};

        // A legal vendor fallback is NOT the selected ammo when a rare
        // projectile (e.g. Doomshot) is still selected. Report it as
        // needing manual selection when the preferred stock runs out.
        return {added + rareAdded, chosen.itemId,
                chosen.decision == Decision::VendorFallback
                    ? Status::AddedVendorAmmoNeedsSelection
                    : Status::AddedSelectedAmmo,
                rareAdded};
    }
}
