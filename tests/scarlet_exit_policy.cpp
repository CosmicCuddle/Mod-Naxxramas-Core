// Native tests for src/Systems/ScarletExitPolicy.h (F12).
// Build: g++ -std=c++17 -Wall -Wextra -Werror -pedantic -Isrc/Systems
//        tests/scarlet_exit_policy.cpp -o /tmp/scarlet && /tmp/scarlet
#include "ScarletExitPolicy.h"

#include <cstdio>
#include <initializer_list>

using namespace NaxxramasScarletExitPolicy;

namespace
{
    int failures = 0;

    void Check(bool ok, char const* what)
    {
        if (!ok)
        {
            ++failures;
            std::printf("FAIL: %s\n", what);
        }
    }

    // Baseline outdoor entrances (areatrigger.sql L45, L130-L132).
    TriggerShape Sphere(float x, float y, float z, float r)
    {
        TriggerShape t;
        t.Present = true;
        t.Map = 0;
        t.X = x; t.Y = y; t.Z = z; t.Radius = r;
        return t;
    }

    TriggerShape const GRAVEYARD = Sphere(2924.38f, -798.429f, 161.611f, 8.0f);
    TriggerShape const CATHEDRAL = Sphere(2925.18f, -820.545f, 161.634f, 8.0f);
    TriggerShape const ARMORY = Sphere(2877.98f, -839.267f, 163.049f, 6.0f);
    TriggerShape const LIBRARY = Sphere(2859.73f, -824.91f, 162.083f, 8.0f);

    bool Safe(uint32_t exit, Point const& p)
    {
        DoorTarget const* door = FindDoorTarget(exit);
        TriggerShape const own = door->EntranceTrigger == 610 ? CATHEDRAL : ARMORY;
        TriggerShape const others[] = {
            GRAVEYARD, LIBRARY, door->EntranceTrigger == 610 ? ARMORY : CATHEDRAL };
        return TargetIsSafe(p, own, others, 3);
    }

    Facts Eligible()
    {
        Facts f;
        f.Enabled = true;
        f.HandledTrigger = true;
        f.TriggerKnown = true;
        f.InRadius = true;
        f.RowExists = true;
        f.RowMap = 0;
        f.UseDoorTargets = true;
        f.DoorTargetSafe = true;
        f.RouteDungeonFinderExits = true;
        return f;
    }
}

int main()
{
    // --- Door table ---
    Check(FindDoorTarget(604) && FindDoorTarget(604)->EntranceTrigger == 610, "604 -> 610");
    Check(FindDoorTarget(606) && FindDoorTarget(606)->EntranceTrigger == 612, "606 -> 612");
    for (uint32_t other : { 45u, 602u, 608u, 610u, 612u, 614u, 4436u, 0u })
        Check(FindDoorTarget(other) == nullptr, "only 604/606 have door targets");

    // --- Geometry ---
    Check(Safe(604, FindDoorTarget(604)->Where), "Cathedral target is safe");
    Check(Safe(606, FindDoorTarget(606)->Where), "Armory target is safe");
    Check(!Safe(604, FindDoorTarget(606)->Where), "Armory point rejected for Cathedral");
    Check(!Safe(606, FindDoorTarget(604)->Where), "Cathedral point rejected for Armory");
    Check(!Safe(604, { 2927.0f, -820.5f, 161.6f, 0.0f }), "point inside own entrance rejected");
    Check(!Safe(604, { 2933.0f, -820.5f, 161.6f, 0.0f }), "point within margin of own entrance rejected");

    {
        TriggerShape missing;
        Check(!TargetIsSafe(FindDoorTarget(604)->Where, missing, nullptr, 0),
            "missing own entrance fails closed");
        TriggerShape wrongMap = CATHEDRAL;
        wrongMap.Map = 189;
        Check(!TargetIsSafe(FindDoorTarget(604)->Where, wrongMap, nullptr, 0),
            "own entrance on wrong map fails closed");
    }

    // Every other entrance is a required witness (CS01 #125 review).
    {
        Point const cathedral = FindDoorTarget(604)->Where;
        TriggerShape const all[] = { GRAVEYARD, LIBRARY, ARMORY };
        Check(TargetIsSafe(cathedral, CATHEDRAL, all, 3), "all witnesses present -> safe");
        for (int i = 0; i < 3; ++i)
        {
            TriggerShape missing[] = { GRAVEYARD, LIBRARY, ARMORY };
            missing[i] = TriggerShape();
            Check(!TargetIsSafe(cathedral, CATHEDRAL, missing, 3),
                "missing other entrance fails closed");

            TriggerShape wrong[] = { GRAVEYARD, LIBRARY, ARMORY };
            wrong[i].Map = 189;
            Check(!TargetIsSafe(cathedral, CATHEDRAL, wrong, 3),
                "other entrance on wrong map fails closed");
        }
        // Swapped-wing falsifier: the Armory point judged as the Cathedral's.
        Check(!TargetIsSafe(FindDoorTarget(606)->Where, CATHEDRAL, all, 3),
            "Armory point with Cathedral as own entrance is rejected");
    }

    // Box trigger: Karazhan outdoor entrance 4131 (areatrigger.sql L453).
    {
        TriggerShape box;
        box.Present = true;
        box.X = -11101.9f; box.Y = -1998.12f; box.Z = 49.3307f;
        box.Length = 20.08f; box.Width = 13.83f; box.Height = 14.69f;
        box.Orientation = 0.6981f;
        Check(InsideTrigger({ -11100.0f, -2001.64f, 49.8927f, 0.0f }, box, 0.0f),
            "box: point near centre is inside");
        Check(!InsideTrigger({ -11112.9f, -2005.89f, 49.3307f, 0.0f }, box, 0.0f),
            "box: Karazhan exit landing is outside");
    }

    // --- Decision ---
    Check(Decide(Eligible()) == Route::DoorTarget, "S07 normal exit -> door");
    {
        Facts f = Eligible(); f.Enabled = false;
        Check(Decide(f) == Route::Stock, "S01 flag off");
        f = Eligible(); f.HandledTrigger = false;
        Check(Decide(f) == Route::Stock, "S02 other trigger");
    }
    {
        bool Facts::* flags[] = { &Facts::InFlight, &Facts::DebugAreaTriggers,
            &Facts::Tavern, &Facts::BoundScript, &Facts::QuestTrigger,
            &Facts::BattlegroundActive, &Facts::OutdoorPvP,
            &Facts::AlreadyOnExitMap, &Facts::EntryDenied };
        for (auto flag : flags)
        {
            Facts f = Eligible(); f.*flag = true;
            Check(Decide(f) == Route::Stock, "S03-S06 native early exit stays stock");
            f.DungeonFinderExit = true;
            Check(Decide(f) == Route::Stock, "S03-S06 early exit stays stock for LFG too");
        }
        bool Facts::* required[] = { &Facts::TriggerKnown, &Facts::InRadius, &Facts::RowExists };
        for (auto flag : required)
        {
            Facts f = Eligible(); f.*flag = false;
            Check(Decide(f) == Route::Stock, "S03/S06 missing requirement stays stock");
        }
        Facts f = Eligible(); f.RowMap = 189;
        Check(Decide(f) == Route::Stock, "S06 row on another map stays stock");
    }
    {
        Facts f = Eligible(); f.UseDoorTargets = false;
        Check(Decide(f) == Route::Stock, "S08 normal exit, door targets off");
        f = Eligible(); f.DoorTargetSafe = false;
        Check(Decide(f) == Route::Stock, "S12 normal exit, unsafe target -> stock");
    }
    {
        Facts f = Eligible(); f.DungeonFinderExit = true;
        Check(Decide(f) == Route::DoorTarget, "S09 LFG -> door");
        f.UseDoorTargets = false;
        Check(Decide(f) == Route::LiveRow, "S09b LFG, targets off -> live row");
        f = Eligible(); f.DungeonFinderExit = true; f.DoorTargetSafe = false;
        Check(Decide(f) == Route::LiveRow, "S12 LFG, unsafe target -> live row");
        f = Eligible(); f.DungeonFinderExit = true; f.RouteDungeonFinderExits = false;
        Check(Decide(f) == Route::Stock, "S10 LFG routing off -> stock");
    }

    if (failures)
    {
        std::printf("%d failure(s)\n", failures);
        return 1;
    }

    std::printf("OK (0 failures)\n");
    return 0;
}
