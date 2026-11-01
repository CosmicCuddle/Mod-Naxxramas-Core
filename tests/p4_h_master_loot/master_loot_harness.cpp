// P4-H Master Loot quest-slot give on the original pinned bodies.
//
// Reuses the unchanged #262 harness (main renamed) and the module's real
// header. "Stock" runs the ORIGINAL tail of pinned
// WorldSession::HandleLootMasterGiveOpcode (slot check to the end), extracted
// byte for byte by build_master_loot.py; only SendLootError is redirected to
// a recorder. The handler's earlier checks (leader, method, target, loot
// GUID, raid) all pass in these scenes and are left to the core by the
// module, so both paths start from the same point.
//
// In every scene B is the master looter (leader M) and A the recipient.
// Quest items: Q0 = Timberling Seed (pinned quest 922 / loot row 2030),
// Q1 = the #262 synthetic quest item T5_ITEM (quest T5_QUEST, needs 2).

#define main a04_baseline_main_unused
#include "../a04_native/harness.cpp"
#undef main

// The #262 InventoryResult stub lists only the values its bodies use. These two
// are read by the handler tail; values are pinned Item.h L57 / L64
// (build_master_loot.py checks those lines).
#define EQUIP_ERR_YOU_CAN_NEVER_USE_THAT_ITEM InventoryResult(10)
#define EQUIP_ERR_CANT_CARRY_MORE_OF_THIS InventoryResult(17)

#include "MasterLootQuestGive.h"

namespace MG = NaxxramasMasterLootQuestGive;

static std::vector<int> g_stockErrors;
static void StockLootError(Player*, ObjectGuid, LootError error) { g_stockErrors.push_back(error); }

static void StockGiveTail(Player* _player, Player* target, Loot* loot, ObjectGuid lootguid, uint8 slotid)
{
#include "stock_master_give.inc"
}

static ObjectGuid const kNoGuid;

// A Master Loot scene: M (= B) is the leader, both players opened the corpse.
struct MasterScene : Scene
{
    Player& M = B;
    std::vector<Row> rowsM, rowsA;

    MasterScene()
    {
        group.lootMethod = MASTER_LOOT;
        group.masterLooter = B.GetGUID();
    }
    // Pinned FillQuestLoot (LootMgr.cpp L663-676) gives the CURRENT master
    // looter a row for every quest item, so M's slots match the global
    // indices. They differ only if the role moves after the corpse filled:
    // fill with A as master looter, then hand the role to M.
    void killThenPassRoleToM(std::vector<LootStoreItem> rows)
    {
        group.masterLooter = A.GetGUID();
        kill(std::move(rows), A);
        group.masterLooter = M.GetGUID();
    }
    void openBoth()
    {
        rowsM = open(M, MASTER_PERMISSION);
        rowsA = open(A, RESTRICTED_PERMISSION);
        M.ev.removedSlots.clear();
        A.ev.removedSlots.clear();
        g_stockErrors.clear();
    }
    int slotOf(std::vector<Row> const& rows, uint32 item) const
    {
        for (Row const& r : rows)
            if (r.item == item)
                return r.slot;
        return -1;
    }
};

static bool removed(Player& p, std::vector<int> const& want) { return p.ev.removedSlots == want; }

// Information's scenario: M needs Q0 and Q1, A only Q1. M gives Q1 to A.
static void hD3WrongRemovedSlot()
{
    for (int fixed = 0; fixed < 2; ++fixed)
    {
        MasterScene s;
        Scene::accept(s.M, Q_QUEST, 0);
        Scene::accept(s.M, T5_QUEST, 1);
        Scene::accept(s.A, T5_QUEST, 0);
        s.kill({rowQuestSeed(), rowT5()}, s.A);
        s.openBoth();
        int const mSlot = s.slotOf(s.rowsM, T5_ITEM);
        int const aSlot = s.slotOf(s.rowsA, T5_ITEM);
        if (!fixed)
        {
            check("FIXTURE.quest_items_are_Q0_then_Q1",
                  s.loot.quest_items.size() == 2 && s.q(0).itemid == Q_ITEM && s.q(1).itemid == T5_ITEM && s.loot.items.empty());
            check("FIXTURE.D3_leader_sees_Q1_at_N1_recipient_at_N0",
                  mSlot == 1 && aSlot == 0 && s.slotOf(s.rowsA, Q_ITEM) == -1 &&
                  s.rowsM.size() == 2 && s.rowsM[1].slotType == LOOT_SLOT_TYPE_MASTER);
            StockGiveTail(&s.M, &s.A, &s.loot, s.corpse, uint8(mSlot));
            check("STOCK.D3_A_gets_Q1", s.received(s.A, T5_ITEM) == 1 && s.received(s.M, T5_ITEM) == 0);
            check("STOCK.D3_A_told_to_remove_slot_it_does_not_have", removed(s.A, {1}) && removed(s.M, {1}));
        }
        else
        {
            unsigned const before = s.loot.unlootedCount;
            MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, uint8(mSlot));
            check("GIVE.D3_given", o.result == MG::Result::Given);
            check("GIVE.D3_only_A_gets_Q1", s.received(s.A, T5_ITEM) == 1 && s.received(s.M, T5_ITEM) == 0 &&
                                            s.received(s.A, Q_ITEM) == 0 && s.received(s.M, Q_ITEM) == 0);
            check("GIVE.D3_each_viewer_told_own_slot", removed(s.A, {0}) && removed(s.M, {1}));
            check("GIVE.D3_item_marked_and_count_lowered",
                  s.q(1).is_looted && s.q(1).count == 0 && !s.q(0).is_looted && s.loot.unlootedCount + 1 == before);
            auto again = s.open(s.M, MASTER_PERMISSION);
            check("GIVE.D3_leader_reopen_shows_only_Q0", again.size() == 1 && again[0].item == Q_ITEM && again[0].slot == 0);
        }
    }
}

// The reverse, after the role moved to M: M needs only Q1, A needs Q0 and Q1.
// M clicks Q1 (M's N+0).
static void hD1WrongItem()
{
    for (int fixed = 0; fixed < 2; ++fixed)
    {
        MasterScene s;
        Scene::accept(s.M, T5_QUEST, 0);
        Scene::accept(s.A, Q_QUEST, 0);
        Scene::accept(s.A, T5_QUEST, 1);
        s.killThenPassRoleToM({rowQuestSeed(), rowT5()});
        s.openBoth();
        int const mSlot = s.slotOf(s.rowsM, T5_ITEM);
        if (!fixed)
        {
            check("FIXTURE.D1_leader_sees_only_Q1_at_N0",
                  mSlot == 0 && s.rowsM.size() == 1 && s.slotOf(s.rowsA, Q_ITEM) == 0 && s.slotOf(s.rowsA, T5_ITEM) == 1);
            StockGiveTail(&s.M, &s.A, &s.loot, s.corpse, uint8(mSlot));
            check("STOCK.D1_A_gets_Q0_not_the_clicked_Q1", s.received(s.A, Q_ITEM) == 1 && s.received(s.A, T5_ITEM) == 0);
            check("STOCK.D1_leader_told_to_remove_Q1_that_is_still_there", removed(s.M, {0}) && !s.q(1).is_looted);
        }
        else
        {
            MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, uint8(mSlot));
            check("GIVE.D1_A_gets_the_clicked_Q1", o.result == MG::Result::Given &&
                                                  s.received(s.A, T5_ITEM) == 1 && s.received(s.A, Q_ITEM) == 0);
            check("GIVE.D1_each_viewer_told_own_slot", removed(s.M, {0}) && removed(s.A, {1}));
            check("GIVE.D1_Q0_still_lootable_by_A", !s.q(0).is_looted && s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 1);
        }
    }
}

// A autostores its own Q1 row; M gives the same Q1 from a stale window.
static void hD2AlreadyLooted()
{
    for (int fixed = 0; fixed < 2; ++fixed)
    {
        MasterScene s;
        Scene::accept(s.M, T5_QUEST, 0);
        Scene::accept(s.A, T5_QUEST, 0);
        s.kill({rowT5()}, s.A);
        s.openBoth();
        check(fixed ? "FIXTURE.D2_A_autostores_first_fixed" : "FIXTURE.D2_A_autostores_first_stock",
              s.take(s.A, 0) && s.received(s.A, T5_ITEM) == 1 && s.q(0).is_looted && s.q(0).count == 1);
        if (!fixed)
        {
            StockGiveTail(&s.M, &s.M, &s.loot, s.corpse, 0);
            check("STOCK.D2_same_copy_given_again", s.received(s.M, T5_ITEM) == 1);
        }
        else
        {
            MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.M, s.loot, 0);
            check("GIVE.D2_refused_already_looted", o.result == MG::Result::AlreadyLooted && s.received(s.M, T5_ITEM) == 0);
        }
    }
}

// Error parity with the original tail: bags full, and a target who cannot use it.
static void hErrorParity()
{
    struct Case { char const* id; bool bagsFull; bool targetNeeds; LootError want; };
    Case const cases[] = {
        {"ERRORS.inventory_full", true, true, LOOT_ERROR_MASTER_INV_FULL},
        {"ERRORS.target_cannot_use", false, false, LOOT_ERROR_MASTER_OTHER},
        {"ERRORS.full_and_cannot_use", true, false, LOOT_ERROR_MASTER_OTHER},
    };
    for (Case const& c : cases)
    {
        int stockError = -1;
        int moduleError = -1;
        for (int fixed = 0; fixed < 2; ++fixed)
        {
            MasterScene s;
            Scene::accept(s.M, T5_QUEST, 0);
            if (c.targetNeeds)
                Scene::accept(s.A, T5_QUEST, 0);
            s.A.bagsFull = c.bagsFull;
            s.kill({rowT5()}, s.A);
            s.openBoth();
            unsigned const before = s.loot.unlootedCount;
            if (!fixed)
            {
                StockGiveTail(&s.M, &s.A, &s.loot, s.corpse, 0);
                stockError = g_stockErrors.size() == 1 ? g_stockErrors[0] : -1;
            }
            else
            {
                MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, 0);
                moduleError = o.result == MG::Result::Error ? int(o.error) : -1;
            }
            if (fixed)
                check(c.id, stockError == int(c.want) && moduleError == int(c.want) && s.received(s.A, T5_ITEM) == 0 &&
                            !s.q(0).is_looted && s.loot.unlootedCount == before && s.M.ev.removedSlots.empty());
        }
    }
}

// Malformed quest item: count zero but shared and viewer looted bits FALSE.
// Normal loot creation is not claimed to produce this state. Refuse cleanly
// without item, achievement, notification or counter changes.
static void hZeroCountUnlooted()
{
    MasterScene s;
    Scene::accept(s.M, T5_QUEST, 0);
    Scene::accept(s.A, T5_QUEST, 0);
    s.kill({rowT5()}, s.A);
    s.openBoth();
    auto const& map = s.loot.GetPlayerQuestItems();
    auto const it = map.find(s.M.GetGUID());
    bool const leaderRow = it != map.end() && it->second &&
                           !it->second->empty() && !it->second->at(0).is_looted;
    s.q(0).count = 0;
    unsigned const before = s.loot.unlootedCount;
    MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, 0);
    check("GIVE.zero_count_unlooted_refused_no_effects",
          !s.rowsM.empty() && leaderRow && before > 0 &&
          o.result == MG::Result::AlreadyLooted &&
          s.received(s.A, T5_ITEM) == 0 && s.received(s.M, T5_ITEM) == 0 &&
          s.q(0).count == 0 && !s.q(0).is_looted &&
          !it->second->at(0).is_looted && s.loot.unlootedCount == before &&
          s.A.ev.removedSlots.empty() && s.M.ev.removedSlots.empty());
}

static void hLeftAlone()
{
    {
        MasterScene s;  // normal slot: the core handles it
        s.kill({rowJunk()}, s.A);
        s.openBoth();
        MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, 0);
        check("PASS.normal_slot_left_to_core", o.result == MG::Result::PassThrough && s.received(s.A, ORDINARY_ITEM) == 0 &&
                                               !s.loot.items[0].is_looted && s.A.ev.removedSlots.empty());
    }
    {
        MasterScene s;  // FFA quest copy: the leader is never shown it as a MASTER row
        Scene::accept(s.M, FFA_QUEST, 0);
        Scene::accept(s.A, FFA_QUEST, 0);
        s.kill({rowFfaClaw()}, s.A);
        s.openBoth();
        bool const shownAllowLoot = s.rowsM.size() == 1 && s.rowsM[0].slotType == LOOT_SLOT_TYPE_ALLOW_LOOT;
        MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, uint8(s.rowsM.empty() ? 0 : s.rowsM[0].slot));
        check("FFA.copy_refused_not_a_master_row", shownAllowLoot && o.result == MG::Result::Error &&
                                                   o.error == LOOT_ERROR_MASTER_OTHER && s.received(s.A, FFA_ITEM) == 0);
        check("FFA.both_copies_still_lootable", s.take(s.A, uint8(s.rowsA[0].slot)) && s.take(s.M, uint8(s.rowsM[0].slot)));
    }
    for (int fixed = 0; fixed < 2; ++fixed)
    {
        MasterScene s;  // role moved to M, who needs nothing: M is shown no quest row
        Scene::accept(s.A, T5_QUEST, 0);
        s.killThenPassRoleToM({rowT5()});
        s.openBoth();
        if (!fixed)
        {
            StockGiveTail(&s.M, &s.A, &s.loot, s.corpse, 0);
            check("STOCK.ROW_gives_an_item_the_leader_is_not_shown", s.rowsM.empty() && s.received(s.A, T5_ITEM) == 1);
        }
        else
        {
            MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, 0);
            check("ROW.leader_without_row_refused", s.rowsM.empty() && o.result == MG::Result::AlreadyLooted &&
                                                    s.received(s.A, T5_ITEM) == 0 && !s.q(0).is_looted);
        }
    }
    {
        MasterScene s;  // M is the master looter at fill time: a row for every quest item
        Scene::accept(s.A, T5_QUEST, 0);
        s.kill({rowQuestSeed(), rowT5()}, s.A);
        s.openBoth();
        check("FIXTURE.leader_at_fill_gets_every_quest_row",
              s.rowsM.size() == 2 && s.slotOf(s.rowsM, Q_ITEM) == 0 && s.slotOf(s.rowsM, T5_ITEM) == 1);
    }
    {
        MasterScene s;  // both need both: stock and module agree
        Scene::accept(s.M, Q_QUEST, 0);
        Scene::accept(s.M, T5_QUEST, 1);
        Scene::accept(s.A, Q_QUEST, 0);
        Scene::accept(s.A, T5_QUEST, 1);
        s.kill({rowQuestSeed(), rowT5()}, s.A);
        s.openBoth();
        MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, 1);
        check("SAME.prefix_case_matches_stock", o.result == MG::Result::Given && s.received(s.A, T5_ITEM) == 1 &&
                                                removed(s.A, {1}) && removed(s.M, {1}));
    }
}

int main()
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    loadTemplates();
    hD3WrongRemovedSlot();
    hD1WrongItem();
    hD2AlreadyLooted();
    hZeroCountUnlooted();
    hErrorParity();
    hLeftAlone();
    std::printf("CHECKS %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
