// P4 quest loot view guard: old RED / new GREEN on the original pinned bodies.
//
// Reuses the #262 extracted-pinned-source harness unchanged (its main() is
// renamed by the macro below) and the module's real guard header
// src/Systems/QuestLootViewGuard.h. Every case runs on two fresh corpses:
//   base:  pinned behaviour (no guard), the T1/T2 witness must reproduce;
//   guard: the guard runs where Player::SendLoot calls OnPlayerBeforeSendLoot
//          (after the loot GUID is set, before the LootView is serialized).
// The guard must not change what any viewer sees, only the shared side effect.

#define main a04_baseline_main_unused
#include "../a04_native/harness.cpp"
#undef main

#include "QuestLootViewGuard.h"

static int g_guardRuns = 0;

// Player::SendLoot order: SetLootGUID, OnPlayerBeforeSendLoot, LootView, AddLooter.
static std::vector<Row> viewWith(Scene& s, Player& p, PermissionTypes perm, bool guard)
{
    if (guard)
    {
        p.lootGuid = s.corpse;
        g_guardRuns += int(NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(&p, s.loot));
    }
    return s.open(p, perm);
}

static bool sameRows(std::vector<Row> const& a, std::vector<Row> const& b)
{
    if (a.size() != b.size())
        return false;
    for (size_t i = 0; i < a.size(); ++i)
        if (a[i].slot != b[i].slot || a[i].item != b[i].item || a[i].slotType != b[i].slotType)
            return false;
    return true;
}

// ---- T1: A opens, banked B opens, A takes ----
static void gT1()
{
    std::vector<Row> rows[2][2];  // [guard][A,B]
    for (int guard = 0; guard < 2; ++guard)
    {
        Scene s;
        Scene::accept(s.A, Q_QUEST);
        bankedB(s);
        s.kill({rowQuestSeed()}, s.A);
        rows[guard][0] = viewWith(s, s.A, GROUP_PERMISSION, guard);
        rows[guard][1] = viewWith(s, s.B, GROUP_PERMISSION, guard);
        bool onlyOwnRow = s.ownQuestRowLooted(s.B) && !s.ownQuestRowLooted(s.A) && !s.q().is_looted;
        bool aGot = s.take(s.A, 0);
        if (!guard)
        {
            check("BASE.T1_RED_view_marks_shared_looted_A_denied",
                  s.q().is_looted && !aGot && s.loot.unlootedCount == 1 && !s.loot.isLooted());
            continue;
        }
        s.obs("GUARD.T1.after_A_take");
        check("GUARD.T1_B_view_marks_only_own_row_not_shared", onlyOwnRow);
        check("GUARD.T1_A_awarded_exactly_one", aGot && s.received(s.A, Q_ITEM) == 1 && s.objectiveDone(s.A, Q_QUEST, 1));
        check("GUARD.T1_corpse_settles", s.loot.unlootedCount == 0 && s.loot.isLooted() && s.q().is_looted);
        check("GUARD.T1_B_gets_nothing", s.received(s.B, Q_ITEM) == 0);
    }
    check("GUARD.T1_rows_identical_to_pinned", sameRows(rows[0][0], rows[1][0]) && sameRows(rows[0][1], rows[1][1]));
}

// ---- T2: banked B opens first, then A opens and takes ----
static void gT2()
{
    std::vector<Row> rows[2][2];
    for (int guard = 0; guard < 2; ++guard)
    {
        Scene s;
        Scene::accept(s.A, Q_QUEST);
        bankedB(s);
        s.kill({rowQuestSeed()}, s.A);
        rows[guard][1] = viewWith(s, s.B, GROUP_PERMISSION, guard);
        rows[guard][0] = viewWith(s, s.A, GROUP_PERMISSION, guard);
        bool aGot = s.take(s.A, 0);
        if (!guard)
        {
            check("BASE.T2_RED_A_sees_no_row_and_is_denied", rows[0][0].empty() && !aGot && s.q().is_looted);
            continue;
        }
        check("GUARD.T2_A_sees_allow_loot_row", oneRow(rows[1][0], Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
        check("GUARD.T2_A_awarded_and_corpse_settles",
              aGot && s.received(s.A, Q_ITEM) == 1 && s.objectiveDone(s.A, Q_QUEST, 1) && s.loot.isLooted());
        // After its own view, B cannot take the seed it no longer needs.
        s.B.lootGuid = s.corpse;
        check("GUARD.T2_B_after_view_cannot_take", !s.take(s.B, 0) && s.received(s.B, Q_ITEM) == 0);
    }
    check("GUARD.T2_B_rows_identical_to_pinned", sameRows(rows[0][1], rows[1][1]) && rows[1][1].empty());
}

// ---- T3: B retrieves the seed after the corpse filled (quest COMPLETE) ----
static void gT3()
{
    std::vector<Row> rows[2];
    for (int guard = 0; guard < 2; ++guard)
    {
        Scene s;
        Scene::accept(s.A, Q_QUEST);
        bankedB(s);
        s.kill({rowQuestSeed()}, s.A);
        Scene::bankToBag(s.B, Q_ITEM);
        rows[guard] = viewWith(s, s.B, GROUP_PERMISSION, guard);
        bool bGot = s.take(s.B, 0);
        viewWith(s, s.A, GROUP_PERMISSION, guard);
        bool aGot = s.take(s.A, 0);
        if (guard)
            check("GUARD.T3_locked_row_kept_B_denied_A_awarded",
                  oneRow(rows[1], Q_ITEM, LOOT_SLOT_TYPE_LOCKED) && !bGot && aGot && s.loot.isLooted());
    }
    // H2 shape is NOT changed by this guard (COMPLETE quest => showInLoot stays true).
    check("GUARD.T3_rows_identical_to_pinned", sameRows(rows[0], rows[1]));
}

// ---- T0 / T4: normal one-copy behaviour unchanged ----
static void gT0T4()
{
    for (int guard = 0; guard < 2; ++guard)
    {
        Scene s;
        Scene::accept(s.A, Q_QUEST);
        s.kill({rowQuestSeed()}, s.A);
        auto a = viewWith(s, s.A, GROUP_PERMISSION, guard);
        auto b = viewWith(s, s.B, GROUP_PERMISSION, guard);
        bool bGot = s.take(s.B, 0);
        bool aGot = s.take(s.A, 0);
        if (guard)
            check("GUARD.T0_unchanged", oneRow(a, Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT) && b.empty() && !bGot && aGot &&
                                        s.objectiveDone(s.A, Q_QUEST, 1) && s.loot.isLooted());
    }
    for (int bFirst = 0; bFirst < 2; ++bFirst)
    {
        Scene s;
        Scene::accept(s.A, Q_QUEST);
        Scene::accept(s.B, Q_QUEST);
        s.kill({rowQuestSeed()}, s.A);
        viewWith(s, s.A, GROUP_PERMISSION, true);
        viewWith(s, s.B, GROUP_PERMISSION, true);
        Player& first = bFirst ? s.B : s.A;
        Player& second = bFirst ? s.A : s.B;
        bool ok = s.take(first, 0) && !s.take(second, 0) && s.received(first, Q_ITEM) == 1 &&
                  s.objectiveDone(first, Q_QUEST, 1) && second.GetQuestStatus(Q_QUEST) == QUEST_STATUS_INCOMPLETE;
        check(bFirst ? "GUARD.T4b_first_taker_single_copy_unchanged" : "GUARD.T4a_first_taker_single_copy_unchanged", ok);
    }
}

// ---- Controls: FFA/MULTI_DROP, Master Loot, ordinary item, gold ----
static void gControls()
{
    {
        Scene s;  // MULTI_DROP: B banked, A needs; both views guarded
        Scene::accept(s.A, FFA_QUEST);
        Scene::accept(s.B, FFA_QUEST);
        Scene::gainToBags(s.B, FFA_ITEM);
        Scene::bagToBank(s.B, FFA_ITEM);
        s.kill({rowFfaClaw()}, s.A);
        auto b = viewWith(s, s.B, GROUP_PERMISSION, true);
        viewWith(s, s.A, GROUP_PERMISSION, true);
        check("GUARD.C1_ffa_banked_B_hidden_A_awarded",
              b.empty() && !s.q().is_looted && s.take(s.A, 0) && s.received(s.A, FFA_ITEM) == 1);
    }
    {
        Scene s;  // MULTI_DROP: both need, both get copies
        Scene::accept(s.A, FFA_QUEST);
        Scene::accept(s.B, FFA_QUEST);
        s.kill({rowFfaClaw()}, s.A);
        viewWith(s, s.A, GROUP_PERMISSION, true);
        viewWith(s, s.B, GROUP_PERMISSION, true);
        check("GUARD.C1_ffa_both_copies", s.take(s.A, 0) && s.take(s.B, 0) && s.loot.isLooted());
    }
    std::vector<Row> ml[2];
    for (int guard = 0; guard < 2; ++guard)
    {
        Scene s;  // Master Loot: B is master looter without the quest
        s.group.lootMethod = MASTER_LOOT;
        s.group.masterLooter = s.B.GetGUID();
        Scene::accept(s.A, Q_QUEST);
        s.kill({rowQuestSeed()}, s.A);
        ml[guard] = viewWith(s, s.B, MASTER_PERMISSION, guard);
        bool bGot = s.take(s.B, 0);
        viewWith(s, s.A, RESTRICTED_PERMISSION, guard);
        bool aGot = s.take(s.A, 0);
        if (guard)
            check("GUARD.C3_master_row_kept_self_store_denied_A_awarded",
                  oneRow(ml[1], Q_ITEM, LOOT_SLOT_TYPE_MASTER) && !bGot && aGot);
    }
    check("GUARD.C3_master_rows_identical_to_pinned", sameRows(ml[0], ml[1]));
    {
        Scene s;  // ordinary below-threshold item under round robin
        s.kill({rowJunk()}, s.A);
        auto a = viewWith(s, s.A, GROUP_PERMISSION, true);
        auto b = viewWith(s, s.B, GROUP_PERMISSION, true);
        check("GUARD.C2_ordinary_rows_unchanged", oneRow(a, ORDINARY_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT) && b.empty());
    }
    {
        Scene s;  // gold plus banked B view
        Scene::accept(s.A, Q_QUEST);
        bankedB(s);
        s.kill({rowQuestSeed()}, s.A);
        s.loot.gold = 50;
        viewWith(s, s.B, GROUP_PERMISSION, true);
        check("GUARD.C4_gold_still_loot_for_all", s.loot.hasItemForAll() && !s.q().is_looted);
    }
}

// The guard is a no-op with no quest list, a null viewer, or nothing to hide.
static void gNoOp()
{
    Scene s;
    s.kill({rowJunk()}, s.A);
    check("GUARD.noop_without_quest_rows_or_viewer",
          NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(&s.A, s.loot) == 0 &&
          NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(nullptr, s.loot) == 0);
}

int main()
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    loadTemplates();
    gT1();
    gT2();
    gT3();
    gT0T4();
    gControls();
    gNoOp();
    check("GUARD.marked_rows_counted", g_guardRuns > 0);
    std::printf("CHECKS %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
