// Minimal stand-ins for the collaborators of two ORIGINAL code fragments:
//  - the prefix of pinned WorldSession::HandleLootMasterGiveOpcode (its own
//    checks, before the slot range check), and
//  - #272's PermitMasterGive and CanPacketReceive bodies.
// build_interop.py extracts both byte for byte; this header only supplies
// what they call. Every call is recorded so the harness can compare them.
#ifndef P4_H_INTEROP_SEAM_ENV_H
#define P4_H_INTEROP_SEAM_ENV_H

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <map>
#include <string>
#include <vector>

using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
using uint64 = std::uint64_t;

#define LOG_DEBUG(...) ((void)0)

// Values as in pinned SharedDefines.h / LootMgr.h / Item.h / Opcodes.h
// (test_p4_h_interop.py checks the lines).
enum LootMethod : uint8 { FREE_FOR_ALL = 0, ROUND_ROBIN = 1, MASTER_LOOT = 2, GROUP_LOOT = 3, NEED_BEFORE_GREED = 4 };
enum LootError : uint8
{
    LOOT_ERROR_DIDNT_KILL = 0,
    LOOT_ERROR_PLAYER_NOT_FOUND = 10,
    LOOT_ERROR_MASTER_INV_FULL = 12,
    LOOT_ERROR_MASTER_UNIQUE_ITEM = 13,
    LOOT_ERROR_MASTER_OTHER = 14,
};
enum InventoryResult : uint8 { EQUIP_ERR_OK = 0, EQUIP_ERR_ALREADY_LOOTED = 49 };
enum PlayerFlags : uint32 { PLAYER_FLAGS_NO_PLAY_TIME = 0x00002000 };
enum Opcodes : uint32 { CMSG_AUTOSTORE_LOOT_ITEM = 0x108, CMSG_LOOT_MASTER_GIVE = 0x2A3 };

class ObjectGuid
{
public:
    enum class High : uint8 { None, Player, Unit, Vehicle, GameObject };
    ObjectGuid() = default;
    ObjectGuid(High h, uint64 low) : _raw((uint64(h) << 56) | low) { }
    explicit ObjectGuid(uint64 raw) : _raw(raw) { }
    [[nodiscard]] uint64 GetRawValue() const { return _raw; }
    [[nodiscard]] High GetHigh() const { return High(_raw >> 56); }
    [[nodiscard]] bool IsCreatureOrVehicle() const { return GetHigh() == High::Unit || GetHigh() == High::Vehicle; }
    [[nodiscard]] bool IsGameObject() const { return GetHigh() == High::GameObject; }
    bool operator==(ObjectGuid const& o) const { return _raw == o._raw; }
    bool operator!=(ObjectGuid const& o) const { return _raw != o._raw; }
    bool operator<(ObjectGuid const& o) const { return _raw < o._raw; }
private:
    uint64 _raw{0};
};

class WorldPacket
{
public:
    explicit WorldPacket(uint32 opcode = 0) : _opcode(opcode) { }
    [[nodiscard]] uint32 GetOpcode() const { return _opcode; }
    [[nodiscard]] std::size_t size() const { return _data.size(); }
    void rpos(std::size_t p) { _rpos = p; }
    WorldPacket& operator<<(uint8 v) { _data.push_back(v); return *this; }
    WorldPacket& operator<<(ObjectGuid g)
    {
        uint64 raw = g.GetRawValue();
        for (int i = 0; i < 8; ++i)
            _data.push_back(uint8(raw >> (8 * i)));
        return *this;
    }
    WorldPacket& operator>>(uint8& v) { v = _rpos < _data.size() ? _data[_rpos] : 0; ++_rpos; return *this; }
    WorldPacket& operator>>(ObjectGuid& g)
    {
        uint64 raw = 0;
        for (int i = 0; i < 8; ++i, ++_rpos)
            raw |= uint64(_rpos < _data.size() ? _data[_rpos] : 0) << (8 * i);
        g = ObjectGuid(raw);
        return *this;
    }
private:
    uint32 _opcode;
    std::vector<uint8> _data;
    std::size_t _rpos{0};
};

struct LootItemStub { uint32 itemid{0}; };
struct Loot
{
    std::vector<LootItemStub> items;
    std::vector<LootItemStub> quest_items;
};
struct Creature { Loot loot; };
struct GameObject { Loot loot; };

class Map
{
public:
    std::map<ObjectGuid, Creature*> creatures;
    std::map<ObjectGuid, GameObject*> gameObjects;
    Creature* GetCreature(ObjectGuid g) { auto it = creatures.find(g); return it == creatures.end() ? nullptr : it->second; }
    GameObject* GetGameObject(ObjectGuid g) { auto it = gameObjects.find(g); return it == gameObjects.end() ? nullptr : it->second; }
};

class Player;
class Group
{
public:
    ObjectGuid masterLooter;
    LootMethod method{MASTER_LOOT};
    [[nodiscard]] ObjectGuid GetMasterLooterGuid() const { return masterLooter; }
    [[nodiscard]] LootMethod GetLootMethod() const { return method; }
};

class WorldObject { };

struct Replies
{
    std::vector<std::pair<uint64, int>> lootErrors;   // (loot guid, LootError)
    std::vector<int> equipErrors;
};

class Player : public WorldObject
{
public:
    ObjectGuid guid;
    bool inWorld{true};
    Group* group{nullptr};
    ObjectGuid lootGuid;
    Map* map{nullptr};
    bool inRaidWithTarget{true};
    uint32 flags{0};
    Replies replies;

    [[nodiscard]] ObjectGuid GetGUID() const { return guid; }
    [[nodiscard]] bool IsInWorld() const { return inWorld; }
    [[nodiscard]] Group* GetGroup() const { return group; }
    [[nodiscard]] ObjectGuid GetLootGUID() const { return lootGuid; }
    [[nodiscard]] Map* GetMap() const { return map; }
    [[nodiscard]] bool IsInRaidWith(Player const*) const { return inRaidWithTarget; }
    [[nodiscard]] bool HasPlayerFlag(PlayerFlags f) const { return (flags & f) != 0; }
    [[nodiscard]] std::string GetName() const { return "stub"; }
    void SendLootError(ObjectGuid g, LootError e) { replies.lootErrors.push_back({g.GetRawValue(), int(e)}); }
    void SendEquipError(InventoryResult r, void*, void*) { replies.equipErrors.push_back(int(r)); }
};

namespace ObjectAccessor
{
    extern std::map<ObjectGuid, Player*> g_players;
    inline Player* GetPlayer(WorldObject const&, ObjectGuid g)
    {
        auto it = g_players.find(g);
        return it == g_players.end() ? nullptr : it->second;
    }
}

class WorldSession
{
public:
    Player* player{nullptr};
    [[nodiscard]] Player* GetPlayer() const { return player; }
};

// Records the call #272's PermitMasterGive makes into the real header and
// returns a scripted outcome. The enum mirrors MasterLootQuestGive.h
// (test_p4_h_interop.py checks the names).
namespace NaxxramasMasterLootQuestGive
{
    enum class Result : uint8 { PassThrough, Given, AlreadyLooted, Error };
    struct Outcome { Result result; LootError error; };

    struct Call { Player* leader; Player* target; Loot* loot; uint8 slot; };
    extern std::vector<Call> g_calls;
    extern Outcome g_next;

    inline Outcome GiveQuestSlot(Player* leader, Player* target, Loot& loot, uint8 slot)
    {
        g_calls.push_back({leader, target, &loot, slot});
        return g_next;
    }
}

#endif
