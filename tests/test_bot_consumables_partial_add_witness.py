#!/usr/bin/env python3
"""Source-extracted P11 witness: partial AddItem success can overstate consumables stats.

The module source is NOT modified. Its actual TopUpToCount implementation is
compiled against a minimal controlled Player mock. A test-only arithmetic
control (using observed inventory deltas) is independently compiled as well.

Original mismatched stats are an EXPECTED negative, not a fixed production path.
No client, owner DB, item grants, core changes or live Worldserver involved.
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
    if start == -1:
        raise AssertionError("Pinned production TopUpToCount signature missing")
    opening = source.find("{", start)
    if opening == -1:
        raise AssertionError("Function opening brace absent")
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("Unclosed TopUpToCount function")


def test_only_delta_control(original: str) -> str:
    items = "        stats.ItemsAdded += amountToAdd;"
    reagents = "            stats.ReagentsAdded += amountToAdd;"
    if original.count(items) != 1 or original.count(reagents) != 1:
        raise AssertionError("Cannot safely synthesize independent control")
    with_count = original.replace(
        items,
        "        uint32 const actualAdded = "
        "bot->GetItemCount(itemId, false) - currentCount;\n"
        "        stats.ItemsAdded += actualAdded;",
    )
    return with_count.replace(reagents, "            stats.ReagentsAdded += actualAdded;")


HARNESS = r"""
#include <algorithm>
#include <cstdint>
#include <iostream>
using uint32 = std::uint32_t;
struct ItemTemplate { int MaxCount = 100; };
struct FakeObjectMgr {
    ItemTemplate item;
    ItemTemplate const* GetItemTemplate(uint32) const { return &item; }
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
    uint32 GetItemCount(uint32, bool) const { return count; }
    bool AddItem(uint32, uint32 requested) {
        uint32 const added = std::min(requested, freeSpace);
        count += added;
        freeSpace -= added;
        return added != 0;
    }
};
void RecordItemFailure(PreparationStats&, Player*, uint32, char const*) {}
__FUNCTION__

void Scenario(char const* name, uint32 owned, uint32 space, uint32 target) {
    Player bot{owned, space};
    PreparationStats stats;
    uint32 const before = bot.GetItemCount(17030, false); // renewable Ankh
    bool const success = TopUpToCount(&bot, 17030, target, stats, true);
    uint32 const actual = bot.GetItemCount(17030, false) - before;
    std::cout << name << " " << success << " " << actual
              << " " << stats.ItemsAdded << " " << stats.ReagentsAdded
              << " " << stats.ItemFailures << "\n";
}
int main() {
    Scenario("full", 1, 10, 5);
    Scenario("partial", 1, 2, 5);
    Scenario("no_space", 1, 0, 5);
    Scenario("sufficient", 5, 0, 5);
}
"""


def run_variant(workdir: pathlib.Path, label: str, function: str):
    source_file = workdir / (label + ".cpp")
    binary = workdir / label
    source_file.write_text(HARNESS.replace("__FUNCTION__", function), encoding="utf-8")
    subprocess.run(
        ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
         "-pedantic", "-O1", str(source_file), "-o", str(binary)],
        check=True,
    )
    out = subprocess.check_output([str(binary)], text=True)
    cases = {}
    for row in out.splitlines():
        match = re.fullmatch(r"(\w+) ([01]) (\d+) (\d+) (\d+) (\d+)", row)
        if not match:
            raise AssertionError(f"Unexpected C++ output: {row!r}")
        name, *values = match.groups()
        cases[name] = tuple(map(int, values))
    if set(cases) != {"full", "partial", "no_space", "sufficient"}:
        raise AssertionError("Missing case outputs")
    print(f"{label} source-extracted C++: {cases}")
    return cases


def main():
    original = extract_top_up(SOURCE.read_text(encoding="utf-8"))
    if "bot->GetItemCount(itemId, false)" not in original:
        raise AssertionError("Production inventory lookup contract drifted")
    if "if (!bot->AddItem(itemId, amountToAdd))" not in original:
        raise AssertionError("Production AddItem branch contract drifted")
    with tempfile.TemporaryDirectory(prefix="naxx-p11-") as folder:
        workdir = pathlib.Path(folder)
        actual = run_variant(workdir, "original", original)
        control = run_variant(workdir, "delta_control", test_only_delta_control(original))
    expected_common = {
        "full": (1, 4, 4, 4, 0),
        "no_space": (0, 0, 0, 0, 1),
        "sufficient": (1, 0, 0, 0, 0),
    }
    for name, expected in expected_common.items():
        if actual[name] != expected or control[name] != expected:
            raise AssertionError(f"Unexpected {name} grant/success semantics")
    if actual["partial"] != (1, 2, 4, 4, 0):
        raise AssertionError("Historical source overcount witness changed")
    if control["partial"] != (1, 2, 2, 2, 0):
        raise AssertionError("Test-only observed-delta positive control failed")
    print("PASS: production partial-success overcounts 4 vs 2 (EXPECTED safety/telemetry RED)")
    print("PASS: test-only delta control accounts 2 vs 2; full, none and sufficient unchanged")
    print("Scope: source-extracted real module function, mock inventory, NO production patch.")


if __name__ == "__main__":
    main()
