#!/usr/bin/env python3
"""Compile and run the EXACT NT1 ApplyValidated C++ body against counted fakes.

This source-extracted decision-path fixture is not a Worldserver, not actual
AzerothCore hook execution, and not gear-preservation certification. It
proves the draft's independent Alt Bot reject-before-reset guard remains
effective even if a first-stage readiness check mistakenly returns READY.
No character/database access, no real inventory or talent mutation.
"""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/Systems/BotTalentImport.cpp").read_text("utf-8")
BEGIN = "    bool ApplyValidated("
END = "    bool ReadArguments("
start = SOURCE.index(BEGIN)
stop = SOURCE.index(END, start + len(BEGIN))
EXACT_CPP = SOURCE[start:stop]

PREFIX = r"""
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
using uint8 = std::uint8_t;
using uint32 = std::uint32_t;

struct ValidatedBuild {};
struct Guid
{
    uint32 GetCounter() const { return 77; }
};
struct Player
{
    bool random = false;
    bool mutateSpecOnReset = false;
    uint8 spec = 0;
    int resets = 0, saves = 0, packets = 0;
    bool resetTalents(bool)
    {
        ++resets;
        if (mutateSpecOnReset)
            spec = 1;
        return true;
    }
    uint8 GetActiveSpec() const { return spec; }
    void SendTalentsInfoData(bool) { ++packets; }
    void SaveToDB(bool, bool) { ++saves; }
    Guid GetGUID() const { return {}; }
};

struct FakeRandomBotMgr
{
    bool IsRandomBot(Player const* bot) const { return bot->random; }
} sRandomPlayerbotMgr;

struct FakeCharacterDatabase
{
    int writes = 0;
    template<class... Args>
    void DirectExecute(char const*, Args const&...) { ++writes; }
} CharacterDatabase;

int enterScope = 0, leaveScope = 0;
struct ImportScope
{
    explicit ImportScope(Player const*) { ++enterScope; }
    ~ImportScope() { ++leaveScope; }
};

bool readOnly = false, readiness = true, exact = false;
int preflightCalls = 0, learnCalls = 0, failAtLearnCall = 0;
bool IsReadOnlyAccessMode() { return readOnly; }
bool CheckApplyReadiness(Player*, Player*, ValidatedBuild const&,
                         std::string& error, ValidatedBuild* snapshot,
                         bool* verifiedNoOp)
{
    ++preflightCalls;
    if (!readiness)
    {
        error = "preflight rejected";
        return false;
    }
    if (snapshot)
        *snapshot = {};
    if (verifiedNoOp)
        *verifiedNoOp = exact;
    return true;
}
bool LearnValidated(Player*, ValidatedBuild const&, std::string& error)
{
    ++learnCalls;
    if (learnCalls == failAtLearnCall || failAtLearnCall == -1)
    {
        error = "simulated learning failure";
        return false;
    }
    return true;
}
"""

SUFFIX = r"""
void Require(bool ok, char const* label)
{
    if (!ok)
        throw std::runtime_error(label);
}
void ResetFakes()
{
    readOnly = false;
    readiness = true;
    exact = false;
    preflightCalls = 0;
    learnCalls = 0;
    failAtLearnCall = 0;
    enterScope = 0;
    leaveScope = 0;
    CharacterDatabase.writes = 0;
}
void MustHaveNoEffects(Player const& bot)
{
    Require(bot.resets == 0, "Alt Bot reset was reached");
    Require(bot.saves == 0, "Alt Bot was saved");
    Require(bot.packets == 0, "Alt Bot received modified talent packets");
    Require(learnCalls == 0, "Alt Bot learned talents");
    Require(CharacterDatabase.writes == 0, "Alt Bot profile write was reached");
    Require(enterScope == 0 && leaveScope == 0,
        "Alt Bot entered a mutating import scope");
}
int main()
{
    Player issuer;
    ValidatedBuild plan;

    // Preflight denies: unchanged must reset to false and never mutate.
    ResetFakes();
    readiness = false;
    Player altDenied;
    bool unchanged = true;
    std::string error;
    Require(!ApplyValidated(&issuer, &altDenied, "NT1:example", plan,
                            error, &unchanged), "denied preflight accepted");
    Require(!unchanged && preflightCalls == 1,
        "denied preflight incorrectly reported no-op");
    MustHaveNoEffects(altDenied);

    // Crucial independent gate: even a BUGGY preflight that returns READY
    // on a differing Alt Bot cannot reach the core's ordinary reset.
    ResetFakes();
    Player altDifferent;
    unchanged = true;
    error.clear();
    Require(!ApplyValidated(&issuer, &altDifferent, "NT1:example", plan,
                            error, &unchanged), "changed Alt Bot accepted");
    Require(!unchanged && preflightCalls == 1 &&
            error.find("changed-build Apply blocked") != std::string::npos,
        "changed Alt Bot was not correctly refused");
    MustHaveNoEffects(altDifferent);

    // An authorized, exact active build is a true no-op.
    ResetFakes();
    exact = true;
    Player altExact;
    unchanged = false;
    error.clear();
    Require(ApplyValidated(&issuer, &altExact, "NT1:example", plan,
                           error, &unchanged), "exact Alt Bot no-op rejected");
    Require(unchanged && preflightCalls == 1,
        "exact Alt Bot no-op not reported");
    MustHaveNoEffects(altExact);

    // Modes 3/4 must be denied BEFORE preflight, even if EXACT.
    ResetFakes();
    readOnly = true;
    exact = true;
    Player altReadOnly;
    unchanged = true;
    error.clear();
    Require(!ApplyValidated(&issuer, &altReadOnly, "NT1:example", plan,
                            error, &unchanged), "read-only mode accepted");
    Require(!unchanged && preflightCalls == 0, "read-only preflight reached");
    MustHaveNoEffects(altReadOnly);

    // Random Bot ordinary success retains one reset, learn and save.
    ResetFakes();
    Player randomSuccess;
    randomSuccess.random = true;
    unchanged = true;
    error.clear();
    Require(ApplyValidated(&issuer, &randomSuccess, "NT1:example", plan,
                           error, &unchanged), "Random Bot apply rejected");
    Require(!unchanged && randomSuccess.resets == 1 &&
            randomSuccess.saves == 1 && randomSuccess.packets == 1 &&
            learnCalls == 1 && CharacterDatabase.writes == 0 &&
            enterScope == 1 && leaveScope == 1,
        "Random Bot ordinary apply was changed");

    // Random Bot rollback still attempts second reset on learn failure.
    ResetFakes();
    failAtLearnCall = 1;
    Player randomRollback;
    randomRollback.random = true;
    error.clear();
    Require(!ApplyValidated(&issuer, &randomRollback, "NT1:example", plan,
                            error), "Random Bot failed learning succeeded");
    Require(randomRollback.resets == 2 && randomRollback.saves == 1 &&
            randomRollback.packets == 1 && learnCalls == 2 &&
            CharacterDatabase.writes == 0 &&
            enterScope == 1 && leaveScope == 1,
        "Random Bot successful rollback behavior changed");

    // Random Bot failed rollback still leaves explicit recovery warning.
    ResetFakes();
    failAtLearnCall = -1;
    Player randomBadRollback;
    randomBadRollback.random = true;
    error.clear();
    Require(!ApplyValidated(&issuer, &randomBadRollback, "NT1:example", plan,
                            error), "Random Bot failed rollback succeeded");
    Require(randomBadRollback.resets == 2 &&
            randomBadRollback.saves == 0 && learnCalls == 2 &&
            error.find("ROLLBACK FAILED:") != std::string::npos,
        "Random Bot failed rollback behavior changed");

    // Unexpected spec switch still aborts before learn or save.
    ResetFakes();
    Player randomSpecChanged;
    randomSpecChanged.random = true;
    randomSpecChanged.mutateSpecOnReset = true;
    error.clear();
    Require(!ApplyValidated(&issuer, &randomSpecChanged, "NT1:example",
                            plan, error), "spec-changing reset succeeded");
    Require(randomSpecChanged.resets == 1 &&
            randomSpecChanged.saves == 0 && learnCalls == 0,
        "unexpected spec switch no longer stops apply");
    std::cout << "PASS: 8 source-extracted NT1 Apply guard scenarios; "
                 "no true AzerothCore reset, inventory, or DB access\n";
}
"""

def main():
    compiler = shutil.which(os.environ.get("CXX", "g++"))
    if compiler is None:
        raise RuntimeError("C++ compiler missing; cannot verify guard.")
    with tempfile.TemporaryDirectory(prefix="nt1_alt_apply_guard_") as tmp:
        source = Path(tmp) / "apply_guard.cpp"
        exe = Path(tmp) / "apply_guard"
        source.write_text(PREFIX + "\n" + EXACT_CPP + "\n" + SUFFIX, "utf-8")
        subprocess.run(
            [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror",
             "-pedantic", str(source), "-o", str(exe)],
            check=True, timeout=60,
        )
        subprocess.run([str(exe)], check=True, timeout=15)
    print("PASS: exact extracted C++ guard, NOT a live Apply or full respec.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError,
            subprocess.TimeoutExpired) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
