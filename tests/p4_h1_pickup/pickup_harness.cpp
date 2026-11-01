// P4 H1 pickup authorization on the original pinned bodies.
//
// Reuses the unchanged #262 harness (main renamed) and the module's real
// headers QuestLootViewGuard.h and QuestLootPickupAuthorization.h. Each
// award path is run as stock (no check) and with the check placed where the
// module runs it: ServerScript::CanPacketReceive, before
// HandleAutostoreLootItemOpcode calls the original StoreLootItem.

#define main a04_baseline_main_unused
#include "../a04_native/harness.cpp"
#undef main

#include "QuestLootPickupAuthorization.h"

namespace PA = NaxxramasQuestLootPickupAuthorization;

// A CMSG_AUTOSTORE_LOOT_ITEM for 'slot' after the player opened the corpse.
// With the check on, a refused request never reaches StoreLootItem.
static bool autostore(Scene& s, Player& p, PermissionTypes perm, uint8 slot, bool check, bool* refused = nullptr)
{
    bool const visible = PA::SlotVisibleInServerView(&p, s.loot, perm, slot);
    if (refused)
        *refused = check && !visible;
    if (check && !visible)
        return false;
    return s.take(p, slot);
}

// Synthetic loot row: the same pinned item 5168, but QuestRequired=0, so it
// lands in the normal item list (a quest-class item in ordinary loot).
static LootStoreItem rowSeedAsNormalLoot() { return LootStoreItem(Q_ITEM, 0, 100.0f, false, 1, 0, 1, 1); }

// Pinned LootHandler.cpp clears roundRobinPlayer when its owner releases the corpse.
static void ownerReleases(Scene& s) { s.loot.roundRobinPlayer.Clear(); }

// ---- O2: below-threshold ordinary item reserved by round robin for A ----
static void hHiddenOrdinary()
{
    for (int withCheck = 0; withCheck < 2; ++withCheck)
    {
        Scene s;
        s.kill({rowJunk()}, s.A);
        auto b = s.open(s.B, GROUP_PERMISSION);
        bool refused = false;
        bool bGot = autostore(s, s.B, GROUP_PERMISSION, 0, withCheck, &refused);
        if (!withCheck)
        {
            check("STOCK.O2_hidden_round_robin_slot_awarded_to_B", b.empty() && bGot);
            continue;
        }
        check("AUTH.O2_hidden_slot_refused_B_gets_nothing", b.empty() && refused && !bGot && s.received(s.B, ORDINARY_ITEM) == 0);
        s.open(s.A, GROUP_PERMISSION);
        check("AUTH.O2_owner_A_still_awarded", autostore(s, s.A, GROUP_PERMISSION, 0, true) && s.received(s.A, ORDINARY_ITEM) == 1);
    }
    {
        Scene s;  // after the owner releases, stock lets the group take it; unchanged
        s.kill({rowJunk()}, s.A);
        ownerReleases(s);
        auto b = s.open(s.B, GROUP_PERMISSION);
        check("AUTH.O2_after_release_B_sees_and_takes_unchanged",
               oneRow(b, ORDINARY_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT) && autostore(s, s.B, GROUP_PERMISSION, 0, true));
    }
}

// ---- H1 candidate: quest item 5168 in NORMAL loot, B has no quest ----
static void hQuestItemInNormalLoot()
{
    for (int withCheck = 0; withCheck < 2; ++withCheck)
    {
        Scene s;
        Scene::accept(s.A, Q_QUEST);
        s.kill({rowSeedAsNormalLoot()}, s.A);
        auto b = s.open(s.B, GROUP_PERMISSION);
        bool bGot = autostore(s, s.B, GROUP_PERMISSION, 0, withCheck);
        if (!withCheck)
        {
            check("STOCK.H1_quest_class_item_hidden_from_B_still_awarded_to_B",
                   b.empty() && bGot && s.received(s.B, Q_ITEM) == 1 && s.B.GetQuestStatus(Q_QUEST) == QUEST_STATUS_NONE);
            continue;
        }
        check("AUTH.H1_quest_class_item_refused_for_B", b.empty() && !bGot && s.received(s.B, Q_ITEM) == 0);
        s.open(s.A, GROUP_PERMISSION);
        check("AUTH.H1_A_awarded_and_quest_completes",
               autostore(s, s.A, GROUP_PERMISSION, 0, true) && s.objectiveDone(s.A, Q_QUEST, 1));
    }
    {
        Scene s;  // released turn: stock shows it to B; owner policy (A/B/C), not changed here
        Scene::accept(s.A, Q_QUEST);
        s.kill({rowSeedAsNormalLoot()}, s.A);
        ownerReleases(s);
        auto b = s.open(s.B, GROUP_PERMISSION);
        check("POLICY.H1_after_release_visible_to_B_and_allowed_unchanged",
               oneRow(b, Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT) && autostore(s, s.B, GROUP_PERMISSION, 0, true));
    }
}

// ---- Quest-required loot (quest_items): stock already denies non-entitled B ----
static void hQuestItems()
{
    {
        Scene s;  // B has no quest: no row, refused either way
        Scene::accept(s.A, Q_QUEST);
        s.kill({rowQuestSeed()}, s.A);
        s.open(s.B, GROUP_PERMISSION);
        bool stock = s.take(s.B, 0);
        s.open(s.B, GROUP_PERMISSION);
        bool refused = false;
        autostore(s, s.B, GROUP_PERMISSION, 0, true, &refused);
        check("AUTH.quest_items_non_entitled_B_refused_as_stock", !stock && refused);
        s.open(s.A, GROUP_PERMISSION);
        check("AUTH.quest_items_A_awarded", autostore(s, s.A, GROUP_PERMISSION, 0, true) && s.loot.isLooted());
    }
    for (int bFirst = 0; bFirst < 2; ++bFirst)
    {
        Scene s;  // both entitled: first visible taker wins, unchanged (owner policy)
        Scene::accept(s.A, Q_QUEST);
        Scene::accept(s.B, Q_QUEST);
        s.kill({rowQuestSeed()}, s.A);
        s.open(s.A, GROUP_PERMISSION);
        s.open(s.B, GROUP_PERMISSION);
        Player& first = bFirst ? s.B : s.A;
        Player& second = bFirst ? s.A : s.B;
        bool ok = autostore(s, first, GROUP_PERMISSION, 0, true) && !autostore(s, second, GROUP_PERMISSION, 0, true);
        check(bFirst ? "POLICY.T4b_both_entitled_first_taker_unchanged" : "POLICY.T4a_both_entitled_first_taker_unchanged", ok);
    }
    {
        Scene s;  // T1 with the check: B's banked view leaves no shared side effect
        Scene::accept(s.A, Q_QUEST);
        bankedB(s);
        s.kill({rowQuestSeed()}, s.A);
        s.open(s.A, GROUP_PERMISSION);
        s.B.lootGuid = s.corpse;  // B clicks; the check serializes B's view first
        bool refused = false;
        autostore(s, s.B, GROUP_PERMISSION, 0, true, &refused);
        check("AUTH.check_has_no_shared_side_effect", refused && !s.q().is_looted);
        check("AUTH.T1_A_then_awarded", autostore(s, s.A, GROUP_PERMISSION, 0, true) && s.received(s.A, Q_ITEM) == 1);
    }
}

// ---- Controls: FFA copies, Master Loot, gold not affected ----
static void hControls()
{
    {
        Scene s;
        Scene::accept(s.A, FFA_QUEST);
        Scene::accept(s.B, FFA_QUEST);
        s.kill({rowFfaClaw()}, s.A);
        s.open(s.A, GROUP_PERMISSION);
        s.open(s.B, GROUP_PERMISSION);
        check("AUTH.ffa_both_copies_allowed",
               autostore(s, s.A, GROUP_PERMISSION, 0, true) && autostore(s, s.B, GROUP_PERMISSION, 0, true));
    }
    {
        Scene s;  // Master Loot: B is master looter without the quest; A has it
        s.group.lootMethod = MASTER_LOOT;
        s.group.masterLooter = s.B.GetGUID();
        Scene::accept(s.A, Q_QUEST);
        s.kill({rowQuestSeed()}, s.A);
        s.open(s.B, MASTER_PERMISSION);
        bool mlRefused = false;
        bool mlGot = autostore(s, s.B, MASTER_PERMISSION, 0, true, &mlRefused);
        s.open(s.A, RESTRICTED_PERMISSION);
        // Visible MASTER row is not refused by this check; the core still denies it.
        check("AUTH.master_row_passed_to_core_core_denies_A_awarded",
               !mlRefused && !mlGot && autostore(s, s.A, RESTRICTED_PERMISSION, 0, true));
    }
    {
        Scene s;
        s.kill({rowJunk()}, s.A);
        s.loot.gold = 50;
        check("AUTH.no_rights_means_not_visible", !PA::SlotVisibleInServerView(&s.B, s.loot, NONE_PERMISSION, 0));
    }
}

// ---- Permission mirror of pinned SendLoot (creature corpse, not skinning) ----
static void hPermission()
{
    check("PERM.group_loot", PA::CorpsePermission(true, true, false, GROUP_LOOT, false) == GROUP_PERMISSION);
    check("PERM.need_before_greed", PA::CorpsePermission(true, true, false, NEED_BEFORE_GREED, false) == GROUP_PERMISSION);
    check("PERM.round_robin", PA::CorpsePermission(true, true, false, ROUND_ROBIN, false) == ROUND_ROBIN_PERMISSION);
    check("PERM.free_for_all", PA::CorpsePermission(true, true, false, FREE_FOR_ALL, false) == ALL_PERMISSION);
    check("PERM.master_looter", PA::CorpsePermission(true, true, false, MASTER_LOOT, true) == MASTER_PERMISSION);
    check("PERM.master_other", PA::CorpsePermission(true, true, false, MASTER_LOOT, false) == RESTRICTED_PERMISSION);
    check("PERM.other_group", PA::CorpsePermission(true, false, true, GROUP_LOOT, false) == NONE_PERMISSION);
    check("PERM.solo_recipient", PA::CorpsePermission(false, false, true, FREE_FOR_ALL, false) == OWNER_PERMISSION);
    check("PERM.solo_other", PA::CorpsePermission(false, false, false, FREE_FOR_ALL, false) == NONE_PERMISSION);
}

// ---- H0 (view guard) x H1 (pickup check) ON/OFF matrix ----
// H0 runs where SendLoot calls OnPlayerBeforeSendLoot; H1 runs before the
// autostore handler. Expected: H0 alone fixes T1, H1 alone fixes the hidden
// slot, neither adds the other's effect, both ON fixes both.
static std::vector<Row> openWith(Scene& s, Player& p, PermissionTypes perm, bool viewGuard)
{
    if (viewGuard)
    {
        p.lootGuid = s.corpse;
        NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(&p, s.loot);
    }
    return s.open(p, perm);
}

static void hToggleMatrix()
{
    for (int combo = 0; combo < 4; ++combo)
    {
        bool const viewOn = combo & 1;
        bool const pickOn = combo & 2;
        char const* tag[4] = {"both_off", "view_only", "pickup_only", "both_on"};
        char id[96];

        {   // T1 order: A opens, banked B opens, B clicks, A clicks
            Scene s;
            Scene::accept(s.A, Q_QUEST);
            bankedB(s);
            s.kill({rowQuestSeed()}, s.A);
            openWith(s, s.A, GROUP_PERMISSION, viewOn);
            openWith(s, s.B, GROUP_PERMISSION, viewOn);
            bool bGot = autostore(s, s.B, GROUP_PERMISSION, 0, pickOn);
            bool aGot = autostore(s, s.A, GROUP_PERMISSION, 0, pickOn);
            std::snprintf(id, sizeof(id), "MATRIX.%s.T1_A_awarded_iff_view_guard", tag[combo]);
            check(id, !bGot && aGot == viewOn && s.received(s.B, Q_ITEM) == 0);
        }
        {   // hidden round-robin slot requested by B
            Scene s;
            s.kill({rowJunk()}, s.A);
            openWith(s, s.B, GROUP_PERMISSION, viewOn);
            bool bGot = autostore(s, s.B, GROUP_PERMISSION, 0, pickOn);
            std::snprintf(id, sizeof(id), "MATRIX.%s.hidden_slot_refused_iff_pickup_check", tag[combo]);
            check(id, bGot == !pickOn);
        }
    }
}

// With H0 OFF, H1's check changes nothing at all: not the shared flag, not
// the requester's own row, not anyone else's.
static void hPickupFootprintWithViewGuardOff()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    Scene::accept(s.B, Q_QUEST);
    s.kill({rowQuestSeed()}, s.A);
    openWith(s, s.A, GROUP_PERMISSION, false);
    openWith(s, s.B, GROUP_PERMISSION, false);  // B still needed the seed when it opened
    Scene::gainToBags(s.B, Q_ITEM);             // B gets one elsewhere and banks it
    Scene::bagToBank(s.B, Q_ITEM);
    bool const sharedBefore = s.q().is_looted, aRowBefore = s.ownQuestRowLooted(s.A);
    bool refused = false;
    autostore(s, s.B, GROUP_PERMISSION, 0, true, &refused);
    check("FOOTPRINT.view_off_check_changes_no_flag",
          refused && !s.ownQuestRowLooted(s.B) && !sharedBefore && !s.q().is_looted && aRowBefore == s.ownQuestRowLooted(s.A));
    check("FOOTPRINT.view_off_A_still_awarded_after_check", autostore(s, s.A, GROUP_PERMISSION, 0, true) && s.received(s.A, Q_ITEM) == 1);
}

int main()
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    loadTemplates();
    hHiddenOrdinary();
    hQuestItemInNormalLoot();
    hQuestItems();
    hControls();
    hPermission();
    hToggleMatrix();
    hPickupFootprintWithViewGuardOff();
    std::printf("CHECKS %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
