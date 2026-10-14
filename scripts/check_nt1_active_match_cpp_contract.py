#!/usr/bin/env python3
"""Compile + execute EXACT draft NT1 read-only comparison against fake C++ APIs.

This is a deliberately tiny deterministic API harness, NOT an AzerothCore
compilation. It has no network, no game server, no database, and no commands
that change talents or equipment. Real dependency headers, hooks and runtime
require a separate production-fork build and review.
"""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src" / "Systems" / "BotTalentImport.cpp").read_text(
    encoding="utf-8"
)

BEGIN = "    enum class ActiveTalentMatchStatus\n"
END = "    // Diagnostic-only Alt Bot repair preview."
first = SOURCE.index(BEGIN)
last = SOURCE.index(END, first + len(BEGIN))
EXACT_CPP = SOURCE[first:last]

# The simulated API deliberately uses the visible class/talent field names
# and signatures from the operator's pinned AzerothCore Player.h.
PREFIX = r"""
#include <cstdint>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;
constexpr uint8 MAX_TALENT_SPECS = 2;
constexpr uint8 MAX_TALENT_RANK = 5;
enum PlayerSpellState : uint8
{
    PLAYERSPELL_UNCHANGED = 0, PLAYERSPELL_CHANGED = 1,
    PLAYERSPELL_NEW = 2, PLAYERSPELL_REMOVED = 3, PLAYERSPELL_TEMPORARY = 4
};
struct PlayerTalent
{
    PlayerSpellState State = PLAYERSPELL_UNCHANGED;
    uint8 specMask = 1;
    uint32 talentID = 0;
};
struct TalentEntry
{
    uint32 TalentID = 0, TalentTab = 0;
    uint32 RankID[5] = {};
};
struct TalentTabEntry
{
    uint32 ClassMask = 0;
    uint8 tabpage = 0;
};
struct TalentStore
{
    std::unordered_map<uint32, TalentEntry> rows;
    TalentEntry const* LookupEntry(uint32 id) const
    {
        auto it = rows.find(id);
        return it == rows.end() ? nullptr : &it->second;
    }
};
struct TalentTabStore
{
    std::unordered_map<uint32, TalentTabEntry> rows;
    TalentTabEntry const* LookupEntry(uint32 id) const
    {
        auto it = rows.find(id);
        return it == rows.end() ? nullptr : &it->second;
    }
};
TalentStore sTalentStore;
TalentTabStore sTalentTabStore;
struct SpellInfo {};
struct FakeSpellMgr
{
    SpellInfo info;
    std::unordered_set<uint32> spells;
    SpellInfo const* GetSpellInfo(uint32 id) const
    {
        return spells.count(id) ? &info : nullptr;
    }
};
FakeSpellMgr fakeSpellMgr;
FakeSpellMgr* sSpellMgr = &fakeSpellMgr;
char const* ClassName(uint8 cls) { return cls == 5 ? "priest" : nullptr; }
struct TalentSelection
{
    uint32 Id = 0;
    uint8 Rank = 0;
    TalentEntry const* Talent = nullptr;
    TalentTabEntry const* Tab = nullptr;
};
struct ValidatedBuild
{
    std::string Class = "priest";
    std::vector<TalentSelection> Ordered;
    uint32 Spent = 0;
    uint32 Available = 5;
};
struct Player
{
    uint8 cls = 5, activeSpec = 0, specCount = 2;
    uint32 available = 5, freePoints = 0, classMask = 1u << 4;
    std::unordered_map<uint32, PlayerTalent*> talentMap;
    std::vector<std::unique_ptr<PlayerTalent>> storage;
    uint8 getClass() const { return cls; }
    uint32 getClassMask() const { return classMask; }
    uint8 GetSpecsCount() const { return specCount; }
    uint8 GetActiveSpec() const { return activeSpec; }
    uint32 CalculateTalentsPoints() const { return available; }
    uint32 GetFreeTalentPoints() const { return freePoints; }
    std::unordered_map<uint32, PlayerTalent*> const& GetTalentMap() const
    {
        return talentMap;
    }
    bool HasTalent(uint32 spell, uint8 spec) const
    {
        auto it = talentMap.find(spell);
        return it != talentMap.end() && it->second &&
            it->second->State != PLAYERSPELL_REMOVED &&
            (it->second->specMask & (1u << spec)) != 0;
    }
    void Add(uint32 spell, uint32 talent, uint8 specMask = 1,
        PlayerSpellState state = PLAYERSPELL_UNCHANGED)
    {
        auto record = std::make_unique<PlayerTalent>();
        record->State = state;
        record->specMask = specMask;
        record->talentID = talent;
        talentMap.emplace(spell, record.get());
        storage.push_back(std::move(record));
    }
};
struct ChatHandler
{
    void SendSysMessage(char const*) const {}
    template <class... A>
    void PSendSysMessage(char const*, A&&...) const {}
};
"""
SUFFIX = r"""
void Expect(ActiveTalentMatchStatus expected, ActiveTalentMatch actual,
    char const* label)
{
    if (actual.Status != expected)
    {
        std::cerr << "FAIL " << label << " unexpected status; reason="
                  << actual.Reason << "\n";
        throw std::runtime_error(label);
    }
}

void ExpectDelta(ActiveTalentMatch const& actual, uint32 add, uint32 remove,
    char const* label)
{
    if (actual.Status != ActiveTalentMatchStatus::Different ||
        actual.PointsToAdd != add || actual.PointsToRemove != remove)
    {
        std::cerr << "FAIL " << label << " incorrect read-only talent delta"
                  << " status=" << static_cast<int>(actual.Status)
                  << " add=" << actual.PointsToAdd
                  << " remove=" << actual.PointsToRemove << "\n";
        throw std::runtime_error(label);
    }
}
ValidatedBuild Plan(uint8 rank = 5)
{
    ValidatedBuild result;
    if (rank)
    {
        auto const& t = sTalentStore.rows.at(100);
        result.Ordered.push_back({t.TalentID, rank, &t,
            sTalentTabStore.LookupEntry(t.TalentTab)});
        result.Spent = rank;
    }
    return result;
}
void RegisterTalent()
{
    sTalentStore.rows.clear();
    sTalentTabStore.rows.clear();
    fakeSpellMgr.spells.clear();
    TalentEntry t;
    t.TalentID = 100;
    t.TalentTab = 200;
    for (uint32 i = 0; i < MAX_TALENT_RANK; ++i)
    {
        t.RankID[i] = 5001 + i;
        fakeSpellMgr.spells.insert(t.RankID[i]);
    }
    sTalentStore.rows.emplace(100, t);
    // Another legal priest talent to test a same-budget full tree swap.
    TalentEntry second = t;
    second.TalentID = 101;
    for (uint32 i = 0; i < MAX_TALENT_RANK; ++i)
    {
        second.RankID[i] = 6001 + i;
        fakeSpellMgr.spells.insert(second.RankID[i]);
    }
    sTalentStore.rows.emplace(101, second);
    sTalentTabStore.rows.emplace(200, TalentTabEntry{1u << 4, 0});
}
int main()
{
    RegisterTalent();
    ChatHandler handler;
    Player exact;
    exact.Add(5005, 100);
    Expect(ActiveTalentMatchStatus::Exact,
        InspectActiveTalentMatch(&exact, Plan()), "exact rank five");
    PrintActiveTalentMatch(&handler, &exact, Plan());
    {
        auto const result = InspectActiveTalentMatch(&exact, Plan());
        if (result.PointsToAdd || result.PointsToRemove)
            throw std::runtime_error("exact build reported a nonzero delta");
    }

    Player wrongRank;
    wrongRank.Add(5004, 100);
    wrongRank.freePoints = 1;
    Expect(ActiveTalentMatchStatus::Different,
        InspectActiveTalentMatch(&wrongRank, Plan()), "valid different rank");
    ExpectDelta(InspectActiveTalentMatch(&wrongRank, Plan()), 1, 0,
        "one point needed to finish existing rank");

    Player empty;
    empty.freePoints = 5;
    ExpectDelta(InspectActiveTalentMatch(&empty, Plan()), 5, 0,
        "five-point additions only");

    Player downgrade;
    downgrade.Add(5005, 100);
    ExpectDelta(InspectActiveTalentMatch(&downgrade, Plan(4)), 0, 1,
        "same talent reduced by one rank");

    Player fullSwap;
    fullSwap.Add(5005, 100);
    ValidatedBuild swapTarget;
    auto const& second = sTalentStore.rows.at(101);
    swapTarget.Ordered.push_back({101, 5, &second,
        sTalentTabStore.LookupEntry(second.TalentTab)});
    swapTarget.Spent = 5;
    ExpectDelta(InspectActiveTalentMatch(&fullSwap, swapTarget), 5, 5,
        "full-budget respec requires both additions and removals");

    Player extra;
    extra.Add(5005, 100);
    extra.Add(5001, 100);
    extra.freePoints = 0;
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&extra, Plan()), "duplicate live rank");

    Player orphan;
    orphan.Add(9001, 999);
    orphan.freePoints = 0;
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&orphan, Plan()), "unknown DBC talent");

    Player wrongClass;
    wrongClass.cls = 6;
    wrongClass.Add(5005, 100);
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&wrongClass, Plan()), "unexpected class");

    Player inconsistent;
    inconsistent.Add(5005, 100);
    inconsistent.freePoints = 1;
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&inconsistent, Plan()), "point mismatch");

    Player missingSpell;
    missingSpell.Add(5005, 100);
    fakeSpellMgr.spells.erase(5005);
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&missingSpell, Plan()), "missing spell.dbc rank");
    fakeSpellMgr.spells.insert(5005);

    Player duplicateDBC;
    duplicateDBC.Add(5005, 100);
    sTalentStore.rows.at(100).RankID[0] = 5005;
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&duplicateDBC, Plan()), "duplicate DBC rank spell");
    sTalentStore.rows.at(100).RankID[0] = 5001;

    Player temporarilySaved;
    temporarilySaved.Add(5005, 100, 1, PLAYERSPELL_TEMPORARY);
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&temporarilySaved, Plan()), "temporary record");

    Player inactiveOnly;
    inactiveOnly.Add(5005, 100, 2);
    inactiveOnly.freePoints = 5;
    Expect(ActiveTalentMatchStatus::Exact,
        InspectActiveTalentMatch(&inactiveOnly, Plan(0)), "inactive only");

    Player removedOnly;
    removedOnly.Add(5005, 100, 1, PLAYERSPELL_REMOVED);
    removedOnly.freePoints = 5;
    Expect(ActiveTalentMatchStatus::Exact,
        InspectActiveTalentMatch(&removedOnly, Plan(0)), "removed rank ignored");

    Player nullRecord;
    nullRecord.talentMap.emplace(5005, nullptr);
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&nullRecord, Plan()), "null talent record");

    Player badSpec;
    badSpec.Add(5005, 100);
    badSpec.activeSpec = 3;
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&badSpec, Plan()), "invalid active spec");

    ValidatedBuild stalePointPlan = Plan();
    stalePointPlan.Spent = 4;
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&exact, stalePointPlan),
        "mismatched proposed rank sum");

    ValidatedBuild staleDbcPlan = Plan();
    sTalentStore.rows.at(100).RankID[4] = 0;
    Expect(ActiveTalentMatchStatus::Indeterminate,
        InspectActiveTalentMatch(&exact, staleDbcPlan),
        "missing planned DBC rank");
    sTalentStore.rows.at(100).RankID[4] = 5005;

    std::cout << "NT1 isolated C++ exact-function contract: 18 cases and 5 delta assertions passed\n";
}
"""


def main():
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if not compiler:
        raise RuntimeError("No C++ compiler found; cannot claim validation.")
    # Compile the source EXACTLY as written; do not substitute a rewritten
    # implementation or pretend the fixture stands in for real AzerothCore.
    actual = PREFIX + "\n" + EXACT_CPP + "\n" + SUFFIX
    with tempfile.TemporaryDirectory(prefix="nt1_cpp_readonly_") as dirname:
        source = Path(dirname) / "exact_match.cpp"
        executable = Path(dirname) / "exact_match"
        source.write_text(actual, encoding="utf-8")
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
             "-pedantic", str(source), "-o", str(executable)],
            check=True, timeout=60,
        )
        subprocess.run([str(executable)], check=True, timeout=15)
    print("PASS: isolated C++ function compile/run, NOT a server build.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        sys.exit(1)
