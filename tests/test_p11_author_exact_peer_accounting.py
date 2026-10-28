#!/usr/bin/env python3
"""Independent CS01 cross-check of the exact Claude P11 production C++ source.

This is a test-only child of immutable author PR #217 commit 4e697e7.
The 16-case inventory fixture originates independently in CS01 PR #216,
which proved the main source's five accounting mismatches. Here it compiles
Claude's ACTUAL modified TopUpToCount body, without synthesizing its correction.

Only model inventory is used. This is NOT real server, bot, owner or gameplay.
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
    if source.count(signature) != 1:
        raise AssertionError("Expected exactly one production TopUpToCount declaration")
    start = source.find(signature)
    opening = source.find("{", start)
    if opening == -1:
        raise AssertionError("Function opening brace missing")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("Unclosed production TopUpToCount")


HARNESS = r"""
#include <algorithm>
#include <cstdint>
#include <iostream>
using uint32 = std::uint32_t;

struct ItemTemplate {
    int MaxCount = 100;
};
struct FakeObjectMgr {
    ItemTemplate item;
    bool valid = true;
    ItemTemplate const* GetItemTemplate(uint32) const {
        return valid ? &item : nullptr;
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
    uint32 count;
    uint32 freeSpace;
    bool forceFailure;
    uint32 addCalls = 0;
    uint32 GetItemCount(uint32, bool) const { return count; }
    bool AddItem(uint32, uint32 requested) {
        ++addCalls;
        if (forceFailure)
            return false;
        // Matches pinned core's ability to return true after storing a
        // reduced count when the bags cannot fit the entire request.
        uint32 const added = std::min(requested, freeSpace);
        count += added;
        freeSpace -= added;
        return added != 0;
    }
};
void RecordItemFailure(PreparationStats&, Player*, uint32, char const*) {}
__FUNCTION__

void Scenario(char const* name, uint32 owned, uint32 space, uint32 target,
              bool reagent, int maxCount, bool hasTemplate,
              bool forceFailure, unsigned repeats) {
    manager.item.MaxCount = maxCount;
    manager.valid = hasTemplate;
    Player bot{owned, space, forceFailure, 0};
    PreparationStats stats;
    uint32 const before = bot.GetItemCount(17030, false); // Ankh fixture
    bool success = false;
    for (unsigned i = 0; i < repeats; ++i)
        success = TopUpToCount(&bot, 17030, target, stats, reagent);
    uint32 const delta = bot.GetItemCount(17030, false) - before;
    std::cout << name << " " << success << " " << delta
              << " " << stats.ItemsAdded << " " << stats.ReagentsAdded
              << " " << stats.ItemFailures << " " << bot.count
              << " " << bot.addCalls << "\n";
}
void NullBot() {
    manager.valid = true;
    PreparationStats stats;
    bool const success = TopUpToCount(nullptr, 17030, 5, stats, true);
    std::cout << "null_bot " << success << " 0 "
              << stats.ItemsAdded << " " << stats.ReagentsAdded
              << " " << stats.ItemFailures << " 0 0\n";
}
int main() {
    Scenario("full_reagent",         1, 10, 5, true, 100, true, false, 1);
    Scenario("partial_reagent",      1,  2, 5, true, 100, true, false, 1);
    Scenario("partial_nonreagent",   1,  2, 5, false,100, true, false, 1);
    Scenario("full_nonreagent",      1, 10, 5, false,100, true, false, 1);
    Scenario("no_space",            1,  0, 5, true, 100, true, false, 1);
    Scenario("sufficient",          5,  0, 5, true, 100, true, false, 1);
    Scenario("max_clamp_partial",    1,  2,10, true,   4, true, false, 1);
    Scenario("max_clamp_full",       1, 10,10, true,   4, true, false, 1);
    Scenario("max_clamp_sufficient", 5, 10,10, true,   4, true, false, 1);
    Scenario("missing_template",    1, 10, 5, true, 100, false,false, 1);
    Scenario("zero_target",         1, 10, 0, true, 100, true, false, 1);
    Scenario("add_failure",         1, 10, 5, true, 100, true, true,  1);
    Scenario("repeat_partial",      1,  2, 5, true, 100, true, false, 2);
    Scenario("repeat_full",         1, 10, 5, true, 100, true, false, 2);
    Scenario("huge_partial",        1,  2,4294967295u,true,0,true,false,1);
    NullBot();
}
"""

# Tuple: (last call success, actual inventory delta, ItemsAdded,
#         ReagentsAdded, ItemFailures, final inventory count, AddItem calls)
COMMON = {
    "full_reagent":          (1, 4, 4, 4, 0, 5, 1),
    "full_nonreagent":       (1, 4, 4, 0, 0, 5, 1),
    "no_space":              (0, 0, 0, 0, 1, 1, 1),
    "sufficient":            (1, 0, 0, 0, 0, 5, 0),
    "max_clamp_full":        (1, 3, 3, 3, 0, 4, 1),
    "max_clamp_sufficient":  (1, 0, 0, 0, 0, 5, 0),
    "missing_template":      (0, 0, 0, 0, 1, 1, 0),
    "zero_target":           (0, 0, 0, 0, 0, 1, 0),
    "add_failure":           (0, 0, 0, 0, 1, 1, 1),
    "repeat_full":           (1, 4, 4, 4, 0, 5, 1),
    "null_bot":              (0, 0, 0, 0, 0, 0, 0),
}
LEGACY_EXPECTED_RED = {
    "partial_reagent":       (1, 2, 4, 4, 0, 3, 1),
    "partial_nonreagent":    (1, 2, 4, 0, 0, 3, 1),
    "max_clamp_partial":     (1, 2, 3, 3, 0, 3, 1),
    "repeat_partial":        (0, 2, 4, 4, 1, 3, 2),
    "huge_partial":          (1, 2, 4294967294, 4294967294, 0, 3, 1),
}
DELTA_CONTROL = {
    "partial_reagent":       (1, 2, 2, 2, 0, 3, 1),
    "partial_nonreagent":    (1, 2, 2, 0, 0, 3, 1),
    "max_clamp_partial":     (1, 2, 2, 2, 0, 3, 1),
    "repeat_partial":        (0, 2, 2, 2, 1, 3, 2),
    "huge_partial":          (1, 2, 2, 2, 0, 3, 1),
}


def run_variant(directory: pathlib.Path, label: str,
                function: str, standard: str) -> dict[str, tuple[int, ...]]:
    source_file = directory / f"{label}_{standard}.cpp"
    binary = directory / f"{label}_{standard}"
    source_file.write_text(HARNESS.replace("__FUNCTION__", function), encoding="utf-8")
    subprocess.run(
        ["g++", f"-std={standard}", "-Wall", "-Wextra", "-Werror", "-pedantic",
         "-O1", "-fsanitize=undefined", "-fno-sanitize-recover=all",
         str(source_file), "-o", str(binary)],
        check=True,
    )
    output = subprocess.check_output([str(binary)], text=True)
    cases = {}
    for line in output.splitlines():
        match = re.fullmatch(r"(\w+) ([01]) (\d+) (\d+) (\d+) (\d+) (\d+) (\d+)", line)
        if not match:
            raise AssertionError(f"Unexpected output: {line!r}")
        name, *numbers = match.groups()
        if name in cases:
            raise AssertionError(f"Duplicated test scenario: {name}")
        cases[name] = tuple(map(int, numbers))
    return cases


def check(label: str, cases: dict[str, tuple[int, ...]],
          expected_negatives: dict[str, tuple[int, ...]]) -> None:
    expected = COMMON | expected_negatives
    if cases.keys() != expected.keys():
        raise AssertionError(
            f"{label}: expected {sorted(expected)} but got {sorted(cases)}"
        )
    for name, value in expected.items():
        if cases[name] != value:
            raise AssertionError(f"{label} {name}: expected {value}, got {cases[name]}")
    print(f"PASS: {label}: {len(cases)} exact source-extracted C++ fixture cases")


def main() -> None:
    production = extract_top_up(SOURCE.read_text(encoding="utf-8"))
    # Fail closed if the exact author's production accounting contract drifts.
    if production.count("bot->GetItemCount(itemId, false)") != 2:
        raise AssertionError("Expected one pre-grant and one post-grant bag query")
    if production.count("if (!bot->AddItem(itemId, amountToAdd))") != 1:
        raise AssertionError("Author AddItem/return branch contract drifted")
    if production.count("stats.ItemsAdded += added;") != 1:
        raise AssertionError("Author total accounting must use observed delta")
    if production.count("stats.ReagentsAdded += added;") != 1:
        raise AssertionError("Author reagent accounting must use observed delta")
    if "stats.ItemsAdded += amountToAdd;" in production:
        raise AssertionError("Original requested-amount defect reappeared")
    if production.count("afterCount > currentCount") != 1:
        raise AssertionError("Underflow-safe positive increase guard missing")
    if production.count("std::min<uint32>(afterCount - currentCount, amountToAdd)") != 1:
        raise AssertionError("Quantity cap missing or modified")
    # Exact independent expectations are frozen from the CS01 initial
    # original-source negative and separately positive controlled witness.
    if len(LEGACY_EXPECTED_RED) != 5 or len(DELTA_CONTROL) != 5:
        raise AssertionError("Expected mismatch witness corpus drifted")
    with tempfile.TemporaryDirectory(prefix="naxx-p11-author-peer-") as temp:
        directory = pathlib.Path(temp)
        for standard in ("c++17", "c++20"):
            actual = run_variant(directory, "actual_author_source", production, standard)
            check(f"{standard} actual author production TopUpToCount",
                  actual, DELTA_CONTROL)
    print("PASS: all five original partial-accounting discrepancies fixed in actual author source")
    print("PASS: 16 cases each C++17/C++20 with UBSan, exact independent quantities")
    print("NO module production code changed by this TEST-ONLY peer branch")


if __name__ == "__main__":
    main()
