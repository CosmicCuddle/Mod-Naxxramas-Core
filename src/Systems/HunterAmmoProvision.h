#ifndef NAXXRAMAS_CORE_HUNTER_AMMO_PROVISION_H
#define NAXXRAMAS_CORE_HUNTER_AMMO_PROVISION_H

#include <cstdint>

class Player;

namespace NaxxramasHunterAmmo
{
    enum class Status : uint8_t
    {
        Disabled,
        SkippedNotEligible,
        NoCompatibleRangedWeapon,
        UnsupportedSelection,
        ItemRejected,
        AlreadySupplied,
        NoBagSpace,
        AddedSelectedAmmo,
        AddedVendorAmmoNeedsSelection
    };

    struct Result
    {
        uint32_t added = 0;
        uint32_t itemId = 0;
        Status status = Status::Disabled;
    };

    // Only called by the already authenticated, cooldown-limited
    // Bot Consumables preparation command. NEVER a per-tick refill.
    Result TopUpHunterAmmo(Player* bot, uint32_t effectiveLevel);
}
#endif // NAXXRAMAS_CORE_HUNTER_AMMO_PROVISION_H
