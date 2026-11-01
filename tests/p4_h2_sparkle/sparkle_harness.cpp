// P4 H2 corpse sparkle guard on the original pinned bodies.
//
// Reuses the unchanged #262 harness (main renamed) and the module's real
// headers. "Core sparkle" below is pinned Player::isAllowedToLoot's corpse /
// group-loot decision recomposed from the ORIGINAL extracted Loot predicates
// (hasItemForAll, hasItemFor, hasOverThresholdItem, isLooted); the
// isAllowedToLoot body itself is not extracted (it needs a full Creature).
// The guard can only clear that sparkle, never add it.

#define main a04_baseline_main_unused
#include "../a04_native/harness.cpp"
#undef main

#include "QuestLootSparkleGuard.h"

namespace SG = NaxxramasQuestLootSparkleGuard;

// PlayerStorage.cpp L5755-L5792 for a grouped viewer under GROUP_LOOT / NEED_BEFORE_GREED.
static bool coreSparkleGroupLoot(Scene& s, Player& p)
{
    Loot const& l = s.loot;
    if (l.isLooted())
        return false;
    if (!l.hasItemForAll() && !s.loot.hasItemFor(&p))
        return false;
    if (!l.roundRobinPlayer || l.roundRobinPlayer == p.GetGUID())
        return true;
    if (l.hasOverThresholdItem())
        return true;
    return s.loot.hasItemFor(&p);
}

// What the viewer's packet would carry: core flag, then the guard (if on).
static bool sparkle(Scene& s, Player& p, PermissionTypes perm, bool guard)
{
    bool const core = coreSparkleGroupLoot(s, p);
    if (!core || !guard)
        return core;
    return SG::ViewOffersSomething(&p, s.loot, perm);
}

static void hT3StaleLockedRow()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    bankedB(s);
    s.kill({rowQuestSeed()}, s.A);
    Scene::bankToBag(s.B, Q_ITEM);  // B now has the seed: quest COMPLETE, cached row stays
    check("STOCK.T3_core_sparkles_for_B", sparkle(s, s.B, GROUP_PERMISSION, false));
    check("SPARKLE.T3_cleared_for_B", !sparkle(s, s.B, GROUP_PERMISSION, true));
    check("SPARKLE.T3_kept_for_A", sparkle(s, s.A, GROUP_PERMISSION, true));
    check("SPARKLE.T3_no_shared_side_effect", !s.q().is_looted);
    s.open(s.A, GROUP_PERMISSION);
    check("SPARKLE.T3_A_still_awarded", s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 1);
}

static void hT1BankedViewer()
{
    for (int viewGuard = 0; viewGuard < 2; ++viewGuard)
    {
        Scene s;
        Scene::accept(s.A, Q_QUEST);
        bankedB(s);
        s.kill({rowQuestSeed()}, s.A);
        if (viewGuard)
        {
            s.A.lootGuid = s.corpse;
            NaxxramasQuestLootViewGuard::HideOwnSatisfiedQuestRows(&s.A, s.loot);
        }
        bool const stock = sparkle(s, s.B, GROUP_PERMISSION, false);
        bool const guarded = sparkle(s, s.B, GROUP_PERMISSION, true);
        char id[96];
        std::snprintf(id, sizeof(id), "SPARKLE.T1_banked_B_core_yes_guard_no_view_guard_%s", viewGuard ? "on" : "off");
        check(id, stock && !guarded && !s.q().is_looted);
        s.open(s.A, GROUP_PERMISSION);
        std::snprintf(id, sizeof(id), "SPARKLE.T1_A_still_awarded_view_guard_%s", viewGuard ? "on" : "off");
        check(id, s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 1);
    }
}

static void hKeptCases()
{
    {
        Scene s;  // both need the seed
        Scene::accept(s.A, Q_QUEST);
        Scene::accept(s.B, Q_QUEST);
        s.kill({rowQuestSeed()}, s.A);
        check("SPARKLE.both_need_kept", sparkle(s, s.A, GROUP_PERMISSION, true) && sparkle(s, s.B, GROUP_PERMISSION, true));
    }
    {
        Scene s;  // round-robin owner with ordinary loot
        s.kill({rowJunk()}, s.A);
        check("SPARKLE.round_robin_owner_kept", sparkle(s, s.A, GROUP_PERMISSION, true));
        check("STOCK.non_owner_already_no_sparkle", !sparkle(s, s.B, GROUP_PERMISSION, false));
    }
    {
        Scene s;  // gold on the corpse
        s.kill({rowJunk()}, s.A);
        s.loot.gold = 50;
        check("SPARKLE.gold_kept_when_core_sparkles", sparkle(s, s.A, GROUP_PERMISSION, true) && SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION));
    }
    {
        Scene s;  // MULTI_DROP copies
        Scene::accept(s.A, FFA_QUEST);
        Scene::accept(s.B, FFA_QUEST);
        s.kill({rowFfaClaw()}, s.A);
        check("SPARKLE.ffa_copies_kept", sparkle(s, s.A, GROUP_PERMISSION, true) && sparkle(s, s.B, GROUP_PERMISSION, true));
    }
    {
        Scene s;  // Master Loot: master looter sees a MASTER quest row; A sees own row
        s.group.lootMethod = MASTER_LOOT;
        s.group.masterLooter = s.B.GetGUID();
        Scene::accept(s.A, Q_QUEST);
        s.kill({rowQuestSeed()}, s.A);
        check("SPARKLE.master_rows_kept", SG::ViewOffersSomething(&s.B, s.loot, MASTER_PERMISSION) &&
                                          SG::ViewOffersSomething(&s.A, s.loot, RESTRICTED_PERMISSION));
    }
    {
        Scene s;  // ordinary item shown LOCKED to a non-master looter: stock parity, kept
        s.group.lootMethod = MASTER_LOOT;
        s.group.masterLooter = s.A.GetGUID();
        s.kill({rowJunk()}, s.A);
        s.loot.items[0].is_blocked = true;  // Group::MasterLoot blocks over-threshold items (not executed here)
        s.loot.items[0].is_underthreshold = false;
        check("SPARKLE.master_locked_normal_row_kept", SG::ViewOffersSomething(&s.B, s.loot, RESTRICTED_PERMISSION));
    }
    {
        Scene s;
        s.kill({rowJunk()}, s.A);
        check("SPARKLE.no_rights_offers_nothing", !SG::ViewOffersSomething(&s.B, s.loot, NONE_PERMISSION) &&
                                                  !SG::ViewOffersSomething(nullptr, s.loot, GROUP_PERMISSION));
    }
}

// ---- The passive sparkle check must not change ANY loot state ----
struct LootSnapshot
{
    std::vector<int> rowsA, rowsB, questFlags, itemFlags;
    unsigned unlooted;
    uint32 gold;
    ObjectGuid roundRobin;
    bool operator==(LootSnapshot const& o) const
    {
        return rowsA == o.rowsA && rowsB == o.rowsB && questFlags == o.questFlags && itemFlags == o.itemFlags &&
               unlooted == o.unlooted && gold == o.gold && roundRobin == o.roundRobin;
    }
};

static std::vector<int> ownRows(Scene& s, Player& p)
{
    std::vector<int> out;
    auto it = s.loot.GetPlayerQuestItems().find(p.GetGUID());
    if (it != s.loot.GetPlayerQuestItems().end() && it->second)
        for (QuestItem const& r : *it->second)
            out.push_back(r.is_looted);
    return out;
}

static LootSnapshot snapshot(Scene& s)
{
    LootSnapshot snap;
    snap.rowsA = ownRows(s, s.A);
    snap.rowsB = ownRows(s, s.B);
    for (LootItem const& q : s.loot.quest_items)
        snap.questFlags.push_back(int(q.is_looted) | int(q.is_counted) << 1 | int(q.is_blocked) << 2);
    for (LootItem const& i : s.loot.items)
        snap.itemFlags.push_back(int(i.is_looted) | int(i.is_blocked) << 1 | int(i.is_underthreshold) << 2);
    snap.unlooted = s.loot.unlootedCount;
    snap.gold = s.loot.gold;
    snap.roundRobin = s.loot.roundRobinPlayer;
    return snap;
}

// Passive reads for both viewers before anyone opens the corpse.
static bool passiveReadsChangeNothing(Scene& s)
{
    LootSnapshot const before = snapshot(s);
    SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION);
    SG::ViewOffersSomething(&s.A, s.loot, GROUP_PERMISSION);
    return snapshot(s) == before;
}

static void hNoMutation()
{
    {
        Scene s;  // T1: B banked (the view guard helper WOULD mark B's row)
        Scene::accept(s.A, Q_QUEST);
        bankedB(s);
        s.kill({rowQuestSeed()}, s.A);
        check("NOMUT.T1_passive_reads_change_nothing", !ownRows(s, s.B).empty() && passiveReadsChangeNothing(s));
    }
    {
        Scene s;  // T3: B retrieved the seed after the corpse filled
        Scene::accept(s.A, Q_QUEST);
        bankedB(s);
        s.kill({rowQuestSeed()}, s.A);
        Scene::bankToBag(s.B, Q_ITEM);
        check("NOMUT.T3_passive_reads_change_nothing", passiveReadsChangeNothing(s));
    }
    {
        Scene s;  // MULTI_DROP with banked B
        Scene::accept(s.A, FFA_QUEST);
        Scene::accept(s.B, FFA_QUEST);
        Scene::gainToBags(s.B, FFA_ITEM);
        Scene::bagToBank(s.B, FFA_ITEM);
        s.kill({rowFfaClaw()}, s.A);
        check("NOMUT.ffa_passive_reads_change_nothing", passiveReadsChangeNothing(s));
    }
    {
        Scene s;  // B needs the seed again after a passive read: B must still get a real row
        Scene::accept(s.B, Q_QUEST);
        Scene::gainToBags(s.B, Q_ITEM);
        Scene::bagToBank(s.B, Q_ITEM);  // B banked one: not needed right now
        s.kill({rowQuestSeed()}, s.A);
        bool const hidden = !SG::ViewOffersSomething(&s.B, s.loot, GROUP_PERMISSION);
        s.B.bankCount[Q_ITEM] = 0;      // the banked seed is gone (e.g. destroyed): B needs it again
        auto b = s.open(s.B, GROUP_PERMISSION);
        check("NOMUT.B_needs_again_after_passive_read_gets_row_and_item",
              hidden && oneRow(b, Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT) && s.take(s.B, 0) && s.received(s.B, Q_ITEM) == 1);
    }
}

int main()
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    loadTemplates();
    hT3StaleLockedRow();
    hT1BankedViewer();
    hKeptCases();
    hNoMutation();
    std::printf("CHECKS %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
