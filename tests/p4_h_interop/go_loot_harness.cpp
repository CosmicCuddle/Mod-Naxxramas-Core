// P4-H follow-on: gameobject (chest) loot on the original pinned bodies.
//
// Reuses the unchanged #262 harness (main renamed), the #272 original
// handler tail (extracted by build_master_loot.extract_tail) and the real
// #272 header. A chest's loot is filled the way pinned Player::SendLoot's
// gameobject branch fills it on first open:
//   loot->FillLoot(lootid, LootTemplates_Gameobject, opener, !groupRules,
//                  false, go->GetLootMode(), go);
// i.e. personal = !(chest && groupLootRules), lootSource = the chest. A
// group-rules chest then also runs FillNotNormalLootFor for the chest's
// allowed looters; the group pass inside FillLoot already covers every
// member in range here, and FillNotNormalLootFor never refills an existing
// list, so that extra call changes nothing in these scenes.
// Not modelled: Group::MasterLoot / UpdateLooterGuid (not on the give path),
// chest traps, money, fishing.
//
// B is the master looter M and A the other player. Q0 = Timberling Seed
// (pinned quest 922), Q1 = the #262 synthetic quest item T5_ITEM.

#define main a04_baseline_main_unused
#include "../a04_native/harness.cpp"
#undef main

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

struct ChestScene : Scene
{
    Player& M = B;
    WorldObject chest;
    ObjectGuid chestGuid = ObjectGuid::Create<HighGuid::GameObject>(pinned::LOOT_2030_5168.entry, 7);

    ChestScene()
    {
        group.lootMethod = MASTER_LOOT;
        group.masterLooter = B.GetGUID();
        loot.sourceWorldObjectGUID = chestGuid;
        corpse = chestGuid;  // Scene::open/take use this as the loot GUID
    }
    // Player::SendLoot gameobject branch, first open.
    void openChestFirst(Player& opener, bool groupRules, std::vector<LootStoreItem> rows)
    {
        g_templateRows = std::move(rows);
        static LootTemplate tmpl;
        g_template = &tmpl;
        loot.FillLoot(pinned::LOOT_2030_5168.entry, store, &opener, !groupRules, false, LOOT_MODE_DEFAULT, &chest);
    }
    int slotOf(std::vector<Row> const& rows, uint32 item) const
    {
        for (Row const& r : rows)
            if (r.item == item)
                return r.slot;
        return -1;
    }
    void clearEvents()
    {
        M.ev.removedSlots.clear();
        A.ev.removedSlots.clear();
        g_stockErrors.clear();
    }
};

static bool removed(Player& p, std::vector<int> const& want) { return p.ev.removedSlots == want; }

// Group-rules chest opened by A: filled like a corpse; M (master looter at
// fill) gets a row for every quest item. Information's D3 scene.
static void goGroupRulesD3()
{
    for (int fixed = 0; fixed < 2; ++fixed)
    {
        ChestScene s;
        Scene::accept(s.A, T5_QUEST, 0);
        s.openChestFirst(s.A, true, {rowQuestSeed(), rowT5()});
        auto rowsM = s.open(s.M, MASTER_PERMISSION);
        auto rowsA = s.open(s.A, RESTRICTED_PERMISSION);
        s.clearEvents();
        int const mSlot = s.slotOf(rowsM, T5_ITEM);
        if (!fixed)
        {
            check("GO.FIXTURE.group_rules_leader_every_row_recipient_own_row",
                  s.loot.items.empty() && rowsM.size() == 2 && mSlot == 1 && s.slotOf(rowsA, T5_ITEM) == 0 && rowsA.size() == 1 &&
                  s.loot.roundRobinPlayer == s.A.GetGUID());
            StockGiveTail(&s.M, &s.A, &s.loot, s.chestGuid, uint8(mSlot));
            check("GO.STOCK.D3_A_told_slot_it_does_not_have", s.received(s.A, T5_ITEM) == 1 && removed(s.A, {1}) && removed(s.M, {1}));
        }
        else
        {
            MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, uint8(mSlot));
            check("GO.GIVE.D3_only_A_gets_Q1_each_told_own_slot",
                  o.result == MG::Result::Given && s.received(s.A, T5_ITEM) == 1 && s.received(s.M, T5_ITEM) == 0 &&
                  s.received(s.A, Q_ITEM) == 0 && removed(s.A, {0}) && removed(s.M, {1}) && s.q(1).is_looted && !s.q(0).is_looted);
        }
    }
}

// Group-rules chest: A autostores its Q1, then M gives the same Q1.
static void goGroupRulesD2()
{
    for (int fixed = 0; fixed < 2; ++fixed)
    {
        ChestScene s;
        Scene::accept(s.M, T5_QUEST, 0);
        Scene::accept(s.A, T5_QUEST, 0);
        s.openChestFirst(s.A, true, {rowT5()});
        s.open(s.M, MASTER_PERMISSION);
        s.open(s.A, RESTRICTED_PERMISSION);
        s.clearEvents();
        bool const aFirst = s.take(s.A, 0) && s.received(s.A, T5_ITEM) == 1 && s.q(0).is_looted;
        if (!fixed)
        {
            StockGiveTail(&s.M, &s.M, &s.loot, s.chestGuid, 0);
            check("GO.STOCK.D2_second_copy_given", aFirst && s.received(s.M, T5_ITEM) == 1);
        }
        else
        {
            MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.M, s.loot, 0);
            check("GO.GIVE.D2_refused_already_looted", aFirst && o.result == MG::Result::AlreadyLooted && s.received(s.M, T5_ITEM) == 0);
        }
    }
}

// Personal chest (no group loot rules) opened by M: only M has a quest list
// (every quest item, as master looter at fill); A has none.
static void goPersonalOpenedByLeader()
{
    for (int fixed = 0; fixed < 2; ++fixed)
    {
        ChestScene s;
        Scene::accept(s.A, T5_QUEST, 0);
        s.openChestFirst(s.M, false, {rowQuestSeed(), rowT5()});
        auto rowsM = s.open(s.M, MASTER_PERMISSION);
        auto rowsA = s.open(s.A, RESTRICTED_PERMISSION);
        s.clearEvents();
        int const mSlot = s.slotOf(rowsM, T5_ITEM);
        if (!fixed)
        {
            check("GO.FIXTURE.personal_only_opener_has_rows",
                  s.inQuestList(s.M) && !s.inQuestList(s.A) && rowsM.size() == 2 && mSlot == 1 && rowsA.empty() &&
                  s.loot.roundRobinPlayer == ObjectGuid::Empty);
            StockGiveTail(&s.M, &s.A, &s.loot, s.chestGuid, uint8(mSlot));
            // Award is right (M's slots match the global indices); A, who has no row, is still sent slot 1.
            check("GO.STOCK.personal_award_right_rowless_viewer_sent_slot",
                  s.received(s.A, T5_ITEM) == 1 && removed(s.M, {1}) && removed(s.A, {1}));
        }
        else
        {
            MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, uint8(mSlot));
            check("GO.GIVE.personal_same_award_only_row_holder_notified",
                  o.result == MG::Result::Given && s.received(s.A, T5_ITEM) == 1 && s.received(s.M, T5_ITEM) == 0 &&
                  removed(s.M, {1}) && s.A.ev.removedSlots.empty());
        }
    }
}

// Personal chest opened by A: M has no quest list, so M is shown no quest row.
// Only a hand-made packet can name a quest slot.
static void goPersonalOpenedByOther()
{
    for (int fixed = 0; fixed < 2; ++fixed)
    {
        ChestScene s;
        Scene::accept(s.A, T5_QUEST, 0);
        s.openChestFirst(s.A, false, {rowQuestSeed(), rowT5()});
        auto rowsM = s.open(s.M, MASTER_PERMISSION);
        auto rowsA = s.open(s.A, RESTRICTED_PERMISSION);
        s.clearEvents();
        if (!fixed)
        {
            check("GO.FIXTURE.personal_other_opener_leader_has_no_row",
                  !s.inQuestList(s.M) && rowsM.empty() && rowsA.size() == 1 && s.slotOf(rowsA, T5_ITEM) == 0);
            StockGiveTail(&s.M, &s.A, &s.loot, s.chestGuid, 1);
            check("GO.STOCK.crafted_slot_gives_item_leader_not_shown", s.received(s.A, T5_ITEM) == 1);
        }
        else
        {
            MG::Outcome const o0 = MG::GiveQuestSlot(&s.M, &s.A, s.loot, 0);
            MG::Outcome const o1 = MG::GiveQuestSlot(&s.M, &s.A, s.loot, 1);
            check("GO.GIVE.crafted_slots_refused_no_row",
                  o0.result == MG::Result::AlreadyLooted && o1.result == MG::Result::AlreadyLooted &&
                  s.received(s.A, T5_ITEM) == 0 && s.received(s.A, Q_ITEM) == 0 && !s.q(0).is_looted && !s.q(1).is_looted &&
                  s.A.ev.removedSlots.empty());
            check("GO.GIVE.A_still_loots_own_row", s.take(s.A, uint8(rowsA[0].slot)) && s.received(s.A, T5_ITEM) == 1);
        }
    }
}

// Deliberately malformed zero-count loot-template row. This bypasses the
// database LootStoreItem::IsValid loader (test-only), and exercises pinned
// Loot::AddItem: count=0 computes stacks=0 and emits NO LootItem at all.
// Thus a normal freshly filled chest cannot yield (count=0, is_looted=false)
// via this source path. An arbitrary other script mutating a filled loot item
// later is outside this narrow test and must not be claimed impossible.
static void goZeroCountTemplateCannotEmitRow()
{
    ChestScene s;
    Scene::accept(s.M, T5_QUEST, 0);
    Scene::accept(s.A, T5_QUEST, 0);
    s.openChestFirst(s.A, true, {LootStoreItem(T5_ITEM, 0, 100.0f, true, 1, 0, 0, 0)});
    auto const rowsM = s.open(s.M, MASTER_PERMISSION);
    auto const rowsA = s.open(s.A, RESTRICTED_PERMISSION);
    s.clearEvents();

    check("GO.ZERO.original_AddItem_emits_no_zero_count_quest_row",
          s.loot.items.empty() && s.loot.quest_items.empty() &&
          rowsM.empty() && rowsA.empty() && s.loot.unlootedCount == 0);

    // A crafted quest-slot request must be refused, without an award,
    // quest counter, removed-slot notification or unlootedCount underflow.
    MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, 0);
    check("GO.ZERO.crafted_master_give_denied_without_side_effects",
          o.result == MG::Result::AlreadyLooted &&
          s.received(s.A, T5_ITEM) == 0 && s.received(s.M, T5_ITEM) == 0 &&
          s.A.ev.removedSlots.empty() && s.M.ev.removedSlots.empty() &&
          s.loot.unlootedCount == 0 &&
          s.A.m_QuestStatus[T5_QUEST].ItemCount[0] == 0);
}

// Group-rules chest with a normal item: the header leaves it to the core.
static void goNormalSlot()
{
    ChestScene s;
    s.openChestFirst(s.A, true, {rowJunk(), rowT5()});
    s.open(s.M, MASTER_PERMISSION);
    s.clearEvents();
    MG::Outcome const o = MG::GiveQuestSlot(&s.M, &s.A, s.loot, 0);
    check("GO.PASS.normal_slot_left_to_core", o.result == MG::Result::PassThrough && !s.loot.items[0].is_looted &&
                                              s.received(s.A, ORDINARY_ITEM) == 0 && s.M.ev.removedSlots.empty());
}

int main()
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    loadTemplates();
    goGroupRulesD3();
    goGroupRulesD2();
    goPersonalOpenedByLeader();
    goPersonalOpenedByOther();
    goNormalSlot();
    goZeroCountTemplateCannotEmitRow();
    std::printf("CHECKS %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
