#include "HunterAmmoSelection.h"
#include <cassert>
#include <iostream>

using namespace NaxxramasHunterAmmo;

int main()
{
    // Weapon type, WotLK subclass constants, and Vanilla stage caps.
    assert(ProjectileForWeapon(2) == 2);   // bow
    assert(ProjectileForWeapon(18) == 2);  // crossbow
    assert(ProjectileForWeapon(3) == 3);   // gun
    assert(ProjectileForWeapon(16) == 0);  // thrown
    assert(ProjectileForWeapon(19) == 0);  // wand
    assert(ProjectileForWeapon(0) == 0);

    assert(ChooseAmmo(2, 11285, 60).itemId == 11285);
    assert(ChooseAmmo(18, 11285, 60).itemId == 11285);
    assert(ChooseAmmo(3, 11284, 60).itemId == 11284);
    assert(ChooseAmmo(2, 18042, 60).itemId == 18042);
    assert(ChooseAmmo(3, 15997, 60).itemId == 15997);

    // Selected ammo is never substituted on a mismatch or unsupported ID.
    assert(ChooseAmmo(3, 11285, 60).decision ==
           Decision::UnsupportedSelectedAmmo);
    assert(ChooseAmmo(2, 11284, 60).itemId == 0);
    assert(ChooseAmmo(2, 19316, 60).itemId == 0); // AV/reputation
    assert(ChooseAmmo(2, 12654, 60).itemId == 0); // quest / unknown
    assert(ChooseAmmo(3, 15997, 51).decision == Decision::LevelTooLow);
    assert(ChooseAmmo(2, 18042, 51).itemId == 0);

    // No selected ammo: conservative level-appropriate VENDOR pairs only.
    assert(ChooseAmmo(2, 0, 1).itemId == 2512);
    assert(ChooseAmmo(3, 0, 1).itemId == 2516);
    assert(ChooseAmmo(2, 0, 10).itemId == 2515);
    assert(ChooseAmmo(3, 0, 10).itemId == 2519);
    assert(ChooseAmmo(2, 0, 25).itemId == 3030);
    assert(ChooseAmmo(3, 0, 25).itemId == 3033);
    assert(ChooseAmmo(18, 0, 40).itemId == 11285);
    assert(ChooseAmmo(3, 0, 40).itemId == 11284);
    assert(ChooseAmmo(2, 0, 60).itemId == 11285); // not quest Thorium
    assert(ChooseAmmo(3, 0, 60).itemId == 11284);
    assert(ChooseAmmo(2, 0, 60).decision == Decision::VendorFallback);
    assert(ChooseAmmo(2, 0, 0).itemId == 0);
    assert(ChooseAmmo(19, 0, 60).itemId == 0);

    std::cout << "PASS: Hunter ammunition selection is type/level/source bounded\n";
    return 0;
}
