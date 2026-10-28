#!/usr/bin/env python3
"""P11: compile the unchanged production TopUpToCount and test-only controls.

The pinned module source remains unchanged. Three variants are compiled:
  ORIGINAL: actual module function; expected to over-report a partial grant.
  UNGUARDED: test-only observed-delta fix that wraps if count unexpectedly falls.
  GUARDED: test-only bounded observed-delta accounting reference.

The C++ mock models the pinned core's *possible* partial-success AddItem
behavior. "anomalous_loss" is a separate artificial fault injection, NOT a
claim that stock AzerothCore loses items during AddItem.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/Systems/BotRaidConsumables.cpp"


def extract_top_up(source: str) -> str:
    signature = "    bool TopUpToCount("
    start = source.find(signature)
    if start < 0:
        raise AssertionError("Production TopUpToCount signature absent")
    opening = source.find("{", start)
    if opening < 0:
        raise AssertionError("Function has no opening brace")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("Unterminated production function")


def delta_control(original: str, guarded: bool) -> str:
    items = "        stats.ItemsAdded += amountToAdd;"
    reagents = "            stats.ReagentsAdded += amountToAdd;"
    if original.count(items) != 1 or original.count(reagents) != 1:
        raise AssertionError("Source accounting contract drift; do not transform")
    if guarded:
        delta = (
            "        uint32 const afterCount = bot->GetItemCount(itemId, false);\n"
            "        uint32 const actualAdded = afterCount > currentCount\n"
            "            ? std::min<uint32>(afterCount - currentCount, amountToAdd)\n"
            "            : 0;\n"
        )
    else:
        delta = (
            "        uint32 const actualAdded = "
            "bot->GetItemCount(itemId, false) - currentCount;\n"
        )
    return original.replace(items, delta + "        stats.ItemsAdded += actualAdded;").replace(
        reagents, "            stats.ReagentsAdded += actualAdded;"
    )


HARNESS = r"""
#include <algorithm>
#include <cstdint>
#include <iostream>
using uint32 = std::uint32_t;
struct ItemTemplate { int MaxCount = 100; };
struct FakeObjectMgr {
    ItemTemplate item;
    bool available = true;
    ItemTemplate const* GetItemTemplate(uint32) const {
        return available ? &item : nullptr;
    }
};
FakeObjectMgr manager;
FakeObjectMgr* sObjectMgr = &manager;
struct PreparationStats {
    uint32 ItemFailures = 0;
    uint32 ItemsAdded = 0;
    uint32 ReagentsAdded = 0;
};
struct Player {
    uint32 count = 0;
    uint32 freeSpace = 0;
    bool failStore = false;
    bool injectedLoss = false;
    uint32 addCalls = 0;
    uint32 GetItemCount(uint32, bool) const { return count; }
    bool AddItem(uint32, uint32 requested) {
        ++addCalls;
        if (failStore)
            return false;
        if (injectedLoss) {
            if (count)
                --count;
            return true;
        }
        uint32 const added = std::min(requested, freeSpace);
        count += added;
        freeSpace -= added;
        return added != 0;
    }
};
void RecordItemFailure(PreparationStats&, Player*, uint32, char const*) {}
__FUNCTION__

void Scenario(char const* name, uint32 owned, uint32 freeSpace,
              uint32 target, bool isReagent = true,
              int maxCount = 100, bool hasTemplate = true,
              bool failStore = false, bool injectedLoss = false,
              bool repeat = false) {
    manager.item.MaxCount = maxCount;
    manager.available = hasTemplate;
    Player bot{owned, freeSpace, failStore, injectedLoss, 0};
    PreparationStats stats;
    uint32 const before = bot.GetItemCount(17030, false);
    bool const first = TopUpToCount(&bot, 17030, target, stats, isReagent);
    bool const second = repeat
        ? TopUpToCount(&bot, 17030, target, stats, isReagent) : false;
    uint32 const observed = bot.count > before ? bot.count - before : 0;
    std::cout << name << " " << int(first) + (second ? 2 : 0)
              << " " << observed << " " << stats.ItemsAdded
              << " " << stats.ReagentsAdded << " " << stats.ItemFailures
              << " " << bot.count << " " << bot.addCalls << "\n";
}
int main() {
    Scenario("full", 1, 10, 5);
    Scenario("partial", 1, 2, 5);
    Scenario("no_space", 1, 0, 5);
    Scenario("sufficient", 5, 0, 5);
    Scenario("nonreagent_partial", 1, 2, 5, false);
    Scenario("nonreagent_full", 1, 10, 5, false);
    Scenario("maxcount", 1, 10, 5, true, 3);
    Scenario("no_template", 1, 10, 5, true, 100, false);
    Scenario("failed_store", 1, 10, 5, true, 100, true, true);
    Scenario("zero_target", 1, 10, 0);
    Scenario("repeat_partial", 1, 3, 5, true, 100, true, false, false, true);
    Scenario("anomalous_loss", 1, 10, 5, true, 100, true, false, true);
}
"""

EXPECTED_COMMON = {
    "full": (1, 4, 4, 4, 0, 5, 1),
    "no_space": (0, 0, 0, 0, 1, 1, 1),
    "sufficient": (1, 0, 0, 0, 0, 5, 0),
    "nonreagent_full": (1, 4, 4, 0, 0, 5, 1),
    "maxcount": (1, 2, 2, 2, 0, 3, 1),
    "no_template": (0, 0, 0, 0, 1, 1, 0),
    "failed_store": (0, 0, 0, 0, 1, 1, 1),
    "zero_target": (0, 0, 0, 0, 0, 1, 0),
}
EXPECTED_DIFFERENCES = {
    "partial": ((1, 2, 4, 4, 0, 3, 1), (1, 2, 2, 2, 0, 3, 1)),
    "nonreagent_partial": ((1, 2, 4, 0, 0, 3, 1), (1, 2, 2, 0, 0, 3, 1)),
    "repeat_partial": ((1, 3, 4, 4, 1, 4, 2), (1, 3, 3, 3, 1, 4, 2)),
    "anomalous_loss": ((1, 0, 4, 4, 0, 0, 1), (1, 0, 0, 0, 0, 0, 1)),
}


def run_variant(workdir: pathlib.Path, label: str, function: str, standard: str):
    source_file = workdir / f"{label}_{standard}.cpp"
    executable = workdir / f"{label}_{standard}"
    source_file.write_text(HARNESS.replace("__FUNCTION__", function), encoding="utf-8")
    subprocess.run(
        ["g++", f"-std={standard}", "-Wall", "-Wextra", "-Werror",
         "-pedantic", "-O1", str(source_file), "-o", str(executable)],
        check=True,
    )
    out = subprocess.check_output([str(executable)], text=True)
    cases = {}
    for row in out.splitlines():
        match = re.fullmatch(r"(\w+) ([0-3]) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)", row)
        if not match:
            raise AssertionError(f"{label}/{standard} unexpected C++ output: {row!r}")
        name, *values = match.groups()
        cases[name] = tuple(map(int, values))
    expected_names = set(EXPECTED_COMMON) | set(EXPECTED_DIFFERENCES)
    if set(cases) != expected_names:
        raise AssertionError(f"{label}/{standard}: cases mismatch: {set(cases) ^ expected_names}")
    return cases


def main():
    original = extract_top_up(SOURCE.read_text(encoding="utf-8"))
    required_contracts = (
        "bot->GetItemCount(itemId, false)",
        "if (!bot->AddItem(itemId, amountToAdd))",
        "if (itemTemplate->MaxCount > 0)",
        "targetCount - currentCount",
    )
    for needle in required_contracts:
        if needle not in original:
            raise AssertionError(f"Production contract drift: {needle}")
    with tempfile.TemporaryDirectory(prefix="naxx-p11-") as folder:
        for std in ("c++17", "c++20"):
            actual = run_variant(pathlib.Path(folder), "original", original, std)
            unchecked = run_variant(
                pathlib.Path(folder), "unchecked", delta_control(original, False), std
            )
            guarded = run_variant(
                pathlib.Path(folder), "guarded", delta_control(original, True), std
            )
            for name, row in EXPECTED_COMMON.items():
                if any(c[name] != row for c in (actual, unchecked, guarded)):
                    raise AssertionError(f"{std}: {name} must preserve existing semantics")
            for name, (bad, good) in EXPECTED_DIFFERENCES.items():
                if actual[name] != bad or guarded[name] != good:
                    raise AssertionError(f"{std}: {name} mismatch in original/guarded")
            for name in ("partial", "nonreagent_partial", "repeat_partial"):
                if unchecked[name] != guarded[name]:
                    raise AssertionError(f"{std}: normal observed deltas must agree")
            assert unchecked["anomalous_loss"] == (
                1, 0, 4294967295, 4294967295, 0, 0, 1
            ), "Unsigned-underflow mutation must be detected"
            print(f"PASS {std}: 12 source-extracted cases x 3 variants, 8 shared and "
                  "4 original-vs-guarded negative/positive pairs")
    print("EXPECTED SOURCE RED: partial AddItem grants 2/4 but original reports 4")
    print("EXPECTED FAULT RED: artificial inventory loss makes unchecked delta wrap")
    print("PASS: test-only guarded actual deltas are bounded and non-negative")
    print("NO PRODUCTION FIX: all changes are isolated test/CI code, not live inventory")


if __name__ == "__main__":
    main()
