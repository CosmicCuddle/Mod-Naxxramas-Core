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
    // Selecting a quest/crafted item is not proof it may be duplicated.
    assert(ChooseAmmo(2, 18042, 60).itemId == 11285);
    assert(ChooseAmmo(3, 15997, 60).itemId == 11284);
    assert(ChooseAmmo(2, 18042, 60).decision == Decision::VendorFallback);
    assert(ChooseAmmo(3, 15997, 60).decision == Decision::VendorFallback);
    // Separate deliberate enablement is required for this premium source.
    assert(ChooseAmmo(2, 18042, 60, true).itemId == 18042);
    assert(ChooseAmmo(3, 15997, 60, true).itemId == 15997);

    // An unsupplyable selection is preserved; compatible vendor backup is supplied.
    assert(ChooseAmmo(3, 11285, 60).itemId == 11284);
    assert(ChooseAmmo(2, 11284, 60).itemId == 11285);
    assert(ChooseAmmo(2, 19316, 60).itemId == 11285); // AV/reputation
    assert(ChooseAmmo(2, 12654, 60).itemId == 11285); // Doomshot backup
    assert(ChooseAmmo(3, 15997, 51).itemId == 11284);
    assert(ChooseAmmo(2, 18042, 51).itemId == 11285);

    assert(ChooseAmmo(18, 12654, 25).itemId == 3030); // lower-level fallback
    assert(ChooseAmmo(2, 12654, 0).itemId == 0); // no legal ammo
    assert(ChooseAmmo(3, 12654, 60).itemId == 11284); // gun never receives arrows
    assert(ChooseAmmo(18, 11285, 60).decision == Decision::Selected);
    assert(ChooseAmmo(3, 11284, 60).decision == Decision::Selected);
    assert(ChooseAmmo(2, 18042, 60, true).decision == Decision::Selected);

    // Real quiver layout: each equipped slot has a 200-arrow logical
    // ceiling even when the server item_template allows a bigger stack.
    assert(QuiverSlotTarget(200) == 200);
    assert(QuiverSlotTarget(1000) == 200);
    assert(QuiverSlotTarget(120) == 120);
    assert(QuiverSlotTarget(0) == 0);
    assert(MoltenCoreQuiverSlotCount == 16);
    assert(MoltenCoreQuiverSlotCount * MoltenCoreQuiverSlotTarget == 3200);

    // Owner-approved rare allocation is a separate, default-DENY permission.
    assert(DoomshotAllocationTarget(600, 12654, 18, 60, 100, false) == 0);
    assert(DoomshotAllocationTarget(600, 12654, 18, 60, 100, true) == 200);
    assert(DoomshotAllocationTarget(600, 12654, 2, 54, 1, true) == 200);
    assert(DoomshotAllocationTarget(150, 12654, 18, 60, 100, true) == 150);
    assert(DoomshotAllocationTarget(600, 12654, 18, 53, 100, true) == 0);
    assert(DoomshotAllocationTarget(600, 12654, 3, 60, 100, true) == 0);
    assert(DoomshotAllocationTarget(600, 12654, 18, 60, 0, true) == 0);
    assert(DoomshotAllocationTarget(600, 18042, 18, 60, 100, true) == 0);
    assert(Shortfall(100, DoomshotRareAllocation) == 100);
    assert(Shortfall(200, DoomshotRareAllocation) == 0);
    // 200 rare + 400 vendor = 600; no extra rare or fallback over target.
    assert(TargetCount(600, 0) - DoomshotRareAllocation == 400);
    assert(ChooseAmmo(18, 12654, 60).itemId == 11285);

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

    // Repeated preparation never adds when already at/above target.
    assert(TargetCount(600, 0) == 600);
    assert(TargetCount(600, -1) == 600);
    assert(TargetCount(-3, 0) == 1);
    assert(TargetCount(0, 0) == 1);
    assert(TargetCount(2000, 0) == 1000);
    assert(TargetCount(2000, 200) == 200);
    assert(TargetCount(600, 20) == 20);
    assert(Shortfall(0, 600) == 600);
    assert(Shortfall(599, 600) == 1);
    assert(Shortfall(600, 600) == 0);
    assert(Shortfall(800, 600) == 0);
    // Report what was really stored, including unexpected partial writes.
    assert(ObservedAdded(0, 600, 600) == 600);
    assert(ObservedAdded(0, 250, 600) == 250);
    assert(ObservedAdded(599, 600, 1) == 1);
    assert(ObservedAdded(400, 400, 200) == 0);
    assert(ObservedAdded(400, 350, 200) == 0);
    assert(ObservedAdded(400, 900, 200) == 200);

    std::cout << "PASS: Hunter ammunition selection is type/level/source bounded\n";
    return 0;
}
