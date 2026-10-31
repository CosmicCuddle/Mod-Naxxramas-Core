// A04 extracted-pinned-source harness: scenario driver.
//
// Runs the ORIGINAL pinned Grimfeather 8daffda loot/quest bodies (generated
// pinned_bodies.cpp) for two human players A and B in one party. This file
// only arranges state, calls the original functions in the order the server
// calls them, decodes the original SMSG_LOOT_RESPONSE bytes and records what
// happened. It contains no loot or quest decision logic.
//
// Not executed (named stand-ins, see the doc): Player::SendLoot itself (the
// harness performs its two loot steps: serialize LootView, then AddLooter),
// WorldSession::HandleAutostoreLootItemOpcode (creature path only finds the
// loot and calls StoreLootItem), Group::GroupLoot/MasterLoot rolls,
// LootTemplate::Process/Roll (the 100% row is taken as dropped), real item
// storage (Player::SwapItem/StoreItem/BankItem: counters only, with the
// original Item{Added,Removed}QuestCheck), UNIT_DYNFLAG_LOOTABLE serialization.

#include "harness_env.h"
#include "pinned_fixture.h"

#include <cstdlib>
#include <memory>

ObjectMgrStub g_objectMgr;
DisableMgrStub g_disableMgr;
ConditionMgrStub g_conditionMgr;
ScriptMgrStub g_scriptMgr;
LootItemStorageStub g_lootItemStorage;

// Assertion-failure path of the pinned Errors.h (never reached when tests pass).
void Acore::Assert(std::string_view file, uint32 line, std::string_view, std::string_view, std::string_view message, std::string_view)
{
    std::fprintf(stderr, "ASSERT FAILED %.*s:%u %.*s\n", int(file.size()), file.data(), line, int(message.size()), message.data());
    std::abort();
}
std::string GetDebugInfo() { return {}; }

static std::map<ObjectGuid, Player*> g_players;
Player* ObjectAccessor::FindPlayer(ObjectGuid guid)
{
    auto it = g_players.find(guid);
    return it == g_players.end() ? nullptr : it->second;
}

bool Player::CanCompleteQuest(uint32 q) const
{
    Quest const* quest = g_objectMgr.GetQuestTemplate(q);
    auto it = m_QuestStatus.find(q);
    if (!quest || it == m_QuestStatus.end())
        return false;
    for (int j = 0; j < QUEST_ITEM_OBJECTIVES_COUNT; ++j)
        if (quest->RequiredItemCount[j] && it->second.ItemCount[j] < quest->RequiredItemCount[j])
            return false;
    return true;
}

// LootTemplate::Process and LootStore lookups are not under test: the fixture
// template holds the loot rows, and Process hands each one to the ORIGINAL
// Loot::AddItem, which is what the real Process does once a row drops.
static std::vector<LootStoreItem> g_templateRows;
static LootTemplate* g_template = nullptr;
void LootTemplate::Process(Loot& loot, LootStore const&, uint16, Player const*, uint8, bool) const
{
    for (LootStoreItem const& row : g_templateRows)
        loot.AddItem(row);
}
LootTemplate const* LootStore::GetLootFor(uint32) const { return g_template; }
void LootStore::Clear() {}
LootTemplate::~LootTemplate() {}

// ---------------------------------------------------------------- checks
static int g_pass = 0, g_fail = 0;
static void check(char const* id, bool ok)
{
    std::printf("CHECK %s %s\n", ok ? "PASS" : "FAIL", id);
    (ok ? g_pass : g_fail)++;
}

// ---------------------------------------------------------------- fixture data
static ItemTemplate itemFromRow(pinned::ItemRow const& r)
{
    ItemTemplate t{};
    t.ItemId = r.entry;
    t.Class = r.cls;
    t.Quality = r.quality;
    t.Flags = ItemFlags(r.flags);
    t.Flags2 = ItemFlags2(r.flagsExtra);
    t.FlagsCu = ItemFlagsCustom(r.flagsCustom);
    t.Bonding = r.bonding;
    t.StartQuest = r.startquest;
    t.RequiredSkill = r.requiredSkill;
    t.DisplayInfoID = r.displayid;
    t.BagFamily = r.bagFamily;
    t.MaxCount = r.maxcount;
    t.Stackable = r.stackable;
    t.Name1 = r.name;
    return t;
}

static Quest questFromRow(pinned::QuestRow const& r)
{
    Quest q;
    q.Id = r.id;
    q.PrevQuestId = int32(r.prevQuestId);
    // ObjectMgr::LoadQuests adds DELIVER to every quest with a required item.
    q.SpecialFlags = r.specialFlags | QUEST_SPECIAL_FLAGS_DELIVER;
    for (int j = 0; j < 6; ++j)
    {
        q.RequiredItemId[j] = r.requiredItemId[j];
        q.RequiredItemCount[j] = r.requiredItemCount[j];
    }
    for (int j = 0; j < 4; ++j)
    {
        q.ItemDrop[j] = r.itemDrop[j];
        q.ItemDropQuantity[j] = r.itemDropQuantity[j];
    }
    return q;
}

constexpr uint32 Q_ITEM = pinned::ITEM_5168.entry;      // Timberling Seed
constexpr uint32 Q_QUEST = pinned::QUEST_922.id;        // Rellian Greenspyre
constexpr uint32 FFA_ITEM = pinned::ITEM_1931.entry;    // Huge Gnoll Claw (MULTI_DROP)
constexpr uint32 FFA_QUEST = pinned::QUEST_176.id;      // Wanted: Hogger
constexpr uint32 ORDINARY_ITEM = 900001;                // synthetic poor-quality junk item
constexpr uint32 T5_ITEM = 900002;                      // synthetic quest item, does not stack
constexpr uint32 T5_QUEST = 900003;                     // synthetic quest: deliver 2 x T5_ITEM

static void loadTemplates()
{
    g_objectMgr.items[Q_ITEM] = itemFromRow(pinned::ITEM_5168);
    g_objectMgr.items[FFA_ITEM] = itemFromRow(pinned::ITEM_1931);
    ItemTemplate junk{};
    junk.ItemId = ORDINARY_ITEM;
    junk.Quality = ITEM_QUALITY_POOR;
    junk.Stackable = 1;
    junk.Name1 = "synthetic ordinary item";
    g_objectMgr.items[ORDINARY_ITEM] = junk;
    ItemTemplate t5{};
    t5.ItemId = T5_ITEM;
    t5.Class = ITEM_CLASS_QUEST;
    t5.Quality = ITEM_QUALITY_NORMAL;
    t5.Bonding = BIND_QUEST_ITEM;
    t5.Stackable = 1;
    t5.Name1 = "synthetic two-slot quest item";
    g_objectMgr.items[T5_ITEM] = t5;
    Quest t5q;
    t5q.Id = T5_QUEST;
    t5q.SpecialFlags = QUEST_SPECIAL_FLAGS_DELIVER;
    t5q.RequiredItemId[0] = T5_ITEM;
    t5q.RequiredItemCount[0] = 2;
    g_objectMgr.quests[T5_QUEST] = t5q;
    g_objectMgr.quests[Q_QUEST] = questFromRow(pinned::QUEST_922);
    g_objectMgr.quests[FFA_QUEST] = questFromRow(pinned::QUEST_176);
}

static LootStoreItem rowQuestSeed()
{
    auto const& l = pinned::LOOT_2030_5168;
    return LootStoreItem(l.item, l.reference, l.chance, l.questRequired != 0, uint16(l.lootMode),
                         uint8(l.groupId), int32(l.minCount), uint8(l.maxCount));
}
// Item and quest rows are pinned; this loot row is synthetic (1931 is used only
// as the MULTI_DROP control).
static LootStoreItem rowFfaClaw() { return LootStoreItem(FFA_ITEM, 0, 100.0f, true, 1, 0, 1, 1); }
static LootStoreItem rowJunk() { return LootStoreItem(ORDINARY_ITEM, 0, 100.0f, false, 1, 0, 1, 1); }
static LootStoreItem rowT5() { return LootStoreItem(T5_ITEM, 0, 100.0f, true, 1, 0, 1, 1); }

// ---------------------------------------------------------------- one corpse
struct Row { int slot; uint32 item; int slotType; };

struct Scene
{
    Player A, B;
    Group group;
    Loot loot;
    LootStore store{"creature_loot_template", "creature entry", true};
    ObjectGuid corpse = ObjectGuid::Create<HighGuid::Unit>(pinned::LOOT_2030_5168.entry, 1);

    Scene()
    {
        A.guid = ObjectGuid::Create<HighGuid::Player>(1);
        A.name = "A";
        B.guid = ObjectGuid::Create<HighGuid::Player>(2);
        B.name = "B";
        for (Player* p : {&A, &B})
        {
            p->group = &group;
            p->rewardedQuests.insert(pinned::QUEST_922.prevQuestId);  // prerequisite 918 done
            g_players[p->guid] = p;
        }
        group.SetMembers({&A, &B});
        loot.sourceWorldObjectGUID = corpse;
    }
    ~Scene()
    {
        g_players.erase(A.guid);
        g_players.erase(B.guid);
    }

    static void accept(Player& p, uint32 quest, int slot = 0)
    {
        p.questSlots[slot] = quest;
        p.m_QuestStatus[quest].Status = QUEST_STATUS_INCOMPLETE;
    }
    // Item reaches the bags (StoreNewItem path), then the original counter check runs.
    static void gainToBags(Player& p, uint32 item)
    {
        p.bagCount[item] += 1;
        p.ItemAddedQuestCheck(item, 1);
    }
    // Player::SwapItem bag -> empty bank slot: RemoveItem, BankItem, then the
    // original ItemRemovedQuestCheck (PlayerStorage.cpp, SwapItem body).
    static void bagToBank(Player& p, uint32 item)
    {
        p.bagCount[item] -= 1;
        p.bankCount[item] += 1;
        p.ItemRemovedQuestCheck(item, 1);
    }
    // Player::SwapItem bank -> bag: RemoveItem, StoreItem, then the original
    // ItemAddedQuestCheck because the source was a bank slot.
    static void bankToBag(Player& p, uint32 item)
    {
        p.bankCount[item] -= 1;
        p.bagCount[item] += 1;
        p.ItemAddedQuestCheck(item, 1);
    }

    void kill(std::vector<LootStoreItem> rows, Player& owner)
    {
        g_templateRows = std::move(rows);
        static LootTemplate tmpl;
        g_template = &tmpl;
        loot.FillLoot(pinned::LOOT_2030_5168.entry, store, &owner, false, false, LOOT_MODE_DEFAULT, nullptr);
    }

    // The loot steps of Player::SendLoot: original LootView serialization, then AddLooter.
    std::vector<Row> open(Player& p, PermissionTypes perm)
    {
        p.lootGuid = corpse;
        ByteBuffer b;
        b << LootView(loot, &p, perm);
        loot.AddLooter(p.GetGUID());
        std::vector<Row> rows;
        uint32 gold = b.read<uint32>();
        (void)gold;
        uint8 n = b.read<uint8>();
        for (uint8 i = 0; i < n; ++i)
        {
            Row r{};
            r.slot = b.read<uint8>();
            r.item = b.read<uint32>();
            b.read<uint32>();  // count
            b.read<uint32>();  // display id
            b.read<uint32>();  // random suffix
            b.read<uint32>();  // random property
            r.slotType = b.read<uint8>();
            rows.push_back(r);
        }
        return rows;
    }

    // The creature branch of HandleAutostoreLootItemOpcode ends in this call.
    bool take(Player& p, uint8 slot)
    {
        p.lootGuid = corpse;
        size_t before = p.ev.received.size();
        InventoryResult msg;
        p.StoreLootItem(slot, &loot, msg);
        return p.ev.received.size() > before;
    }

    LootItem& q(size_t i = 0) { return loot.quest_items.at(i); }
    bool inQuestList(Player& p) { return loot.GetPlayerQuestItems().count(p.GetGUID()) != 0; }
    bool ownQuestRowLooted(Player& p)
    {
        auto it = loot.GetPlayerQuestItems().find(p.GetGUID());
        return it != loot.GetPlayerQuestItems().end() && !it->second->empty() && it->second->at(0).is_looted;
    }
    uint32 received(Player& p, uint32 item)
    {
        uint32 n = 0;
        for (auto const& r : p.ev.received)
            if (r.first == item)
                n += r.second;
        return n;
    }
    void obs(char const* tag)
    {
        std::printf("OBS %s q.is_looted=%d q.is_counted=%d unlooted=%u isLooted=%d hasItemFor(A)=%d hasItemFor(B)=%d "
                    "A{list=%d own_looted=%d got=%u} B{list=%d own_looted=%d got=%u}\n",
                    tag, loot.quest_items.empty() ? -1 : int(q().is_looted), loot.quest_items.empty() ? -1 : int(q().is_counted),
                    unsigned(loot.unlootedCount), int(loot.isLooted()), int(loot.hasItemFor(&A)), int(loot.hasItemFor(&B)),
                    int(inQuestList(A)), int(ownQuestRowLooted(A)), received(A, Q_ITEM),
                    int(inQuestList(B)), int(ownQuestRowLooted(B)), received(B, Q_ITEM));
    }
};

static bool oneRow(std::vector<Row> const& rows, uint32 item, int slotType)
{
    return rows.size() == 1 && rows[0].item == item && rows[0].slotType == slotType;
}

// B did quest 922's item step, then legally banked the seed: counter 0, INCOMPLETE, bank 1.
static void bankedB(Scene& s)
{
    Scene::accept(s.B, Q_QUEST);
    Scene::gainToBags(s.B, Q_ITEM);
    Scene::bagToBank(s.B, Q_ITEM);
}

// ---------------------------------------------------------------- cases
static void t0()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    s.kill({rowQuestSeed()}, s.A);
    s.obs("T0.filled");
    check("T0.fill_counts_one_shared_quest_item", s.loot.unlootedCount == 1 && s.q().is_counted && !s.q().freeforall);
    check("T0.only_A_in_quest_list", s.inQuestList(s.A) && !s.inQuestList(s.B));
    auto a = s.open(s.A, GROUP_PERMISSION);
    auto b = s.open(s.B, GROUP_PERMISSION);
    check("T0.A_sees_allow_loot_row", oneRow(a, Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
    check("T0.B_sees_no_row", b.empty());
    check("T0.H1neg_B_direct_store_gets_nothing", !s.take(s.B, 0) && s.received(s.B, Q_ITEM) == 0);
    check("T0.A_store_awards_exactly_one", s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 1);
    s.obs("T0.after_A_take");
    check("T0.counts_settle_corpse_looted", s.loot.unlootedCount == 0 && s.loot.isLooted() && s.q().is_looted);
    check("T0.A_quest_counter_unchanged_by_loot_store", s.A.m_QuestStatus[Q_QUEST].ItemCount[0] == 0);
}

static void h1QuestCompleteB()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    Scene::accept(s.B, Q_QUEST);
    Scene::gainToBags(s.B, Q_ITEM);  // B already holds the seed in bags: COMPLETE
    check("H1neg.B_complete_after_original_counter", s.B.GetQuestStatus(Q_QUEST) == QUEST_STATUS_COMPLETE);
    s.kill({rowQuestSeed()}, s.A);
    check("H1neg.complete_B_not_in_quest_list", !s.inQuestList(s.B));
    check("H1neg.complete_B_sees_no_row", s.open(s.B, GROUP_PERMISSION).empty());
    check("H1neg.complete_B_direct_store_gets_nothing", !s.take(s.B, 0));
    check("H1neg.A_still_awarded", s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 1);
}

static void t1()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    bankedB(s);
    check("T1.setup_B_banked_counter0_incomplete",
          s.B.m_QuestStatus[Q_QUEST].ItemCount[0] == 0 && s.B.GetQuestStatus(Q_QUEST) == QUEST_STATUS_INCOMPLETE &&
          s.B.GetItemCount(Q_ITEM, true) == 1 && s.B.GetItemCount(Q_ITEM, false) == 0);
    s.kill({rowQuestSeed()}, s.A);
    check("T1.both_in_quest_list_one_count", s.inQuestList(s.A) && s.inQuestList(s.B) && s.loot.unlootedCount == 1);
    auto a = s.open(s.A, GROUP_PERMISSION);
    check("T1.A_sees_allow_loot_row", oneRow(a, Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
    auto b = s.open(s.B, GROUP_PERMISSION);
    s.obs("T1.after_B_view");
    check("T1.B_view_shows_no_row", b.empty());
    check("T1.WITNESS_B_view_marks_shared_item_looted", s.q().is_looted && s.ownQuestRowLooted(s.B));
    check("T1.WITNESS_no_award_no_count_change", s.received(s.B, Q_ITEM) == 0 && s.loot.unlootedCount == 1);
    check("T1.WITNESS_A_stale_row_store_denied", !s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 0);
    // Stock hook default: no ALREADY_LOOTED error, no release: the click just does nothing.
    check("T1.WITNESS_A_denial_is_silent", s.A.ev.equipErrors.empty() && s.A.ev.lootReleases == 0);
    s.obs("T1.after_A_take");
    check("T1.WITNESS_corpse_never_reaches_isLooted", !s.loot.isLooted() && !s.loot.hasItemFor(&s.A));
    check("T1.no_phantom_award_to_anyone", s.received(s.A, Q_ITEM) + s.received(s.B, Q_ITEM) == 0);
}

static void t2()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    bankedB(s);
    s.kill({rowQuestSeed()}, s.A);
    check("T2.B_first_view_shows_no_row", s.open(s.B, GROUP_PERMISSION).empty());
    check("T2.WITNESS_shared_item_marked_looted_by_view", s.q().is_looted);
    auto a = s.open(s.A, GROUP_PERMISSION);
    s.obs("T2.after_A_view");
    check("T2.WITNESS_A_sees_no_row_despite_need",
          a.empty() && s.A.HasQuestForItem(Q_ITEM) && s.inQuestList(s.A) && !s.ownQuestRowLooted(s.A));
    check("T2.WITNESS_A_store_denied", !s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 0);
    check("T2.WITNESS_count_left_at_one", s.loot.unlootedCount == 1 && !s.loot.isLooted());
}

static void t3()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    bankedB(s);
    s.kill({rowQuestSeed()}, s.A);
    Scene::bankToBag(s.B, Q_ITEM);  // B retrieves the seed after the corpse filled
    check("T3.B_complete_after_retrieval", s.B.GetQuestStatus(Q_QUEST) == QUEST_STATUS_COMPLETE &&
                                           s.B.m_QuestStatus[Q_QUEST].ItemCount[0] == 1);
    check("T3.B_cached_quest_slot_persists", s.inQuestList(s.B));
    auto b = s.open(s.B, GROUP_PERMISSION);
    s.obs("T3.after_B_view");
    check("T3.WITNESS_H2_B_sees_locked_row", oneRow(b, Q_ITEM, LOOT_SLOT_TYPE_LOCKED));
    check("T3.locked_view_does_not_mark_shared", !s.q().is_looted);
    size_t releases = s.B.ev.lootReleases;
    check("T3.WITNESS_H2_B_store_denied_with_release", !s.take(s.B, 0) && s.B.ev.lootReleases == releases + 1);
    check("T3.A_sees_allow_loot_row", oneRow(s.open(s.A, GROUP_PERMISSION), Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
    check("T3.A_right_preserved", s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 1 && s.loot.isLooted());
}

static void t4()
{
    for (int bFirst = 0; bFirst < 2; ++bFirst)
    {
        Scene s;
        Scene::accept(s.A, Q_QUEST);
        Scene::accept(s.B, Q_QUEST);
        s.kill({rowQuestSeed()}, s.A);  // A is loot owner / round-robin player
        check(bFirst ? "T4b.round_robin_is_A" : "T4a.round_robin_is_A", s.loot.roundRobinPlayer == s.A.GetGUID());
        auto a = s.open(s.A, GROUP_PERMISSION);
        auto b = s.open(s.B, GROUP_PERMISSION);
        check(bFirst ? "T4b.both_see_allow_loot_row" : "T4a.both_see_allow_loot_row",
              oneRow(a, Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT) && oneRow(b, Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
        Player& first = bFirst ? s.B : s.A;
        Player& second = bFirst ? s.A : s.B;
        bool firstGot = s.take(first, 0);
        bool secondGot = s.take(second, 0);
        s.obs(bFirst ? "T4b.after_both_take" : "T4a.after_both_take");
        check(bFirst ? "T4b.STOCK_first_eligible_taker_gets_single_copy" : "T4a.STOCK_first_eligible_taker_gets_single_copy",
              firstGot && !secondGot && s.received(first, Q_ITEM) == 1 && s.received(second, Q_ITEM) == 0);
        check(bFirst ? "T4b.other_looter_told_slot_removed" : "T4a.other_looter_told_slot_removed",
              !second.ev.removedSlots.empty() && s.loot.isLooted());
    }
}

// Observation O1: the bank check lives only in the view path.
static void o1()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    bankedB(s);
    s.kill({rowQuestSeed()}, s.A);
    bool got = s.take(s.B, 0);  // no CMSG_LOOT view first
    s.obs("O1.after_B_store_without_view");
    check("O1.STOCK_banked_B_store_without_view_is_awarded", got && s.received(s.B, Q_ITEM) == 1);
    check("O1.then_A_denied", !s.take(s.A, 0));
}

// T5 (optional, counter level, synthetic 2-count quest): B holds two separate
// Q x1 bag slots, objective 2/2, then moves ONE whole slot to the bank in the
// pinned SwapItem order (RemoveItem, BankItem, ItemRemovedQuestCheck).
static void t5()
{
    Scene s;
    Scene::accept(s.A, T5_QUEST);
    Scene::accept(s.B, T5_QUEST);
    Scene::gainToBags(s.B, T5_ITEM);
    Scene::gainToBags(s.B, T5_ITEM);
    bool complete = s.B.GetQuestStatus(T5_QUEST) == QUEST_STATUS_COMPLETE && s.B.m_QuestStatus[T5_QUEST].ItemCount[0] == 2;
    Scene::bagToBank(s.B, T5_ITEM);
    s.obs("T5.after_one_slot_to_bank");
    check("T5.WITNESS_whole_slot_move_double_subtracts",
          complete && s.B.GetItemCount(T5_ITEM, false) == 1 && s.B.GetItemCount(T5_ITEM, true) == 2 &&
          s.B.m_QuestStatus[T5_QUEST].ItemCount[0] == 0 && s.B.GetQuestStatus(T5_QUEST) == QUEST_STATUS_INCOMPLETE);
    s.kill({rowT5()}, s.A);
    check("T5.B_listed_for_item_it_already_holds", s.inQuestList(s.B) && s.inQuestList(s.A));
    s.open(s.B, GROUP_PERMISSION);
    check("T5.B_view_then_marks_shared_looted_A_denied", s.q().is_looted && !s.take(s.A, 0));
}

static void cFfa()
{
    for (int bothNeed = 0; bothNeed < 2; ++bothNeed)
    {
        Scene s;
        Scene::accept(s.A, FFA_QUEST);
        Scene::accept(s.B, FFA_QUEST);
        if (!bothNeed)
        {
            Scene::gainToBags(s.B, FFA_ITEM);
            Scene::bagToBank(s.B, FFA_ITEM);
        }
        s.kill({rowFfaClaw()}, s.A);
        check(bothNeed ? "C1b.multi_drop_is_freeforall" : "C1a.multi_drop_is_freeforall", s.q().freeforall);
        if (!bothNeed)
        {
            check("C1a.banked_B_view_shows_no_row", s.open(s.B, GROUP_PERMISSION).empty());
            check("C1a.ffa_not_marked_looted_by_view", !s.q().is_looted && s.ownQuestRowLooted(s.B));
            check("C1a.A_still_awarded", s.take(s.A, 0) && s.received(s.A, FFA_ITEM) == 1);
        }
        else
        {
            check("C1b.A_awarded_copy", s.take(s.A, 0) && s.received(s.A, FFA_ITEM) == 1);
            check("C1b.B_awarded_own_copy", s.take(s.B, 0) && s.received(s.B, FFA_ITEM) == 1);
            check("C1b.copies_settle_corpse", s.loot.isLooted());
        }
    }
}

// Ordinary below-threshold item under group loot (round-robin owner A).
static void cOrdinary()
{
    Scene s;
    s.kill({rowJunk()}, s.A);
    check("C2.under_threshold_counted_once", s.loot.items.size() == 1 && s.loot.items[0].is_underthreshold && s.loot.unlootedCount == 1);
    check("C2.A_round_robin_sees_row", oneRow(s.open(s.A, GROUP_PERMISSION), ORDINARY_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
    check("C2.B_view_hides_round_robin_row", s.open(s.B, GROUP_PERMISSION).empty());
    // Observation O2: StoreLootItem does not re-check round robin.
    bool got = s.take(s.B, 0);
    check("C2.O2_STOCK_B_direct_store_of_hidden_row_succeeds", got && s.received(s.B, ORDINARY_ITEM) == 1);
    check("C2.A_then_already_looted", !s.take(s.A, 0));
}

static void cMaster()
{
    Scene s;
    s.group.lootMethod = MASTER_LOOT;
    s.group.masterLooter = s.B.GetGUID();  // B is master looter and has no quest
    Scene::accept(s.A, Q_QUEST);
    s.kill({rowQuestSeed()}, s.A);
    check("C3.master_looter_listed_without_right", s.inQuestList(s.B) && !s.q().GetAllowedLooters().count(s.B.GetGUID()));
    check("C3.master_sees_master_row", oneRow(s.open(s.B, MASTER_PERMISSION), Q_ITEM, LOOT_SLOT_TYPE_MASTER));
    check("C3.master_self_store_denied", !s.take(s.B, 0));
    check("C3.A_sees_allow_loot_row", oneRow(s.open(s.A, RESTRICTED_PERMISSION), Q_ITEM, LOOT_SLOT_TYPE_ALLOW_LOOT));
    check("C3.A_awarded", s.take(s.A, 0) && s.received(s.A, Q_ITEM) == 1);
}

static void cGold()
{
    Scene s;
    Scene::accept(s.A, Q_QUEST);
    bankedB(s);
    s.kill({rowQuestSeed()}, s.A);
    s.loot.gold = 50;
    s.open(s.B, GROUP_PERMISSION);  // T1 mutation happens
    check("C4.gold_keeps_loot_for_all", s.loot.hasItemForAll() && !s.loot.isLooted());
}

int main()
{
    loadTemplates();
    check("FIXTURE.pinned_rows", pinned::LOOT_2030_5168.questRequired == 1 && pinned::LOOT_2030_5168.chance == 100.0f &&
                                 pinned::ITEM_5168.flags == 0 && pinned::ITEM_1931.flags == ITEM_FLAG_MULTI_DROP &&
                                 pinned::QUEST_922.requiredItemId[0] == Q_ITEM && pinned::QUEST_922.requiredItemCount[0] == 1 &&
                                 pinned::QUEST_922.prevQuestId == 918);
    t0();
    h1QuestCompleteB();
    t1();
    t2();
    t3();
    t4();
    o1();
    t5();
    cFfa();
    cOrdinary();
    cMaster();
    cGold();
    std::printf("CHECKS %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
