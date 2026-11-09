// TEST ONLY: quest 855 "Centaur Bracers" requires 15 x item 5030.
// A04 original pinned Core loot/quest methods and real Naxx H1/H2 headers.
// The creature is a SYNTHETIC loot-drop fixture: not owner installed SQL,
// not any actual Kolkar creature loot table, client packet, or 3.3.5a runtime.
// Keep every human's own quest right, normal loot, gold, and Master Loot intact.

#define main p4_a04_baseline_main_unused
#include "a04_native/harness.cpp"
#undef main

#include "QuestLootPickupAuthorization.h"
#include "QuestLootSparkleGuard.h"

namespace PA = NaxxramasQuestLootPickupAuthorization;
namespace SG = NaxxramasQuestLootSparkleGuard;

constexpr uint32 BRACER_QUEST = 855;
constexpr uint32 BRACER_ITEM = 5030;
constexpr uint32 BRACER_NEED = 15;

static void LoadCentaurBracerFixture()
{
    loadTemplates();
    ItemTemplate bracer{};
    bracer.ItemId = BRACER_ITEM;
    bracer.Class = ITEM_CLASS_QUEST;
    bracer.Quality = ITEM_QUALITY_NORMAL;
    bracer.Bonding = BIND_QUEST_ITEM;
    bracer.Stackable = 20;
    bracer.Name1 = "synthetic 3.3.5a quest 855 bracer";
    g_objectMgr.items[BRACER_ITEM] = bracer;

    Quest quest;
    quest.Id = BRACER_QUEST;
    quest.SpecialFlags = QUEST_SPECIAL_FLAGS_DELIVER;
    quest.RequiredItemId[0] = BRACER_ITEM;
    quest.RequiredItemCount[0] = BRACER_NEED;
    g_objectMgr.quests[BRACER_QUEST] = quest;
}

static LootStoreItem RowCentaurBracer()
{
    // The item and quest identifiers are real; the 100% loot row is synthetic.
    return LootStoreItem(BRACER_ITEM, 0, 100.0f, true, 1, 0, 1, 1);
}

static void GiveToBags(Player& p, uint32 n)
{
    for (uint32 i = 0; i < n; ++i)
        Scene::gainToBags(p, BRACER_ITEM);
}

// B needs one more on corpse creation, and already has one in the bank.
// B reaches 15 only when that item is retrieved AFTER ordinary corpse
// loot has been removed. This deliberately isolates the H1/H2 test
// from the distinct stock bag-to-bank quest-counter double-subtract issue.
// A remains legitimately at 14/15 and must still be able to take item 15.
static void Quest855CompletedFriendAfterNormalLootRemoved()
{
    Scene s;
    Scene::accept(s.A, BRACER_QUEST);
    Scene::accept(s.B, BRACER_QUEST);
    GiveToBags(s.A, BRACER_NEED - 1);
    // Seed an already-banked bracer as PRE-EXISTING fixture state.
    // The original A04 bag->bank swap model itself exercises a known
    // double-subtract counter witness (T5). Do not mix that independent
    // stock counter defect into this H1/H2 cached-quest-row test.
    GiveToBags(s.B, BRACER_NEED - 1);
    s.B.bankCount[BRACER_ITEM] = 1;
    check("Q855.setup_A_14_B_14_and_one_in_bank",
        s.A.m_QuestStatus[BRACER_QUEST].ItemCount[0] == 14 &&
        s.B.m_QuestStatus[BRACER_QUEST].ItemCount[0] == 14 &&
        s.B.GetItemCount(BRACER_ITEM, true) == 15 &&
        s.B.GetQuestStatus(BRACER_QUEST) == QUEST_STATUS_INCOMPLETE);

    s.kill({rowJunk(), RowCentaurBracer()}, s.A);
    check("Q855.corpse_has_normal_plus_required_quest_row",
        s.loot.items.size() == 1 && s.loot.quest_items.size() == 1 &&
        s.loot.unlootedCount == 2 && s.inQuestList(s.A) && s.inQuestList(s.B));

    s.open(s.A, GROUP_PERMISSION);
    check("Q855.normal_loot_awarded_A_without_using_quest_row",
        s.take(s.A, 0) && s.received(s.A, ORDINARY_ITEM) == 1);
    check("Q855.only_required_quest_item_remains_unlooted",
        s.loot.items[0].is_looted && !s.q().is_looted &&
        s.loot.unlootedCount == 1);

    // B's quest counter is 14/15 but B owns item 15 in the bank.
    // Original HasQuestForItem counts banked ownership separately from the
    // incomplete bag-quest counter, so B must NOT claim another bracer.
    check("Q855.B_incomplete_counter_but_bank_blocks_excess_sparkle",
        s.B.GetQuestStatus(BRACER_QUEST) == QUEST_STATUS_INCOMPLETE &&
        !s.B.HasQuestForItem(BRACER_ITEM) &&
        !SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION));
    check("Q855.B_incomplete_passive_view_does_not_consume_A_quest_item",
        !s.q().is_looted && !s.ownQuestRowLooted(s.A));

    Scene::bankToBag(s.B, BRACER_ITEM);
    check("Q855.B_completes_15_after_corpse_but_A_still_needs_one",
        s.B.GetQuestStatus(BRACER_QUEST) == QUEST_STATUS_COMPLETE &&
        s.B.m_QuestStatus[BRACER_QUEST].ItemCount[0] == BRACER_NEED &&
        s.A.GetQuestStatus(BRACER_QUEST) == QUEST_STATUS_INCOMPLETE);
    check("Q855.B_old_cached_quest_row_remains_after_completion",
        s.inQuestList(s.B) && !s.q().is_looted);

    auto b = s.open(s.B, GROUP_PERMISSION);
    check("Q855.B_stock_view_may_still_show_LOCKED_quest_row",
        oneRow(b, BRACER_ITEM, LOOT_SLOT_TYPE_LOCKED));
    check("Q855.B_H1_only_tests_slot_visibility",
        PA::SlotVisibleInServerView(&s.B, s.loot, GROUP_PERMISSION, 1));
    check("Q855.B_H2_no_sparkle_when_normal_loot_gone",
        !SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION));
    check("Q855.B_H2_repeat_view_after_reentry_remains_no_sparkle",
        !SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION) &&
        !SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION));
    check("Q855.B_passive_checks_leave_shared_and_owner_loot_unmodified",
        !s.q().is_looted && !s.ownQuestRowLooted(s.A) &&
        s.loot.unlootedCount == 1);

    bool const bGot = s.take(s.B, 1);
    check("Q855.B_stock_pickup_is_denied_despite_visible_locked_row",
        !bGot && s.received(s.B, BRACER_ITEM) == 0);
    check("Q855.B_denied_pickup_does_not_take_A_item",
        !s.q().is_looted && !s.ownQuestRowLooted(s.A));

    auto a = s.open(s.A, GROUP_PERMISSION);
    check("Q855.A_still_sees_quest_item_after_B_denial",
        oneRow(a, BRACER_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
    check("Q855.A_H1_allows_and_H2_keeps_rightful_sparkle",
        PA::SlotVisibleInServerView(&s.A, s.loot, GROUP_PERMISSION, 1) &&
        SG::ViewOffersSomething(&s.A, s.loot, GROUP_PERMISSION));
    check("Q855.A_original_Core_awards_final_bracer",
        s.take(s.A, 1) && s.received(s.A, BRACER_ITEM) == 1);
    check("Q855.A_reaches_15_and_B_keeps_independent_15",
        s.objectiveDone(s.A, BRACER_QUEST, BRACER_NEED) &&
        s.objectiveDone(s.B, BRACER_QUEST, BRACER_NEED) &&
        s.received(s.B, BRACER_ITEM) == 0);
}

// The actual positive fairness control is B at 14/15 with NOTHING banked.
// B really needs another bracer and must retain quest-only sparkle rights.
static void Quest855UnbankedFriendStillNeedsBracer()
{
    Scene s;
    Scene::accept(s.A, BRACER_QUEST);
    Scene::accept(s.B, BRACER_QUEST);
    GiveToBags(s.A, BRACER_NEED - 1);
    GiveToBags(s.B, BRACER_NEED - 1);
    s.kill({RowCentaurBracer()}, s.A);
    check("Q855.unbanked_B_at_14_has_actionable_quest_sparkle",
        s.B.GetQuestStatus(BRACER_QUEST) == QUEST_STATUS_INCOMPLETE &&
        s.B.GetItemCount(BRACER_ITEM, true) == BRACER_NEED - 1 &&
        s.B.HasQuestForItem(BRACER_ITEM) &&
        SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION) &&
        SG::ViewOffersSomething(&s.A, s.loot, GROUP_PERMISSION) &&
        !s.q().is_looted);
}

// The completed/ineligible viewer should NOT inherit a quest-only corpse
// sparkle even when A's quest row remains. Gold still counts as something.
static void Quest855NonParticipantAndLegitimateGold()
{
    Scene s;
    Scene::accept(s.A, BRACER_QUEST);
    GiveToBags(s.A, BRACER_NEED - 1);
    s.kill({RowCentaurBracer()}, s.A);
    check("Q855.nonparticipant_B_does_not_sparkle",
        !SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION));
    check("Q855.nonparticipant_A_still_sparkles",
        SG::ViewOffersSomething(&s.A, s.loot, GROUP_PERMISSION));
    s.loot.gold = 37;
    check("Q855.gold_still_causes_ordinary_sparkle_for_B",
        SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION));
    s.loot.gold = 0;
    check("Q855.gold_removed_does_not_leave_false_quest_sparkle_B",
        !SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION));
    check("Q855.gold_read_checks_do_not_consume_shared_quest_item",
        !s.q().is_looted && s.inQuestList(s.A));
}

int main()
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    LoadCentaurBracerFixture();
    Quest855UnbankedFriendStillNeedsBracer();
    Quest855CompletedFriendAfterNormalLootRemoved();
    Quest855NonParticipantAndLegitimateGold();
    std::printf("QUEST855 CHECKS %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
