// Seam equivalence matrix: the ORIGINAL prefix of pinned
// WorldSession::HandleLootMasterGiveOpcode against #272's ORIGINAL
// PermitMasterGive / CanPacketReceive bodies, in one stub environment.
//
// For every request: where the stock prefix rejects (error or silent
// return), the module must pass the packet through untouched, so the core
// still rejects it with its own reply. Where the stock prefix reaches the
// handler tail, the module must call GiveQuestSlot with the same leader,
// target, loot object and slot (the header then passes normal slots back).

#include "seam_env.h"

#include <cstdio>

std::map<ObjectGuid, Player*> ObjectAccessor::g_players;
std::vector<NaxxramasMasterLootQuestGive::Call> NaxxramasMasterLootQuestGive::g_calls;
NaxxramasMasterLootQuestGive::Outcome NaxxramasMasterLootQuestGive::g_next{
    NaxxramasMasterLootQuestGive::Result::PassThrough, LOOT_ERROR_DIDNT_KILL};

namespace MG = NaxxramasMasterLootQuestGive;

// ---- Original stock prefix (extracted by build_interop.py) ----
struct StockSession
{
    Player* _player{nullptr};
    Player* GetPlayer() { return _player; }

    bool tailReached{false};
    Loot* tailLoot{nullptr};
    Player* tailTarget{nullptr};
    uint8 tailSlot{0};

    void Handle(WorldPacket& recvData)
    {
#include "stock_prefix.inc"
        tailReached = true;
        tailLoot = loot;
        tailTarget = target;
        tailSlot = slotid;
    }
};

// ---- Original #272 module bodies (extracted by build_interop.py) ----
namespace
{
    std::atomic<bool> s_masterLootQuestGiveEnabled{false};
#include "module_permit.inc"
}

struct ModulePacketScript
{
#include "module_packet.inc"
};

// ---------------------------------------------------------------- fixture
static int g_pass = 0, g_fail = 0;
static void check(char const* id, bool ok)
{
    std::printf("CHECK %s %s\n", ok ? "PASS" : "FAIL", id);
    (ok ? g_pass : g_fail)++;
}

struct World
{
    Map map;
    Group group;
    Player M, A;
    Creature corpse;
    GameObject chest;
    ObjectGuid corpseGuid{ObjectGuid::High::Unit, 11};
    ObjectGuid chestGuid{ObjectGuid::High::GameObject, 22};
    WorldSession session;

    World()
    {
        M.guid = ObjectGuid(ObjectGuid::High::Player, 1);
        A.guid = ObjectGuid(ObjectGuid::High::Player, 2);
        for (Player* p : {&M, &A})
        {
            p->group = &group;
            p->map = &map;
            ObjectAccessor::g_players[p->guid] = p;
        }
        group.masterLooter = M.guid;
        group.method = MASTER_LOOT;
        M.lootGuid = corpseGuid;
        corpse.loot.items.resize(2);
        corpse.loot.quest_items.resize(2);
        chest.loot.items.resize(1);
        chest.loot.quest_items.resize(2);
        map.creatures[corpseGuid] = &corpse;
        map.gameObjects[chestGuid] = &chest;
        session.player = &M;
    }
    ~World() { ObjectAccessor::g_players.clear(); }

    WorldPacket give(ObjectGuid loot, uint8 slot, ObjectGuid target, uint32 opcode = CMSG_LOOT_MASTER_GIVE) const
    {
        WorldPacket p(opcode);
        p << loot << slot << target;
        return p;
    }
};

struct Case
{
    char const* id;
    void (*setup)(World&);
    uint8 slot;
    bool useChest;
    // Stock expectation: an error reply (code), a silent return (-1), or the tail (-2).
    int stockReply;
};

static void none(World&) { }

static Case const kCases[] = {
    {"SEAM.no_group", [](World& w) { w.M.group = nullptr; }, 2, false, LOOT_ERROR_DIDNT_KILL},
    {"SEAM.not_master_looter", [](World& w) { w.group.masterLooter = w.A.guid; }, 2, false, LOOT_ERROR_DIDNT_KILL},
    {"SEAM.group_loot_method", [](World& w) { w.group.method = GROUP_LOOT; }, 2, false, LOOT_ERROR_DIDNT_KILL},
    {"SEAM.need_before_greed_method", [](World& w) { w.group.method = NEED_BEFORE_GREED; }, 2, false, LOOT_ERROR_DIDNT_KILL},
    {"SEAM.free_for_all_method", [](World& w) { w.group.method = FREE_FOR_ALL; }, 2, false, LOOT_ERROR_DIDNT_KILL},
    {"SEAM.target_missing", [](World& w) { ObjectAccessor::g_players.erase(w.A.guid); }, 2, false, LOOT_ERROR_PLAYER_NOT_FOUND},
    {"SEAM.loot_guid_mismatch", [](World& w) { w.M.lootGuid = ObjectGuid(ObjectGuid::High::Unit, 99); }, 2, false, LOOT_ERROR_DIDNT_KILL},
    {"SEAM.not_in_raid", [](World& w) { w.M.inRaidWithTarget = false; }, 2, false, LOOT_ERROR_MASTER_OTHER},
    {"SEAM.target_no_play_time", [](World& w) { w.A.flags = PLAYER_FLAGS_NO_PLAY_TIME; }, 2, false, LOOT_ERROR_MASTER_OTHER},
    {"SEAM.creature_missing", [](World& w) { w.map.creatures.clear(); }, 2, false, -1},
    {"SEAM.gameobject_missing", [](World& w) { w.map.gameObjects.clear(); }, 1, true, -1},
    {"SEAM.creature_quest_slot_reaches_tail", none, 2, false, -2},
    {"SEAM.creature_normal_slot_reaches_tail", none, 0, false, -2},
    {"SEAM.gameobject_quest_slot_reaches_tail", none, 1, true, -2},
    {"SEAM.gameobject_normal_slot_reaches_tail", none, 0, true, -2},
    {"SEAM.slot_out_of_range_reaches_range_check", none, 4, false, -2},
};

static void runCase(Case const& c)
{
    // Stock prefix.
    World ws;
    if (c.useChest)
        ws.M.lootGuid = ws.chestGuid;
    c.setup(ws);
    StockSession stock;
    stock._player = &ws.M;
    WorldPacket sp = ws.give(c.useChest ? ws.chestGuid : ws.corpseGuid, c.slot, ws.A.guid);
    stock.Handle(sp);
    int stockReply = stock.tailReached ? -2 : (ws.M.replies.lootErrors.empty() ? -1 : ws.M.replies.lootErrors[0].second);

    // Module, same request on a fresh world.
    World wm;
    if (c.useChest)
        wm.M.lootGuid = wm.chestGuid;
    c.setup(wm);
    MG::g_calls.clear();
    MG::g_next = {MG::Result::Given, LOOT_ERROR_DIDNT_KILL};
    s_masterLootQuestGiveEnabled.store(true);
    ModulePacketScript script;
    WorldPacket mp = wm.give(c.useChest ? wm.chestGuid : wm.corpseGuid, c.slot, wm.A.guid);
    bool const moduleLetsCoreRun = script.CanPacketReceive(&wm.session, mp);
    bool const noModuleReply = wm.M.replies.lootErrors.empty() && wm.M.replies.equipErrors.empty();

    bool ok = stockReply == c.stockReply;
    Loot* expectLoot = c.useChest ? &wm.chest.loot : &wm.corpse.loot;
    std::size_t const range = expectLoot->items.size() + expectLoot->quest_items.size();
    if (c.stockReply != -2 || c.slot >= range)
        // Stock rejects (or the tail's own range check returns): the module must not act.
        ok = ok && moduleLetsCoreRun && MG::g_calls.empty() && noModuleReply;
    else
        // Stock reaches the tail: the module hands exactly the same request to GiveQuestSlot.
        ok = ok && !moduleLetsCoreRun && MG::g_calls.size() == 1 && MG::g_calls[0].leader == &wm.M &&
             MG::g_calls[0].target == &wm.A && MG::g_calls[0].loot == expectLoot && MG::g_calls[0].slot == c.slot &&
             stock.tailSlot == c.slot && stock.tailLoot == (c.useChest ? &ws.chest.loot : &ws.corpse.loot) &&
             stock.tailTarget == &ws.A;
    check(c.id, ok);
}

// How #272 turns each header outcome into a reply.
static void outcomeMapping()
{
    struct Map_ { char const* id; MG::Outcome outcome; bool letsCoreRun; int lootError; int equipError; };
    Map_ const rows[] = {
        {"REPLY.pass_through_lets_core_run", {MG::Result::PassThrough, LOOT_ERROR_DIDNT_KILL}, true, -1, -1},
        {"REPLY.given_consumes_silently", {MG::Result::Given, LOOT_ERROR_DIDNT_KILL}, false, -1, -1},
        {"REPLY.already_looted_equip_error", {MG::Result::AlreadyLooted, LOOT_ERROR_DIDNT_KILL}, false, -1, EQUIP_ERR_ALREADY_LOOTED},
        {"REPLY.error_inv_full_with_loot_guid", {MG::Result::Error, LOOT_ERROR_MASTER_INV_FULL}, false, LOOT_ERROR_MASTER_INV_FULL, -1},
        {"REPLY.error_unique_with_loot_guid", {MG::Result::Error, LOOT_ERROR_MASTER_UNIQUE_ITEM}, false, LOOT_ERROR_MASTER_UNIQUE_ITEM, -1},
        {"REPLY.error_other_with_loot_guid", {MG::Result::Error, LOOT_ERROR_MASTER_OTHER}, false, LOOT_ERROR_MASTER_OTHER, -1},
    };
    for (Map_ const& r : rows)
    {
        World w;
        MG::g_calls.clear();
        MG::g_next = r.outcome;
        bool const lets = PermitMasterGive(&w.M, w.corpseGuid, 2, w.A.guid);
        bool ok = lets == r.letsCoreRun && MG::g_calls.size() == 1;
        if (r.lootError >= 0)
            ok = ok && w.M.replies.lootErrors.size() == 1 && w.M.replies.lootErrors[0].first == w.corpseGuid.GetRawValue() &&
                 w.M.replies.lootErrors[0].second == r.lootError && w.M.replies.equipErrors.empty();
        else if (r.equipError >= 0)
            ok = ok && w.M.replies.equipErrors == std::vector<int>{r.equipError} && w.M.replies.lootErrors.empty();
        else
            ok = ok && w.M.replies.lootErrors.empty() && w.M.replies.equipErrors.empty();
        check(r.id, ok);
    }
}

// The packet filter in front of PermitMasterGive.
static void packetFilter()
{
    ModulePacketScript script;
    {
        World w;
        MG::g_calls.clear();
        s_masterLootQuestGiveEnabled.store(false);
        WorldPacket p = w.give(w.corpseGuid, 2, w.A.guid);
        check("FILTER.disabled_lets_core_run", script.CanPacketReceive(&w.session, p) && MG::g_calls.empty());
    }
    {
        World w;
        MG::g_calls.clear();
        s_masterLootQuestGiveEnabled.store(true);
        WorldPacket p = w.give(w.corpseGuid, 2, w.A.guid, CMSG_AUTOSTORE_LOOT_ITEM);
        check("FILTER.other_opcode_untouched", script.CanPacketReceive(&w.session, p) && MG::g_calls.empty());
    }
    {
        World w;
        MG::g_calls.clear();
        s_masterLootQuestGiveEnabled.store(true);
        WorldPacket p(CMSG_LOOT_MASTER_GIVE);
        p << w.corpseGuid << uint8(2);  // 9 of 17 bytes
        check("FILTER.short_packet_left_to_core", script.CanPacketReceive(&w.session, p) && MG::g_calls.empty());
    }
    {
        World w;
        MG::g_calls.clear();
        s_masterLootQuestGiveEnabled.store(true);
        w.session.player = nullptr;
        WorldPacket p = w.give(w.corpseGuid, 2, w.A.guid);
        check("FILTER.no_player_left_to_core", script.CanPacketReceive(&w.session, p) && MG::g_calls.empty());
    }
    {
        World w;
        MG::g_calls.clear();
        s_masterLootQuestGiveEnabled.store(true);
        w.M.inWorld = false;
        WorldPacket p = w.give(w.corpseGuid, 2, w.A.guid);
        check("FILTER.not_in_world_left_to_core", script.CanPacketReceive(&w.session, p) && MG::g_calls.empty());
    }
    {
        World w;  // field order: loot GUID, slot, target GUID (as the handler reads them)
        MG::g_calls.clear();
        MG::g_next = {MG::Result::Given, LOOT_ERROR_DIDNT_KILL};
        s_masterLootQuestGiveEnabled.store(true);
        WorldPacket p = w.give(w.corpseGuid, 3, w.A.guid);
        p << uint8(0xEE);  // trailing byte, ignored like the handler does
        bool const lets = script.CanPacketReceive(&w.session, p);
        check("FILTER.reads_loot_slot_target_in_handler_order",
              !lets && MG::g_calls.size() == 1 && MG::g_calls[0].slot == 3 && MG::g_calls[0].target == &w.A &&
              MG::g_calls[0].loot == &w.corpse.loot);
    }
}

int main()
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    for (Case const& c : kCases)
        runCase(c);
    outcomeMapping();
    packetFilter();
    std::printf("CHECKS %d passed, %d failed\n", g_pass, g_fail);
    return g_fail == 0 ? 0 : 1;
}
