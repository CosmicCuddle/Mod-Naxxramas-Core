#!/usr/bin/env python3
"""Extract and test the ACTUAL cooldown functions from Naxx B10 integrated #120.

The tested code below is copied directly, byte-for-byte, from the production
BotRaidConsumables.cpp at CI runtime. Only surrounding AzerothCore type adapters
are lightweight stand-ins. The optional deliberately UNLOCKED negative fixture
is NOT production code and is for ThreadSanitizer sensitivity testing.
No server, DB, memory under owner account, or runtime module is modified.
"""
from pathlib import Path
import argparse
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Systems/BotRaidConsumables.cpp"

CONST = "constexpr uint32 CONSUMABLE_COMMAND_COOLDOWN_SECONDS =\n        10 * 60;"
STORE_START = "std::mutex ConsumableCooldownLock;"
STORE_END = "\n    void AddConsumableDebugMessage("
FUNCTION_START = "uint64 GetConsumableNow()"
FUNCTION_END = "bool CheckConsumableCooldown("
LOCK = "std::lock_guard<std::mutex> lock(\n            ConsumableCooldownLock);"

def extract(source):
    for token in (CONST, STORE_START, STORE_END, FUNCTION_START, FUNCTION_END):
        if source.count(token) != 1:
            raise ValueError("missing or duplicate integrated #120 source token: " + token)
    a = source.index(STORE_START)
    b = source.index(STORE_END, a)
    if b <= a:
        raise ValueError("bad global cooldown map bound")
    store = source[a:b]
    a = source.index(FUNCTION_START)
    b = source.index(FUNCTION_END, a)
    funcs = source[a:b]
    if store.count("ConsumableCooldownUntil") != 1 or store.count("ConsumableCooldownLock") != 1:
        raise ValueError("expected one original mutex and map in store declaration")
    if funcs.count(LOCK) != 3:
        raise ValueError("all three actual production methods must retain their locks")
    if funcs.count("ConsumableCooldownUntil") < 5:
        raise ValueError("cooldown map read/write/erase paths are missing")
    if funcs.count("GetConsumableNow();") != 2:
        raise ValueError("expiration and start must use original game time")
    if funcs.count("CONSUMABLE_COMMAND_COOLDOWN_SECONDS") != 1:
        raise ValueError("real 600-second cooldown missing")
    for signature in ("uint32 GetConsumableCooldownRemaining(",
                      "void StartConsumableCooldown(",
                      "void ResetConsumableCooldownForGroup("):
        if funcs.count(signature) != 1:
            raise ValueError("original production method missing/duplicated: " + signature)
    lookup = funcs.split("uint32 GetConsumableCooldownRemaining(", 1)[1].split(
        "void StartConsumableCooldown(", 1)[0]
    start = funcs.split("void StartConsumableCooldown(", 1)[1].split(
        "void ResetConsumableCooldownForGroup(", 1)[0]
    group = funcs.split("void ResetConsumableCooldownForGroup(", 1)[1]
    for label, body, map_access in (("lookup", lookup, "ConsumableCooldownUntil.find("),
                                    ("start", start, "ConsumableCooldownUntil[guid]"),
                                    ("reset", group, "ConsumableCooldownUntil.erase(")):
        if LOCK not in body or body.index(LOCK) > body.index(map_access):
            raise ValueError("unguarded cross-map cooldown " + label)
    if group.index("group->GetFirstMember()") > group.index(LOCK):
        raise ValueError("never walk actual Group members while holding cooldown mutex")
    if group.index("guids.push_back(") > group.index(LOCK):
        raise ValueError("group GUID snapshot must finish before cooldown mutex")
    if "group->" in group.split(LOCK, 1)[1] or "member->" in group.split(LOCK, 1)[1]:
        raise ValueError("unsafe game API under mutex")
    return store, funcs


PRELUDE = r"""
#include <atomic>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <thread>
#include <unordered_map>
#include <vector>

using uint32 = std::uint32_t;
using uint64 = std::uint64_t;

struct ObjectGuid {
    using LowType = uint32;
    uint32 value;
    uint32 GetCounter() const { return value; }
};
struct Player;
struct GroupReference {
    Player* member;
    GroupReference* nextRef;
    Player* GetSource() { return member; }
    GroupReference* next() { return nextRef; }
};
struct Group {
    GroupReference* first;
    GroupReference* GetFirstMember() { return first; }
};
struct Player {
    ObjectGuid guid;
    Group* group;
    ObjectGuid GetGUID() const { return guid; }
    Group* GetGroup() const { return group; }
};
static std::atomic<uint64> nowSeconds{100};
struct GameTime {
    struct Tick {
        uint64 value;
        uint64 count() const { return value; }
    };
    static Tick GetGameTime() {
        return Tick{nowSeconds.load(std::memory_order_relaxed)};
    }
};
"""

MAIN = r"""
int main()
{
#ifndef NAXX_UNLOCKED_NEGATIVE_CONTROL
    // Synthetic Player/Group objects. Execute the ACTUAL production
    // cooldown functions, not a parallel reimplementation.
    Player a{ObjectGuid{101}, nullptr};
    Player b{ObjectGuid{102}, nullptr};
    Player c{ObjectGuid{103}, nullptr};
    Player unrelated{ObjectGuid{104}, nullptr};
    GroupReference cRef{&c, nullptr};
    GroupReference bRef{&b, &cRef};
    GroupReference aRef{&a, &bRef};
    Group group{&aRef};
    a.group = b.group = c.group = &group;

    auto Check = [](bool condition, char const* label) {
        if (!condition) {
            std::cerr << "FAIL actual integrated B10 cooldown: " << label << '\n';
            std::exit(1);
        }
    };
    nowSeconds.store(100);
    Check(GetConsumableCooldownRemaining(nullptr) == 0, "null lookup");
    StartConsumableCooldown(nullptr);
    ResetConsumableCooldownForGroup(nullptr);
    Check(ConsumableCooldownUntil.empty(), "null calls do not change store");
    Check(GetConsumableCooldownRemaining(&a) == 0, "empty lookup");
    StartConsumableCooldown(&a);
    Check(GetConsumableCooldownRemaining(&a) == 600, "start 600 seconds");
    nowSeconds.store(699);
    Check(GetConsumableCooldownRemaining(&a) == 1, "one second remaining");
    nowSeconds.store(700);
    Check(GetConsumableCooldownRemaining(&a) == 0, "expired exact boundary");
    Check(ConsumableCooldownUntil.empty(), "expiration removes original entry");

    nowSeconds.store(1000);
    StartConsumableCooldown(&a);
    StartConsumableCooldown(&b);
    StartConsumableCooldown(&c);
    StartConsumableCooldown(&unrelated);
    Player sameGuidAfterRelog{ObjectGuid{101}, nullptr};
    Check(GetConsumableCooldownRemaining(&sameGuidAfterRelog) == 600,
          "per-GUID cooldown survives separate Player object / logout");
    ResetConsumableCooldownForGroup(&a);
    Check(GetConsumableCooldownRemaining(&a) == 0 &&
          GetConsumableCooldownRemaining(&b) == 0 &&
          GetConsumableCooldownRemaining(&c) == 0,
          "group death resets all captured group GUIDs");
    Check(GetConsumableCooldownRemaining(&unrelated) == 600,
          "nonmember retains cooldown");
    ResetConsumableCooldownForGroup(&unrelated);
    Check(GetConsumableCooldownRemaining(&unrelated) == 0,
          "solo death resets only self");
    std::cout << "PASS actual B10 original cooldown semantics and group cases\n";
#endif

    // 8 map workers and the world command thread pattern.
    // Each thread owns its synthetic Player and calls the actual compiled
    // integrated methods on one shared cooldown map. No gameplay engine.
    nowSeconds.store(1500);
    std::atomic<uint64> sink{0};
    std::vector<std::thread> workers;
    for (uint32 t = 0; t < 8; ++t) {
        workers.emplace_back([t, &sink]() {
            uint64 local = 0;
            for (uint32 i = 0; i < 3500; ++i) {
                Player bot{ObjectGuid{uint32(200 + (i * 7 + t * 131) % 128)}, nullptr};
                StartConsumableCooldown(&bot);
                local += GetConsumableCooldownRemaining(&bot);
                if (i % 13 == 0)
                    ResetConsumableCooldownForGroup(&bot);
            }
            sink.fetch_add(local, std::memory_order_relaxed);
        });
    }
    for (std::thread& worker : workers)
        worker.join();
    std::cout << "PASS actual integrated B10 8-worker exercise, sink="
              << sink.load() << '\n';
    return 0;
}
"""

def render(source, negative=False):
    store, funcs = extract(source)
    if negative:
        # Deliberate mutation used ONLY in a separate ThreadSanitizer
        # test executable. Must never be committed to runtime C++.
        funcs = funcs.replace(LOCK, "")
    return (PRELUDE + "\nnamespace {\n" + CONST + "\n" + store +
            "\n" + funcs + "\n}\n" + MAIN)


class OriginalCooldownSourceGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SOURCE.read_text()

    def test_original_compiled_functions_exist_and_lock_all_paths(self):
        store, funcs = extract(self.source)
        self.assertIn("std::unordered_map<ObjectGuid::LowType, uint64>", store)
        self.assertEqual(funcs.count(LOCK), 3)

    def test_remove_lookup_lock_is_rejected(self):
        source = self.source.replace(LOCK, "", 1)
        with self.assertRaises(ValueError):
            extract(source)

    def test_remove_reset_lock_is_rejected(self):
        token = "void ResetConsumableCooldownForGroup("
        before, after = self.source.split(token, 1)
        source = before + token + after.replace(LOCK, "", 1)
        with self.assertRaises(ValueError):
            extract(source)

    def test_group_game_access_under_lock_is_rejected(self):
        source = self.source.replace(
            "std::lock_guard<std::mutex> lock(\n            ConsumableCooldownLock);\n\n        for (ObjectGuid::LowType guid : guids)",
            "std::lock_guard<std::mutex> lock(\n            ConsumableCooldownLock);\n\n        group->GetFirstMember();\n        for (ObjectGuid::LowType guid : guids)", 1)
        with self.assertRaises(ValueError):
            extract(source)

    def test_change_cooldown_seconds_is_rejected(self):
        with self.assertRaises(ValueError):
            extract(self.source.replace("10 * 60;", "9 * 60;", 1))

    def test_reset_group_member_first_then_lock(self):
        _, funcs = extract(self.source)
        group = funcs.split("void ResetConsumableCooldownForGroup(", 1)[1]
        self.assertLess(group.index("group->GetFirstMember()"),
                        group.index(LOCK))

    def test_real_native_fixture_contains_original_method_body_verbatim(self):
        _, funcs = extract(self.source)
        full = render(self.source)
        self.assertIn(funcs, full)
        self.assertNotIn("CooldownStore.h", full)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, help="C++ output; only if specified")
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    if args.output:
        args.output.write_text(render(SOURCE.read_text(), args.negative_control))
        print("Generated source-exact B10 native fixture (negative=%s)" %
              args.negative_control)
    else:
        unittest.main(argv=[__file__])
