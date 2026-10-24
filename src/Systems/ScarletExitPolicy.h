/*
 * Naxxramas Core - Scarlet Monastery exit policy (F12).
 *
 * Dependency-free decision and geometry rules for the Cathedral (604) and
 * Armory (606) exits, so they can be unit-tested without the server.
 * ScarletMonasteryExits.cpp gathers the live facts and calls these.
 * Design: docs/SCARLET-MONASTERY-EXITS.md.
 */

#ifndef NAXXRAMAS_CORE_SCARLET_EXIT_POLICY_H
#define NAXXRAMAS_CORE_SCARLET_EXIT_POLICY_H

#include <cmath>
#include <cstddef>
#include <cstdint>

namespace NaxxramasScarletExitPolicy
{
    constexpr uint32_t EXIT_MAP = 0;
    constexpr float SAFETY_MARGIN = 1.0f;
    constexpr double PI = 3.14159265358979323846;

    struct Point
    {
        float X = 0.0f;
        float Y = 0.0f;
        float Z = 0.0f;
        float O = 0.0f;
    };

    struct DoorTarget
    {
        uint32_t ExitTrigger;
        uint32_t EntranceTrigger;
        Point Where;
    };

    // Vanilla-core reference rows (MaNGOS Zero database 325948a,
    // cMaNGOS classic-db 4e3d118). Used only after TargetIsSafe().
    constexpr DoorTarget DOOR_TARGETS[] =
    {
        { 604, 610, { 2915.13f, -823.637f, 160.327f, 3.49066f } },
        { 606, 612, { 2885.96f, -835.802f, 160.327f, 0.349066f } },
    };

    // Outdoor Scarlet Monastery entrances on map 0.
    constexpr uint32_t SM_ENTRANCES[] = { 45, 610, 612, 614 };

    inline DoorTarget const* FindDoorTarget(uint32_t exitTrigger)
    {
        for (DoorTarget const& target : DOOR_TARGETS)
            if (target.ExitTrigger == exitTrigger)
                return &target;
        return nullptr;
    }

    // Mirrors the fields of AzerothCore's AreaTrigger that matter here.
    struct TriggerShape
    {
        bool Present = false;
        uint32_t Map = 0;
        float X = 0.0f;
        float Y = 0.0f;
        float Z = 0.0f;
        float Radius = 0.0f;
        float Length = 0.0f;
        float Width = 0.0f;
        float Height = 0.0f;
        float Orientation = 0.0f;
    };

    inline float Distance(Point const& p, TriggerShape const& t)
    {
        float const dx = p.X - t.X;
        float const dy = p.Y - t.Y;
        float const dz = p.Z - t.Z;
        return std::sqrt(dx * dx + dy * dy + dz * dz);
    }

    // Same test as Player::IsInAreaTriggerRadius: a 3D sphere when the
    // radius is set, otherwise Position::IsWithinBox (Position.cpp L118-140),
    // each widened by `margin`.
    inline bool InsideTrigger(Point const& p, TriggerShape const& t, float margin)
    {
        if (t.Radius > 0.0f)
            return Distance(p, t) <= t.Radius + margin;

        double const rotation = 2 * PI - t.Orientation;
        double const sinVal = std::sin(rotation);
        double const cosVal = std::cos(rotation);
        float const boxDistX = p.X - t.X;
        float const boxDistY = p.Y - t.Y;
        float const dx = float(boxDistX * cosVal - boxDistY * sinVal);
        float const dy = float(boxDistY * cosVal + boxDistX * sinVal);
        float const dz = p.Z - t.Z;
        return std::fabs(dx) <= t.Length / 2 + margin &&
            std::fabs(dy) <= t.Width / 2 + margin &&
            std::fabs(dz) <= t.Height / 2 + margin;
    }

    // The built-in point is trusted only if the live entrance rows confirm
    // it lands outside its own door (no bounce back in), outside every other
    // SM entrance, and nearer its own door than any other (no wing swap).
    // Every entrance row is a required witness: if any is missing or not on
    // map 0, the point is not trusted (callers fall back to the live row or
    // stock; nothing is invented).
    inline bool TargetIsSafe(Point const& target, TriggerShape const& own,
        TriggerShape const* others, std::size_t otherCount)
    {
        if (!own.Present || own.Map != EXIT_MAP ||
            InsideTrigger(target, own, SAFETY_MARGIN))
            return false;

        float const ownDistance = Distance(target, own);
        for (std::size_t i = 0; i < otherCount; ++i)
        {
            TriggerShape const& other = others[i];
            if (!other.Present || other.Map != EXIT_MAP)
                return false;

            if (InsideTrigger(target, other, SAFETY_MARGIN) ||
                Distance(target, other) <= ownDistance)
                return false;
        }

        return true;
    }

    // Everything the decision needs, gathered by the server script.
    struct Facts
    {
        bool Enabled = false;
        bool HandledTrigger = false;     // 604 or 606
        bool InFlight = false;
        bool DebugAreaTriggers = false;  // GM .debug areatriggers
        bool TriggerKnown = false;
        bool Tavern = false;
        bool InRadius = false;
        bool BoundScript = false;
        bool QuestTrigger = false;
        bool BattlegroundActive = false;
        bool OutdoorPvP = false;
        bool RowExists = false;
        uint32_t RowMap = 0;
        bool AlreadyOnExitMap = false;
        bool EntryDenied = false;
        bool DungeonFinderExit = false;  // LFG group inside a dungeon
        bool RouteDungeonFinderExits = true;
        bool UseDoorTargets = true;
        bool DoorTargetSafe = false;
    };

    enum class Route
    {
        Stock,       // leave everything to the core handler
        DoorTarget,  // module teleports to the validated door target
        LiveRow,     // module teleports to the live areatrigger_teleport row
    };

    inline Route Decide(Facts const& f)
    {
        if (!f.Enabled || !f.HandledTrigger)
            return Route::Stock;

        // Native early exits and other handlers keep the stock path.
        if (f.InFlight || f.DebugAreaTriggers || !f.TriggerKnown ||
            f.Tavern || !f.InRadius || f.BoundScript || f.QuestTrigger ||
            f.BattlegroundActive || f.OutdoorPvP || !f.RowExists ||
            f.RowMap != EXIT_MAP || f.AlreadyOnExitMap || f.EntryDenied)
            return Route::Stock;

        bool const useDoor = f.UseDoorTargets && f.DoorTargetSafe;
        if (f.DungeonFinderExit)
        {
            if (!f.RouteDungeonFinderExits)
                return Route::Stock;
        }
        else if (!useDoor)
        {
            // A normal exit to the live row is exactly what stock does.
            return Route::Stock;
        }

        return useDoor ? Route::DoorTarget : Route::LiveRow;
    }
}

#endif
