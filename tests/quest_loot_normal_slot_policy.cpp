// Native behavioural contract: A04 hidden ordinary slot (source candidate).
// g++ -std=c++17 -Wall -Wextra -Werror -pedantic -Isrc/Systems
//     tests/quest_loot_normal_slot_policy.cpp -o /tmp/naxx-a04 && /tmp/naxx-a04
#include "QuestLootNormalSlotPolicy.h"
#include <cstdio>
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
    std::printf("A04 normal-slot policy: %s (%d failure(s))\n",
        failed ? "FAILED" : "OK", failed);
    return failed ? 1 : 0;
}
