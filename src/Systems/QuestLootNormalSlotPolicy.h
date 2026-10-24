/*
 * A04 candidate: stock-compatible hidden ordinary-loot slot check.
 *
 * This intentionally does not decide whether a quest-related item belongs
 * to a specific player. Only guards an ordinary loot slot that the pinned
 * AzerothCore loot-view rules would hide from the requesting turn non-holder.
 * No inventory or loot-container mutation is performed by this policy.
 *
 * Strictly review-only until independent source, native and full Worldserver
 * verification; no proof this is the owner's reported pickup.
 */
#ifndef NAXXRAMAS_CORE_QUEST_LOOT_NORMAL_SLOT_POLICY_H
#define NAXXRAMAS_CORE_QUEST_LOOT_NORMAL_SLOT_POLICY_H

namespace NaxxramasQuestLootNormalSlotPolicy
{
    enum class GroupMethod
    {
        Other,       // FREE_FOR_ALL, MASTER_LOOT, or unsupported
        RoundRobin,
        GroupLoot,
        NeedBeforeGreed
    };

    struct Facts
    {
        bool Enabled = false;
        GroupMethod Method = GroupMethod::Other;
        bool HasActiveTurn = false;
        bool RequesterHoldsTurn = false;
        bool OwnerPresentInSameGroupAndMap = false;
        bool OrdinarySlotExists = false;
        bool IsLooted = false;
        bool IsFreeForAllItem = false;
        bool HasConditions = false;
        bool IsBlocked = false;
        bool HasRollWinner = false;
        bool IsUnderThreshold = false;
        bool FollowsSpecialLootRules = false;
    };

    // True means that the normal client loot view would not show this
    // unblocked ordinary slot to the requesting member with an active owner.
    // Item eligibility, inventory capacity, source range, quest slots, FFA,
    // rolls, master loot, and any other rule remain native AzerothCore's job.
    inline bool RejectHiddenOrdinarySlot(Facts const& f)
    {
        if (!f.Enabled || !f.HasActiveTurn || f.RequesterHoldsTurn ||
            !f.OwnerPresentInSameGroupAndMap || !f.OrdinarySlotExists ||
            f.IsLooted || f.IsFreeForAllItem || f.HasConditions ||
            f.IsBlocked || f.HasRollWinner || f.FollowsSpecialLootRules)
            return false;

        if (f.Method == GroupMethod::RoundRobin)
            return true;

        if (f.Method == GroupMethod::GroupLoot ||
            f.Method == GroupMethod::NeedBeforeGreed)
            return f.IsUnderThreshold;

        return false;
    }
}

#endif
