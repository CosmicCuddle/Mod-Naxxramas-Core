#!/usr/bin/env python3
"""Compile ACTUAL pinned Grimfeather Player::AddItem and ACTUAL Claude P11 code.

No production patch: real source bodies are extracted unmodified and compiled
against small fake Player/ObjectMgr inventory boundaries. This test is OFFLINE
source evidence, not a real Worldserver or owner gameplay acceptance.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "src/Systems/BotRaidConsumables.cpp"
PINNED_CORE = ROOT / "pinned-core/src/server/game/Entities/Player/Player.cpp"
CORE_SHA = "8daffdabe9202c228e45d833c9a1d399597a15cd"
AUTHOR_SHA = "4e697e7863aff061bb7464865fb967db32804dd6"


def extract(source: str, signature: str) -> str:
    if source.count(signature) != 1:
        raise AssertionError(f"Expected exactly one real source function: {signature!r}")
    start = source.index(signature)
    opening = source.find("{", start)
    if opening < 0:
        raise AssertionError("Missing function body")
    braces = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            braces += 1
        elif source[pos] == "}":
            braces -= 1
            if braces == 0:
                return source[start:pos + 1]
    raise AssertionError("Unterminated function body")


HARNESS = r"""
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <vector>
using uint32 = std::uint32_t;
static constexpr int NULL_BAG = 0;
static constexpr int NULL_SLOT = 0;
enum InventoryResult { EQUIP_ERR_OK, EQUIP_ERR_INVENTORY_FULL };
using ItemPosCountVec = std::vector<uint32>;
struct Item {};

struct ItemTemplate { int MaxCount = 100; };
struct FakeObjectMgr {
    ItemTemplate item;
    bool hasTemplate = true;
    ItemTemplate const* GetItemTemplate(uint32) const {
        return hasTemplate ? &item : nullptr;
    }
};
FakeObjectMgr manager;
FakeObjectMgr* sObjectMgr = &manager;

struct PreparationStats {
    uint32 ItemsAdded = 0;
    uint32 ReagentsAdded = 0;
    uint32 ItemFailures = 0;
};
struct Player {
    uint32 count;
    uint32 space;
    bool rejectStore;
    uint32 attempts = 0;
    uint32 notifications = 0;
    uint32 rejectedMessage = 0;
    Item item;

    uint32 GetItemCount(uint32, bool) const { return count; }
    void* GetSession() const { return nullptr; }

    InventoryResult CanStoreNewItem(int, int, ItemPosCountVec& dest,
                                    uint32, uint32 requested, uint32* noSpace) {
        ++attempts;
        uint32 const accepted = std::min(requested, space);
        *noSpace = requested - accepted;
        if (accepted > 0)
            dest.push_back(accepted);
        return accepted == requested ? EQUIP_ERR_OK : EQUIP_ERR_INVENTORY_FULL;
    }
    Item* StoreNewItem(ItemPosCountVec const& dest, uint32, bool) {
        if (rejectStore)
            return nullptr;
        if (dest.empty())
            return nullptr;
        count += dest.at(0);
        space -= dest.at(0);
        return &item;
    }
    void SendNewItem(Item*, uint32, bool, bool) { ++notifications; }
    bool AddItem(uint32, uint32);
};
struct ChatHandler {
    explicit ChatHandler(void*) {}
    void PSendSysMessage(char const*) {}
};
void RecordItemFailure(PreparationStats&, Player*, uint32, char const*) {}
__CORE_FUNCTION__
__MODULE_FUNCTION__

void Scenario(char const* label, uint32 initial, uint32 freeCapacity,
              uint32 target, bool reagent, bool rejectStore,
              bool templateExists, int maxCount, int repeats) {
    manager.item.MaxCount = maxCount;
    manager.hasTemplate = templateExists;
    Player bot{initial, freeCapacity, rejectStore, 0, 0, 0, {}};
    PreparationStats stats;
    bool ok = false;
    for (int i = 0; i < repeats; ++i)
        ok = TopUpToCount(&bot, 17030, target, stats, reagent);
    std::cout << label << " " << ok << " "
              << bot.count - initial << " "
              << stats.ItemsAdded << " " << stats.ReagentsAdded << " "
              << stats.ItemFailures << " " << bot.attempts << " "
              << bot.notifications << "\n";
}
int main() {
    Scenario("full", 1, 10, 5, true, false, true, 100, 1);
    Scenario("partial", 1, 2, 5, true, false, true, 100, 1);
    Scenario("partial_nonreagent", 1, 2, 5, false, false, true, 100, 1);
    Scenario("no_space", 1, 0, 5, true, false, true, 100, 1);
    Scenario("sufficient", 5, 0, 5, true, false, true, 100, 1);
    Scenario("max_clamp", 1, 2, 10, true, false, true, 4, 1);
    Scenario("store_rejected", 1, 5, 5, true, true, true, 100, 1);
    Scenario("missing_template", 1, 5, 5, true, false, false, 100, 1);
    Scenario("repeat_partial", 1, 2, 5, true, false, true, 100, 2);
    Scenario("repeat_full", 1, 10, 5, true, false, true, 100, 2);
}
"""

# ok, actual increase, total reported, reagents reported, failure count,
# actual core CanStoreNewItem attempts, actual SendNewItem calls.
EXPECTED = {
    "full": (1, 4, 4, 4, 0, 1, 1),
    "partial": (1, 2, 2, 2, 0, 1, 1),
    "partial_nonreagent": (1, 2, 2, 0, 0, 1, 1),
    "no_space": (0, 0, 0, 0, 1, 1, 0),
    "sufficient": (1, 0, 0, 0, 0, 0, 0),
    "max_clamp": (1, 2, 2, 2, 0, 1, 1),
    "store_rejected": (0, 0, 0, 0, 1, 1, 0),
    "missing_template": (0, 0, 0, 0, 1, 0, 0),
    "repeat_partial": (0, 2, 2, 2, 1, 2, 1),
    "repeat_full": (1, 4, 4, 4, 0, 1, 1),
}


def main() -> None:
    original_core = PINNED_CORE.read_text(encoding="utf-8")
    core = extract(original_core, "bool Player::AddItem(uint32 itemId, uint32 count)")
    module = extract(MOD_PATH.read_text(encoding="utf-8"), "    bool TopUpToCount(")
    for required in (
        "InventoryResult msg = CanStoreNewItem(NULL_BAG, NULL_SLOT, dest, itemId, count, &noSpaceForCount);",
        "if (msg != EQUIP_ERR_OK)",
        "count -= noSpaceForCount;",
        "if (count == 0 || dest.empty())",
        "Item* item = StoreNewItem(dest, itemId, true);",
        "SendNewItem(item, count, true, false);",
    ):
        if required not in core:
            raise AssertionError(f"Pinned {CORE_SHA} AddItem source drifted: {required}")
    for required in (
        "if (!bot->AddItem(itemId, amountToAdd))",
        "afterCount > currentCount",
        "std::min<uint32>(afterCount - currentCount, amountToAdd)",
        "stats.ItemsAdded += added;",
        "stats.ReagentsAdded += added;",
    ):
        if required not in module:
            raise AssertionError(f"Author {AUTHOR_SHA} TopUp source drifted: {required}")

    source = HARNESS.replace("__CORE_FUNCTION__", core).replace("__MODULE_FUNCTION__", module)
    with tempfile.TemporaryDirectory(prefix="p11-exact-core-and-module-") as directory:
        for std in ("c++17", "c++20"):
            fixture = pathlib.Path(directory) / f"p11_{std}.cpp"
            binary = pathlib.Path(directory) / f"p11_{std}"
            fixture.write_text(source, encoding="utf-8")
            subprocess.run(
                ["g++", "-std=" + std, "-Wall", "-Wextra", "-Werror", "-pedantic",
                 "-O1", "-fsanitize=undefined", "-fno-sanitize-recover=all",
                 str(fixture), "-o", str(binary)],
                check=True,
            )
            output = subprocess.check_output([str(binary)], text=True)
            actual = {}
            for line in output.splitlines():
                m = re.fullmatch(r"([a-z_]+) ([01]) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)", line)
                if not m:
                    raise AssertionError(f"Unexpected source fixture output: {line!r}")
                name, *numbers = m.groups()
                if name in actual:
                    raise AssertionError("Duplicate fixture")
                actual[name] = tuple(map(int, numbers))
            if actual != EXPECTED:
                raise AssertionError(f"Actual pinned core + module {std}: {actual!r} != {EXPECTED!r}")
            print(f"PASS: {std} real pinned Player::AddItem + actual Claude TopUpToCount: "
                  f"{len(actual)} exact behavioral cases")
    print(f"PASS: exact core source pinned {CORE_SHA}; author source pinned {AUTHOR_SHA}")
    print("NO owner inventory, actual server, upstream source or production file changed")


if __name__ == "__main__":
    main()
