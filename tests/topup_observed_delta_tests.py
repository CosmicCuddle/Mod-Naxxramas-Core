"""P11: TopUpToCount reports only what actually arrived in the bags.

Extracts the REAL `bool TopUpToCount(` function from a given
BotRaidConsumables.cpp (current file by default, or main 80e9de1 with
--main), compiles it against small stubs that mirror pinned 8daffda
Player::AddItem semantics (partial grants return true, Player.cpp
L16030-L16050), and runs scenarios in C++17 and C++20 (strict and
ASan+UBSan). Usage:
  python3 -I tests/topup_observed_delta_tests.py <scratch dir> [--main | --source FILE]
Exit 0 only if every scenario passes for the chosen source.
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = "src/Systems/BotRaidConsumables.cpp"
BASE_MAIN = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
EXPECTED_CHECKS = 41

PRELUDE = r'''
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <map>
#include <string>
#include <vector>

using uint32 = std::uint32_t;
using int32 = std::int32_t;

struct ItemTemplate { int32 MaxCount = 0; };

struct StubObjectMgr
{
    std::map<uint32, ItemTemplate> templates;
    ItemTemplate const* GetItemTemplate(uint32 id) const
    {
        auto it = templates.find(id);
        return it == templates.end() ? nullptr : &it->second;
    }
};
StubObjectMgr g_objectMgr;
#define sObjectMgr (&g_objectMgr)

// Mirrors pinned Player::AddItem: store what fits; false only when nothing
// fits; true for a partial grant. `extraOnAdd` / `loseOnAdd` model another
// actor changing the count at the same moment (bound and underflow guards).
struct Player
{
    std::map<uint32, uint32> bags;
    uint32 freeSpace = 1000;
    uint32 extraOnAdd = 0;
    uint32 loseOnAdd = 0;
    int addCalls = 0;
    uint32 lastRequested = 0;

    uint32 GetItemCount(uint32 id, bool) const
    {
        auto it = bags.find(id);
        return it == bags.end() ? 0 : it->second;
    }
    bool AddItem(uint32 id, uint32 count)
    {
        ++addCalls;
        lastRequested = count;
        uint32 const fits = std::min(count, freeSpace);
        if (fits == 0)
            return false;
        freeSpace -= fits;
        bags[id] += fits + extraOnAdd;
        bags[id] -= std::min(bags[id], loseOnAdd);
        return true;
    }
};

struct PreparationStats
{
    uint32 ItemsAdded = 0;
    uint32 ItemFailures = 0;
    uint32 ReagentsAdded = 0;
    std::vector<std::string> failures;
};

void RecordItemFailure(PreparationStats& stats, Player*, uint32, char const* why)
{
    stats.failures.push_back(why);
}
'''

TESTS = r'''
int failures = 0;
int checks = 0;
#define CHECK(c) do { ++checks; if (!(c)) { ++failures; std::printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

constexpr uint32 POTION = 13444;
constexpr uint32 REAGENT = 17033;
constexpr uint32 UNKNOWN = 999999;

int main()
{
    g_objectMgr.templates[POTION] = ItemTemplate{0};
    g_objectMgr.templates[REAGENT] = ItemTemplate{0};
    g_objectMgr.templates[777] = ItemTemplate{3};        // MaxCount 3

    {   // Full grant: unchanged.
        Player bot; PreparationStats s;
        CHECK(TopUpToCount(&bot, POTION, 5, s));
        CHECK(bot.lastRequested == 5 && bot.GetItemCount(POTION, false) == 5);
        CHECK(s.ItemsAdded == 5 && s.ReagentsAdded == 0 && s.ItemFailures == 0);
    }
    {   // THE DEFECT: 4 requested, 2 fit -> report 2.
        Player bot; bot.freeSpace = 2; PreparationStats s;
        CHECK(TopUpToCount(&bot, POTION, 4, s));            // AddItem still true
        CHECK(bot.lastRequested == 4);                      // same request as before
        CHECK(bot.GetItemCount(POTION, false) == 2);
        CHECK(s.ItemsAdded == 2);
        CHECK(s.ItemFailures == 0 && s.failures.empty());   // no new failure policy
    }
    {   // Partial grant of a raid reagent: both counters use the real delta.
        Player bot; bot.freeSpace = 7; bot.bags[REAGENT] = 3; PreparationStats s;
        CHECK(TopUpToCount(&bot, REAGENT, 20, s, true));
        CHECK(bot.lastRequested == 17 && bot.GetItemCount(REAGENT, false) == 10);
        CHECK(s.ItemsAdded == 7 && s.ReagentsAdded == 7);
    }
    {   // Full raid reagent grant.
        Player bot; PreparationStats s;
        CHECK(TopUpToCount(&bot, REAGENT, 20, s, true));
        CHECK(s.ItemsAdded == 20 && s.ReagentsAdded == 20);
    }
    {   // No space at all: AddItem false, failure path unchanged.
        Player bot; bot.freeSpace = 0; PreparationStats s;
        CHECK(!TopUpToCount(&bot, POTION, 5, s));
        CHECK(s.ItemsAdded == 0 && s.ItemFailures == 1);
        CHECK(s.failures.size() == 1 && s.failures[0] == std::string("AddItem could not add the requested quantity"));
    }
    {   // Already sufficient: no AddItem call.
        Player bot; bot.bags[POTION] = 9; PreparationStats s;
        CHECK(TopUpToCount(&bot, POTION, 5, s));
        CHECK(bot.addCalls == 0 && s.ItemsAdded == 0 && s.ItemFailures == 0);
    }
    {   // MaxCount clamp: target 10 clamped to 3.
        Player bot; bot.bags[777] = 1; PreparationStats s;
        CHECK(TopUpToCount(&bot, 777, 10, s));
        CHECK(bot.lastRequested == 2 && s.ItemsAdded == 2);
    }
    {   // Unknown template: failure path unchanged, no AddItem.
        Player bot; PreparationStats s;
        CHECK(!TopUpToCount(&bot, UNKNOWN, 5, s));
        CHECK(bot.addCalls == 0 && s.ItemFailures == 1 && s.ItemsAdded == 0);
        CHECK(s.failures.size() == 1 && s.failures[0] == std::string("item template was not found"));
    }
    {   // Null bot / zero target: unchanged early return.
        Player bot; PreparationStats s;
        CHECK(!TopUpToCount(nullptr, POTION, 5, s));
        CHECK(!TopUpToCount(&bot, POTION, 0, s));
        CHECK(bot.addCalls == 0 && s.ItemsAdded == 0 && s.ItemFailures == 0);
    }
    {   // Repeated calls accumulate real deltas; a full bag then fails.
        Player bot; bot.freeSpace = 6; PreparationStats s;
        CHECK(TopUpToCount(&bot, POTION, 4, s));            // +4
        CHECK(TopUpToCount(&bot, REAGENT, 5, s, true));     // only 2 fit
        CHECK(!TopUpToCount(&bot, 777, 3, s));              // nothing fits
        CHECK(s.ItemsAdded == 6 && s.ReagentsAdded == 2 && s.ItemFailures == 1);
        CHECK(TopUpToCount(&bot, POTION, 4, s));            // already 4: no-op
        CHECK(s.ItemsAdded == 6 && bot.addCalls == 3);
    }
    {   // Bound: count rising by more than requested is capped at the request.
        Player bot; bot.extraOnAdd = 10; PreparationStats s;
        CHECK(TopUpToCount(&bot, POTION, 5, s));
        CHECK(bot.GetItemCount(POTION, false) == 15);
        CHECK(s.ItemsAdded == 5);
    }
    {   // Underflow guard: count falling during the call reports 0, not 4e9.
        Player bot; bot.bags[POTION] = 3; bot.freeSpace = 1; bot.loseOnAdd = 4; PreparationStats s;
        CHECK(TopUpToCount(&bot, POTION, 5, s, true));
        CHECK(bot.GetItemCount(POTION, false) == 0);
        CHECK(s.ItemsAdded == 0 && s.ReagentsAdded == 0);
    }
    {   // Partial with an existing stack: delta, not request or total.
        Player bot; bot.bags[POTION] = 1; bot.freeSpace = 1; PreparationStats s;
        CHECK(TopUpToCount(&bot, POTION, 5, s));
        CHECK(bot.lastRequested == 4 && bot.GetItemCount(POTION, false) == 2);
        CHECK(s.ItemsAdded == 1);
    }

    if (checks != EXPECTED)
    {
        std::printf("COUNT DRIFT: ran %d checks, expected %d\n", checks, EXPECTED);
        return 1;
    }
    if (failures)
    {
        std::printf("FAILED: %d of %d checks\n", failures, checks);
        return 1;
    }
    std::printf("PASS: TopUpToCount observed delta, %d checks\n", checks);
    return 0;
}
'''


def extract(source):
    start = source.index("    bool TopUpToCount(")
    open_at = source.index("{", start)
    depth = 0
    for i in range(open_at, len(source)):
        depth += {"{": 1, "}": -1}.get(source[i], 0)
        if depth == 0:
            return source[start:i + 1]
    raise SystemExit("unterminated TopUpToCount")


def main():
    out = pathlib.Path(sys.argv[1])
    use_main = "--main" in sys.argv[2:]
    if "--source" in sys.argv[2:]:
        source = pathlib.Path(sys.argv[sys.argv.index("--source") + 1]).read_text()
    elif use_main:
        source = subprocess.run(["git", "show", f"{BASE_MAIN}:{PATH}"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout
    else:
        source = (ROOT / PATH).read_text()
    func = extract(source)
    assert re.search(r"bot->AddItem\(itemId, amountToAdd\)", func), "AddItem call drifted"
    out.mkdir(parents=True, exist_ok=True)
    cpp = out / "topup.cpp"
    cpp.write_text(PRELUDE + "\n" + func + "\n" +
                   TESTS.replace("EXPECTED)", f"{EXPECTED_CHECKS})").replace("expected %d\\n\", checks, EXPECTED", f"expected %d\\n\", checks, {EXPECTED_CHECKS}"))
    ok = True
    builds = [("c++17", ["-Wall", "-Wextra", "-Werror", "-pedantic"]),
              ("c++20", ["-Wall", "-Wextra", "-Werror", "-pedantic"]),
              ("c++20", ["-O1", "-g", "-fsanitize=address,undefined", "-fno-sanitize-recover=all"])]
    for std, flags in builds:
        exe = out / "t"
        subprocess.run(["g++", f"-std={std}", *flags, str(cpp), "-o", str(exe)], check=True)
        r = subprocess.run([str(exe)], capture_output=True, text=True)
        label = f"{std} {' '.join(flags[:1])}"
        print(f"{label}: {r.stdout.strip()}")
        ok &= r.returncode == 0
    sys.exit(0 if ok else 1)


main()
