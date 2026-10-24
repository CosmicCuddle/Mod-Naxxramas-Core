// Native behavioural contract: A04 hidden ordinary slot (source candidate).
// g++ -std=c++17 -Wall -Wextra -Werror -pedantic -Isrc/Systems
//     tests/quest_loot_normal_slot_policy.cpp -o /tmp/naxx-a04 && /tmp/naxx-a04
#include "QuestLootNormalSlotPolicy.h"
#include <array>
#include <cstdio>
#include <initializer_list>
using namespace NaxxramasQuestLootNormalSlotPolicy;

namespace
{
    int failed = 0;
    void Check(bool condition, char const* name)
    {
        if (!condition)
        {
            std::printf("FAIL: %s\n", name);
            ++failed;
        }
    }

    Facts Active(GroupMethod method)
    {
        Facts f;
        f.Enabled = true;
        f.Method = method;
        f.HasActiveTurn = true;
        f.RequesterHoldsTurn = false;
        f.OwnerPresentInSameGroupAndMap = true;
        f.OrdinarySlotExists = true;
        return f;
    }
}

int main()
{
    Check(!RejectHiddenOrdinarySlot(Facts()), "all defaults leave native path");
    Facts f = Active(GroupMethod::RoundRobin);
    Check(RejectHiddenOrdinarySlot(f), "RR hidden ordinary slot denied");
    f = Active(GroupMethod::GroupLoot); f.IsUnderThreshold = true;
    Check(RejectHiddenOrdinarySlot(f), "Group Loot underthreshold hidden slot denied");
    f = Active(GroupMethod::NeedBeforeGreed); f.IsUnderThreshold = true;
    Check(RejectHiddenOrdinarySlot(f), "NBG underthreshold hidden slot denied");
    for (GroupMethod mode : { GroupMethod::GroupLoot, GroupMethod::NeedBeforeGreed })
    {
        f = Active(mode); f.IsUnderThreshold = false;
        Check(!RejectHiddenOrdinarySlot(f), "above threshold visible; leave native");
    }
    f = Active(GroupMethod::Other);
    Check(!RejectHiddenOrdinarySlot(f), "FFA/master native unchanged");
    f = Active(GroupMethod::RoundRobin); f.Enabled = false;
    Check(!RejectHiddenOrdinarySlot(f), "off switch no effect");
    f = Active(GroupMethod::RoundRobin); f.RequesterHoldsTurn = true;
    Check(!RejectHiddenOrdinarySlot(f), "real turn-holder allowed");
    f = Active(GroupMethod::RoundRobin); f.HasActiveTurn = false;
    Check(!RejectHiddenOrdinarySlot(f), "released turn allowed");
    f = Active(GroupMethod::RoundRobin); f.OwnerPresentInSameGroupAndMap = false;
    Check(!RejectHiddenOrdinarySlot(f), "absent or detached owner fail open");
    f = Active(GroupMethod::RoundRobin); f.OrdinarySlotExists = false;
    Check(!RejectHiddenOrdinarySlot(f), "out-of-range slot native");
    f = Active(GroupMethod::RoundRobin); f.IsLooted = true;
    Check(!RejectHiddenOrdinarySlot(f), "already looted item native");
    f = Active(GroupMethod::RoundRobin); f.IsFreeForAllItem = true;
    Check(!RejectHiddenOrdinarySlot(f), "personal multi-drop untouched");
    f = Active(GroupMethod::RoundRobin); f.HasConditions = true;
    Check(!RejectHiddenOrdinarySlot(f), "conditional loot untouched");
    f = Active(GroupMethod::RoundRobin); f.IsBlocked = true;
    Check(!RejectHiddenOrdinarySlot(f), "roll blocked untouched");
    f = Active(GroupMethod::RoundRobin); f.HasRollWinner = true;
    Check(!RejectHiddenOrdinarySlot(f), "roll winner native");
    f = Active(GroupMethod::RoundRobin); f.FollowsSpecialLootRules = true;
    Check(!RejectHiddenOrdinarySlot(f), "special follow-loot-rules native");
    // Exhaustive small-state witness: 4 permission-mode mappings * 4096
    // flag combinations. Expected behaviour is derived independently from
    // pinned LootView permission branches: stock-visible normal slots are
    // NEVER rejected by this module's narrow ordinary-slot pilot.
    // This is a PURE POLICY MODEL, not a worldserver / packet gameplay test.
    constexpr std::array<GroupMethod, 4> modes = {
        GroupMethod::Other, GroupMethod::RoundRobin,
        GroupMethod::GroupLoot, GroupMethod::NeedBeforeGreed
    };
    unsigned long total = 0;
    int matrixMismatches = 0;
    for (GroupMethod mode : modes)
    {
        for (unsigned flags = 0; flags != 4096; ++flags)
        {
            Facts sample;
            sample.Method = mode;
            sample.Enabled = (flags & (1u << 0)) != 0;
            sample.HasActiveTurn = (flags & (1u << 1)) != 0;
            sample.RequesterHoldsTurn = (flags & (1u << 2)) != 0;
            sample.OwnerPresentInSameGroupAndMap = (flags & (1u << 3)) != 0;
            sample.OrdinarySlotExists = (flags & (1u << 4)) != 0;
            sample.IsLooted = (flags & (1u << 5)) != 0;
            sample.IsFreeForAllItem = (flags & (1u << 6)) != 0;
            sample.HasConditions = (flags & (1u << 7)) != 0;
            sample.IsBlocked = (flags & (1u << 8)) != 0;
            sample.HasRollWinner = (flags & (1u << 9)) != 0;
            sample.IsUnderThreshold = (flags & (1u << 10)) != 0;
            sample.FollowsSpecialLootRules = (flags & (1u << 11)) != 0;

            // A normal eligible, unblocked slot is suppressed by stock
            // ROUND_ROBIN_PERMISSION for a different current holder.
            // GROUP_PERMISSION suppresses that slot only below threshold.
            // All other conditions are deliberate conservative fail-opens.
            bool const inWindowBranch =
                mode == GroupMethod::RoundRobin ||
                mode == GroupMethod::GroupLoot ||
                mode == GroupMethod::NeedBeforeGreed;
            bool const aRestrictedRow =
                !sample.IsLooted && !sample.IsFreeForAllItem &&
                !sample.HasConditions && !sample.IsBlocked &&
                !sample.HasRollWinner && !sample.FollowsSpecialLootRules;
            bool const stockWindowHides =
                sample.HasActiveTurn && !sample.RequesterHoldsTurn &&
                (mode == GroupMethod::RoundRobin ||
                    ((mode == GroupMethod::GroupLoot ||
                      mode == GroupMethod::NeedBeforeGreed) &&
                     sample.IsUnderThreshold));
            bool const expected =
                sample.Enabled && inWindowBranch && sample.OrdinarySlotExists &&
                sample.OwnerPresentInSameGroupAndMap && aRestrictedRow &&
                stockWindowHides;
            bool const actual = RejectHiddenOrdinarySlot(sample);
            if (actual != expected)
            {
                if (matrixMismatches < 5)
                    std::printf("MATRIX mismatch mode=%u flags=%u wanted=%d actual=%d\n",
                        static_cast<unsigned>(mode), flags, int(expected), int(actual));
                ++matrixMismatches;
            }
            ++total;
        }
    }
    Check(total == 16384, "all 16384 matrix cases executed");
    Check(matrixMismatches == 0, "native parity matrix matches pinned stock visibility witness");

    std::printf("A04 normal-slot policy: %s (%d failure(s))\n",
        failed ? "FAILED" : "OK", failed);
    return failed ? 1 : 0;
}
