// TEST ONLY — actual Naxx H1 and H2 headers plus unchanged original pinned
// Grimfeather Core LootView/StoreLootItem bodies from the A04 native harness.
// No actual Worldserver, live MySQL, installed loot configs or client involved.
// Keep human guest/owner rights and Master Loot ordinary items unchanged.
// Include the common A04 harness directly, NOT the H1 executable fixture:
// p4_h1_pickup/pickup_harness.cpp itself #defines/#undefs main and declares
// its own main(). Nesting it here previously caused duplicate main symbols.
#define main p4_a04_baseline_main_unused
#include "a04_native/harness.cpp"
#undef main

#include "QuestLootPickupAuthorization.h"
#include "QuestLootSparkleGuard.h"
namespace PA = NaxxramasQuestLootPickupAuthorization;
namespace S = NaxxramasQuestLootSparkleGuard;

static void LockedQuestRowDistinctFromAuthorizedPickup()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    bankedB(s);
    s.kill({rowQuestSeed()}, s.A);

    // The exact original T3: B returns the previously banked seed to bags
    // AFTER the corpse was created, completing the quest objective.
    Scene::bankToBag(s.B, Q_ITEM);
    auto b = s.open(s.B, GROUP_PERMISSION);
    check("BRIDGE.quest_B_core_window_locked",
          oneRow(b, Q_ITEM, LOOT_SLOT_TYPE_LOCKED));

    bool const visibleToH1 =
        PA::SlotVisibleInServerView(&s.B, s.loot, GROUP_PERMISSION, 0);
    // H1 checks serializer visibility, not whether a slot is actionable.
    // This is a distinction in intent, NOT evidence of a pickup exploit.
    check("BRIDGE.quest_B_H1_can_pass_visible_locked_slot", visibleToH1);

    bool const sparkleToB =
        S::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION);
    check("BRIDGE.quest_B_H2_does_not_sparkle_locked_only", !sparkleToB);
    check("BRIDGE.quest_B_observation_does_not_consume_shared_item",
          !s.q().is_looted && !s.ownQuestRowLooted(s.A));

    // The original Core StoreLootItem still makes the decisive award check.
    bool const bGot = visibleToH1 && s.take(s.B, 0);
    check("BRIDGE.quest_B_stock_award_denied_in_spite_of_H1_visible",
          !bGot && s.received(s.B, Q_ITEM) == 0);

    auto a = s.open(s.A, GROUP_PERMISSION);
    check("BRIDGE.quest_A_unlocked_visible",
          oneRow(a, Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
    check("BRIDGE.quest_A_H1_passes",
          PA::SlotVisibleInServerView(&s.A, s.loot, GROUP_PERMISSION, 0));
    check("BRIDGE.quest_A_H2_keeps_sparkle",
          S::ViewOffersSomething(&s.A, s.loot, GROUP_PERMISSION));
    check("BRIDGE.quest_A_original_award_preserved",
          s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 1);
}

static void NormalLockedMasterLootNotBlanketDenied()
{
    Scene s;
    s.group.lootMethod = MASTER_LOOT;
    s.group.masterLooter = s.A.GetGUID();
    s.kill({rowJunk()}, s.A);
    s.loot.items[0].is_blocked = true;
    s.loot.items[0].is_underthreshold = false;

    auto b = s.open(s.B, RESTRICTED_PERMISSION);
    check("BRIDGE.master_normal_B_locked_visible",
          oneRow(b, ORDINARY_ITEM, LOOT_SLOT_TYPE_LOCKED));
    check("BRIDGE.master_normal_H1_respects_visible_locked",
          PA::SlotVisibleInServerView(&s.B, s.loot, RESTRICTED_PERMISSION, 0));
    check("BRIDGE.master_normal_H2_keeps_stock_sparkle",
          S::ViewOffersSomething(&s.B, s.loot, RESTRICTED_PERMISSION));
    check("BRIDGE.master_normal_shared_state_preserved",
          !s.loot.items[0].is_looted);
}

static void LegitimateOrdinaryLootAndGoldStayAvailable()
{
    Scene s;
    s.kill({rowJunk()}, s.A);
    s.loot.gold = 75;
    auto a = s.open(s.A, GROUP_PERMISSION);
    check("BRIDGE.normal_A_actionable",
          oneRow(a, ORDINARY_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
    check("BRIDGE.normal_A_H1_passes",
          PA::SlotVisibleInServerView(&s.A, s.loot, GROUP_PERMISSION, 0));
    check("BRIDGE.normal_A_H2_sparkles",
          S::ViewOffersSomething(&s.A, s.loot, GROUP_PERMISSION));
    check("BRIDGE.gold_B_sparkle_available",
          S::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION));
    check("BRIDGE.normal_A_original_award",
          s.take(s.A, 0) && s.received(s.A, ORDINARY_ITEM) == 1);
}

int main()
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    loadTemplates();
    LockedQuestRowDistinctFromAuthorizedPickup();
    NormalLockedMasterLootNotBlanketDenied();
    LegitimateOrdinaryLootAndGoldStayAvailable();
    std::printf("BRIDGE CHECKS %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
