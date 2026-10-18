#ifndef NAXXRAMAS_CORE_HUNTER_AMMO_SELECTION_H
#define NAXXRAMAS_CORE_HUNTER_AMMO_SELECTION_H

#include <cstdint>

// Research-only selection policy for an opt-in Bot Consumables feature.
// The live C++ caller STILL validates item_template, ranged weapon durability,
// actual ammo compatibility, effective IP/dungeon cap and inventory capacity.
// Numeric subclasses here are from pinned AzerothCore ItemTemplate.h:
// bow 2, gun 3, crossbow 18; projectile arrow 2, bullet 3.
namespace NaxxramasHunterAmmo
{
    enum class Decision : uint8_t
    {
        Selected,
        VendorFallback,
        UnsupportedWeapon,
        UnsupportedSelectedAmmo,
        LevelTooLow
    };

    struct Selection
    {
        uint32_t itemId = 0;
        uint32_t projectileSubclass = 0;
        Decision decision = Decision::UnsupportedWeapon;
    };

    struct KnownAmmo
    {
        uint32_t itemId;
        uint32_t projectileSubclass;
        uint32_t requiredLevel;
        bool vendorFallback;
    };

    // Conservative Classic catalog, not the entire WotLK item database.
    // Quest-exchanged / engineered Thorium ammunition is never a vendor
    // fallback and is only replenished when already selected AND a separate
    // default-DENY owner configuration explicitly permits duplication.
    constexpr KnownAmmo Catalog[] =
    {
        {2512, 2, 1, true},    // Rough Arrow
        {2515, 2, 10, true},   // Sharp Arrow
        {3030, 2, 25, true},   // Razor Arrow
        {11285, 2, 40, true}, // Jagged Arrow
        {18042, 2, 52, false},// Thorium Headed Arrow, selected-only
        {2516, 3, 1, true},    // Light Shot
        {2519, 3, 10, true},   // Heavy Shot
        {3033, 3, 25, true},   // Solid Shot
        {11284, 3, 40, true}, // Accurate Slugs
        {15997, 3, 52, false} // Thorium Shells, selected-only
    };

    // Pure arithmetic policy for repeatable, inventory-safe top-ups.
    // maxCount <= 0 means unlimited in the item template, NOT unlimited
    // supply; the separately configured 1..1000 hard ceiling still applies.
    constexpr uint32_t TargetCount(int32_t configuredTarget, int32_t maxCount)
    {
        uint32_t bounded = configuredTarget < 1 ? 1u :
            configuredTarget > 1000 ? 1000u :
            static_cast<uint32_t>(configuredTarget);

        if (maxCount > 0 && static_cast<uint32_t>(maxCount) < bounded)
            bounded = static_cast<uint32_t>(maxCount);

        return bounded;
    }

    constexpr uint32_t Shortfall(uint32_t current, uint32_t target)
    {
        return current < target ? target - current : 0u;
    }

    // Core AddItem may store fewer pieces than requested if anything goes
    // wrong, so account for actual observed change, never assumed success.
    constexpr uint32_t ObservedAdded(uint32_t before, uint32_t after,
                                     uint32_t attempted)
    {
        uint32_t const delta = after > before ? after - before : 0u;
        return delta < attempted ? delta : attempted;
    }

    constexpr uint32_t ProjectileForWeapon(uint32_t weaponSubclass)
    {
        return weaponSubclass == 2 || weaponSubclass == 18 ? 2 :
               weaponSubclass == 3 ? 3 : 0;
    }

    inline Selection ChooseAmmo(uint32_t weaponSubclass,
                                uint32_t selectedAmmoId,
                                uint32_t effectiveLevel,
                                bool allowSelectedNonVendor = false)
    {
        uint32_t const wanted = ProjectileForWeapon(weaponSubclass);
        if (!wanted)
            return {0, 0, Decision::UnsupportedWeapon};

        if (selectedAmmoId)
        {
            for (KnownAmmo const& item : Catalog)
            {
                if (item.itemId != selectedAmmoId)
                    continue;

                if (item.projectileSubclass != wanted)
                    return {0, wanted, Decision::UnsupportedSelectedAmmo};

                if (item.requiredLevel > effectiveLevel)
                    return {0, wanted, Decision::LevelTooLow};

                // Important for Individual Progression: a Hunter could have
                // acquired a quest-reward or engineered ammo stack legitimately.
                // Merely selecting it is NOT permission to mint extra copies.
                // Operator must explicitly allow those inventory top-ups.
                if (!item.vendorFallback && !allowSelectedNonVendor)
                    return {0, wanted, Decision::UnsupportedSelectedAmmo};

                return {item.itemId, wanted, Decision::Selected};
            }

            // Do not silently replace an unusual/quest/PvP/high-era selected
            // projectile with something weaker or create that item for free.
            return {0, wanted, Decision::UnsupportedSelectedAmmo};
        }

        // No current ammo selection: give only a level-appropriate vendor
        // fallback to inventory. Caller NEVER auto-selects/equips it.
        Selection best{0, wanted, Decision::LevelTooLow};
        for (KnownAmmo const& item : Catalog)
        {
            if (item.vendorFallback &&
                item.projectileSubclass == wanted &&
                item.requiredLevel <= effectiveLevel)
            {
                best = {item.itemId, wanted, Decision::VendorFallback};
            }
        }
        return best;
    }
}
#endif // NAXXRAMAS_CORE_HUNTER_AMMO_SELECTION_H
