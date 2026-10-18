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
    // Crafted Thorium ammunition may be topped up ONLY if already selected;
    // it is never minted as a fallback for an unselected Hunter.
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

    constexpr uint32_t ProjectileForWeapon(uint32_t weaponSubclass)
    {
        return weaponSubclass == 2 || weaponSubclass == 18 ? 2 :
               weaponSubclass == 3 ? 3 : 0;
    }

    inline Selection ChooseAmmo(uint32_t weaponSubclass,
                                uint32_t selectedAmmoId,
                                uint32_t effectiveLevel)
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
