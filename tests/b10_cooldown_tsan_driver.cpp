// Test-only driver for #120's PRODUCTION cooldown code (B10 #114).
//
// Not compilable on its own: scripts/extract_b10_cooldown_harness.py
// replaces the marker below with the verbatim text of
// ConsumableCooldownLock, ConsumableCooldownUntil and the three cooldown
// functions from src/Systems/BotRaidConsumables.cpp, after checking their
// digest. Only the types they need are stubbed here.
//
// Limits: Player, Group and GroupReference are minimal stubs. This proves
// the cooldown map's locking under 8 threads; it does NOT prove group
// membership concurrency, Player::CustomData thread affinity, or anything
// about a running Worldserver.
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <thread>
#include <unordered_map>
#include <vector>

using uint32 = std::uint32_t;
using uint64 = std::uint64_t;

struct ObjectGuid
{
    using LowType = uint32;
    uint32 low;
    LowType GetCounter() const { return low; }
};

struct Group;

struct Player
{
    uint32 id = 0;
    Group* group = nullptr;
    ObjectGuid GetGUID() const { return {id}; }
    Group* GetGroup() const { return group; }
};

struct GroupReference
{
    Player* source = nullptr;
    GroupReference* following = nullptr;
    Player* GetSource() const { return source; }
    GroupReference* next() const { return following; }
};

struct Group
{
    GroupReference* first = nullptr;
    GroupReference* GetFirstMember() const { return first; }
};

constexpr uint32 CONSUMABLE_COMMAND_COOLDOWN_SECONDS = 600;
std::atomic<uint64> FakeNow{1000};
uint64 GetConsumableNow() { return FakeNow.load(); }

namespace
{
// @@B10_EXTRACTED_PRODUCTION_COOLDOWN_CODE@@
}

namespace
{
    int failures = 0;

    void Check(bool ok, char const* what)
    {
        if (!ok)
        {
            std::printf("FAIL: %s\n", what);
            ++failures;
        }
    }

    // Single-threaded behaviour of the production text.
    void Semantics()
    {
        Player a{11}, b{12}, c{13}, solo{14};
        Group g;
        GroupReference ra{&a}, rb{&b}, rc{&c};
        ra.following = &rb;
        rb.following = &rc;
        g.first = &ra;
        a.group = b.group = c.group = &g;

        FakeNow = 1000;
        Check(GetConsumableCooldownRemaining(&a) == 0, "no cooldown -> 0");
        StartConsumableCooldown(&a);
        StartConsumableCooldown(&b);
        StartConsumableCooldown(&solo);
        Check(GetConsumableCooldownRemaining(&a) == 600, "600 s after start");
        FakeNow = 1599;
        Check(GetConsumableCooldownRemaining(&a) == 1, "1 s left");
        ResetConsumableCooldownForGroup(&c);   // a death in the group resets all members
        Check(GetConsumableCooldownRemaining(&a) == 0 &&
              GetConsumableCooldownRemaining(&b) == 0, "group reset clears members");
        Check(GetConsumableCooldownRemaining(&solo) == 1, "non-member keeps cooldown");
        ResetConsumableCooldownForGroup(&solo); // no group: only that player
        Check(GetConsumableCooldownRemaining(&solo) == 0, "solo reset");
        StartConsumableCooldown(&a);
        FakeNow = 1599 + 600;
        Check(GetConsumableCooldownRemaining(&a) == 0, "expires at until");
        Check(ConsumableCooldownUntil.empty(), "expired entries removed on read");
    }

    // 8 workers (MapUpdate.Threads = 8): start, read and group death reset
    // on 64 players in 16 groups, concurrently.
    void Contention()
    {
        std::vector<Player> players(64);
        std::vector<Group> groups(16);
        std::vector<GroupReference> refs(64);
        for (uint32 i = 0; i < 64; ++i)
        {
            players[i].id = 100 + i;
            players[i].group = &groups[i / 4];
            refs[i].source = &players[i];
            refs[i].following = (i % 4 == 3) ? nullptr : &refs[i + 1];
            if (i % 4 == 0)
                groups[i / 4].first = &refs[i];
        }
        std::atomic<uint64> sink{0};
        std::vector<std::thread> workers;
        for (uint32 t = 0; t < 8; ++t)
        {
            workers.emplace_back([&, t]() {
                uint64 local = 0;
                for (uint32 i = 0; i < 20000; ++i)
                {
                    Player* p = &players[(i * 7 + t * 13) % 64];
                    StartConsumableCooldown(p);
                    local += GetConsumableCooldownRemaining(&players[(i + t) % 64]);
                    if (i % 16 == 0)
                        ResetConsumableCooldownForGroup(p);
                    if (i % 1000 == 0)
                        FakeNow += 1;
                }
                sink += local;
            });
        }
        for (std::thread& worker : workers)
            worker.join();
        Check(ConsumableCooldownUntil.size() <= 64, "bounded, consistent map after contention");
    }
}

int main()
{
    Semantics();
    Contention();
    if (failures)
        return 1;
    std::printf("PASS: #120 production cooldown code, semantics + 8-thread contention\n");
    return 0;
}
