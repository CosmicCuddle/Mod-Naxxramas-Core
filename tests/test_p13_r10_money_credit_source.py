#!/usr/bin/env python3
"""P13-R10: pinned ORIGINAL HonorOverflow and Player::ModifyMoney source witness.

Usage:
  python3 -I tests/test_p13_r10_money_credit_source.py . pinned-core

Test-only. Extract exact original C++ bodies into a throwaway compile fixture.
No production edits, actual Worldserver, SQL/DBC, Player objects, or payout.
The 1,000-copper CAP is a purposely SMALL hypothetical test constant; it is
not a claim about the original server's configured live money maximum.
"""
import pathlib
import subprocess
import sys
import tempfile

MOD_COMMIT = "80e9de1c39a6dc995188a80c31a5e785d0f2a6f9"
CORE_COMMIT = "8daffdabe9202c228e45d833c9a1d399597a15cd"
MOD_FILE = "src/Systems/HonorOverflow.cpp"
CORE_FILE = "src/server/game/Entities/Player/Player.cpp"
MOD_BLOB = "d4f70c511ac5a3e32c7e6b8f913d095915da707c"
CORE_BLOB = "138e7eab4905ec366338a54cc18e6cfe749a3670"


def git(root, *args):
    return subprocess.check_output(
        ["git", "-C", str(root), *args], text=True
    ).strip()


def assert_pins(mod, core):
    assert git(core, "rev-parse", "HEAD") == CORE_COMMIT, "wrong core HEAD"
    assert git(core, "rev-parse", f"HEAD:{CORE_FILE}") == CORE_BLOB, "core body drift"
    assert git(mod, "rev-parse", f"{MOD_COMMIT}:{MOD_FILE}") == MOD_BLOB, "mod body drift"
    assert git(mod, "merge-base", "--is-ancestor", MOD_COMMIT, "HEAD") == "", (
        "Mod main ancestor mismatch"
    )
    assert git(mod, "rev-parse", f"HEAD:{MOD_FILE}") == MOD_BLOB, (
        "new branch changed protected HonorOverflow production source"
    )


def method(code, anchor):
    pos = code.index(anchor)
    begin = code.index("{", pos)
    depth = 0
    for i in range(begin, len(code)):
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return code[pos : i + 1]
    raise AssertionError("no balanced closing brace for " + anchor)


def verify(module_src, core_src):
    earn = module_src[module_src.index("        uint64 requestedCopper ="):
                      module_src.index("        bool useBattlegroundSummary =")]
    assert "uint64(excessHonor) * HonorOverflowCopperPerHonor;" in earn
    assert "uint64(MAX_MONEY_AMOUNT) - player->GetMoney()" in earn
    assert "uint32(std::min(requestedCopper, availableMoney));" in earn
    assert "if (rewardCopper > 0)" in earn
    assert ("player->ModifyMoney(static_cast<int32>(rewardCopper));" in earn)
    # The unchanged source explicitly discards ModifyMoney's bool result.
    assert "if (player->ModifyMoney(" not in earn
    assert "bool success" not in earn and "bool credited" not in earn
    assert "AddBattlegroundSummary(" in module_src
    call = "AddBattlegroundSummary(\n                player,\n                excessHonor,\n                requestedCopper,\n                rewardCopper);"
    assert call in module_src, "BG caller no longer passes proposed reward"
    summary = method(module_src, "    void AddBattlegroundSummary(")
    assert "summary.AwardedCopper += awardedCopper;" in summary
    money = method(core_src, "bool Player::ModifyMoney(int32 amount, bool sendError /*= true*/)")
    assert "sScriptMgr->OnPlayerMoneyChanged(this, amount);" in money
    assert "if (GetSession()->IsTrialAccount() && GetMoney() + uint32(amount) > trialMoneyCap)" in money
    assert "return false;" in money
    assert "if (GetMoney() < uint32(MAX_MONEY_AMOUNT - amount))" in money, (
        "real core uses strict less-than in positive cap check"
    )
    assert "SetMoney(GetMoney() + amount);" in money
    return earn, summary, money


def negative_guards(module_src, core_src):
    changes = [
        ("core equality", "core",
         "if (GetMoney() < uint32(MAX_MONEY_AMOUNT - amount))",
         "if (GetMoney() <= uint32(MAX_MONEY_AMOUNT - amount))"),
        ("core trial check", "core",
         "GetSession()->IsTrialAccount() && GetMoney() + uint32(amount) > trialMoneyCap",
         "false"),
        ("HonorOverflow ignores return", "mod",
         "player->ModifyMoney(static_cast<int32>(rewardCopper));",
         "if (!player->ModifyMoney(static_cast<int32>(rewardCopper))) return;"),
        ("BG proposed amount", "mod",
         "                rewardCopper);\n\n            return;",
         "                0);\n\n            return;"),
    ]
    for label, where, old, new in changes:
        original = core_src if where == "core" else module_src
        assert original.count(old) == 1, "nonunique mutant anchor " + label
        changed = original.replace(old, new)
        try:
            if where == "core":
                verify(module_src, changed)
            else:
                verify(changed, core_src)
        except AssertionError:
            print("CAUGHT SOURCE DRIFT: " + label)
        else:
            raise AssertionError("source drift survivor: " + label)


PREFIX = StringPrefix = r"""
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <unordered_map>
using uint32 = std::uint32_t;
using uint64 = std::uint64_t;
using int32 = std::int32_t;
constexpr uint32 MAX_MONEY_AMOUNT = 1000; // SMALL SYNTHETIC cap, not live server value!
constexpr int CONFIG_TRIAL_MONEY_CAP = 1;
constexpr int EQUIP_ERR_TOO_MUCH_GOLD = 1;
uint32 HonorOverflowCopperPerHonor = 1; // SYNTHETIC rate, not config claim.

struct Session {
    bool trial = false;
    bool IsTrialAccount() const { return trial; }
};
struct World {
    uint32 trialMoneyCap = 0;
    uint32 getIntConfig(int) const { return trialMoneyCap; }
} world;
World* sWorld = &world;
class Player;
struct Scripts {
    uint32 moneyHookCalls = 0;
    void OnPlayerMoneyChanged(Player*, int32) { ++moneyHookCalls; }
} scripts;
Scripts* sScriptMgr = &scripts;
struct Guid {
    uint32 counter = 11;
    uint32 GetCounter() const { return counter; }
};
class Player {
public:
    Player(uint32 start, bool isTrial) : money(start) { session.trial = isTrial; }
    uint32 GetMoney() const { return money; }
    void SetMoney(uint32 value) { money = value; }
    Session* GetSession() { return &session; }
    Guid GetGUID() const { return {}; }
    void SendEquipError(int, void*, void*) { ++equipErrors; }
    bool ModifyMoney(int32 amount, bool sendError = true);
    uint32 equipErrors = 0;
private:
    uint32 money;
    Session session;
};
struct BattlegroundHonorSummary {
    uint64 ExcessHonor = 0;
    uint64 RequestedCopper = 0;
    uint64 AwardedCopper = 0;
};
std::unordered_map<uint32, BattlegroundHonorSummary> BattlegroundHonorSummaries;
void Require(bool yes, char const* what) { if (!yes) throw std::runtime_error(what); }
"""

SUFFIX = r"""
struct ProposedResult {
    uint64 requested;
    uint32 proposed;
};
ProposedResult SimulatePinnedProposedReward(Player* player, uint32 excessHonor) {
__EARN__
    // Source-checked original module BG call passes this proposed number,
    // rather than the bool result returned by ModifyMoney.
    AddBattlegroundSummary(player, excessHonor, requestedCopper, rewardCopper);
    return {requestedCopper, rewardCopper};
}
void CheckCase(char const* name, uint32 starting, uint32 honor,
               bool trial, uint32 trialCap, uint32 proposed, uint32 actual,
               bool originalModifySuccess) {
    world.trialMoneyCap = trialCap;
    Player control(starting, trial);
    bool directSucceeded = true;
    if (proposed)
        directSucceeded = control.ModifyMoney(static_cast<int32>(proposed));
    Require(directSucceeded == originalModifySuccess, "literal ModifyMoney bool changed");
    Require(control.GetMoney() - starting == actual, "literal ModifyMoney actual delta changed");

    BattlegroundHonorSummaries.clear();
    Player player(starting, trial);
    ProposedResult r = SimulatePinnedProposedReward(&player, honor);
    Require(r.proposed == proposed, "actual extracted module reward proposal changed");
    Require(player.GetMoney() - starting == actual, "real money mutation differed");
    Require(BattlegroundHonorSummaries[11].AwardedCopper == proposed,
            "original BG summary not the proposed/uncorroborated amount");
    if (proposed != actual)
        std::cout << "MISMATCH: " << name << " proposed=" << proposed
                  << " actual=" << actual << "\n";
    else
        std::cout << "MATCH: " << name << " proposed=" << proposed << "\n";
}
int main() {
    try {
        CheckCase("ordinary below cap", 100, 200, false, 0, 200, 200, true);
        CheckCase("one below cap", 900, 99, false, 0, 99, 99, true);
        CheckCase("exact ordinary cap equality", 900, 100, false, 0, 100, 0, false);
        CheckCase("clipped to exact ordinary cap", 900, 200, false, 0, 100, 0, false);
        CheckCase("trial cap rejection", 500, 200, true, 600, 200, 0, false);
        CheckCase("trial under cap", 500, 50, true, 600, 50, 50, true);
        CheckCase("already at ordinary cap", 1000, 200, false, 0, 0, 0, true);
        std::cout << "PASS: P13-R10 pinned proposed-vs-credited boundary, 7 synthetic cases\n";
        std::cout << "LIMIT: no actual owner Worldserver, real money cap, "
                     "player payout, installed config or gameplay proof\n";
        return 0;
    } catch (std::exception const& e) {
        std::cerr << "FAIL: " << e.what() << "\n";
        return 1;
    }
}
"""


def compiled_witness(earn, summary, money):
    cpp = PREFIX + "\n" + money + "\n" + summary + "\n" + SUFFIX.replace("__EARN__", earn)
    with tempfile.TemporaryDirectory(prefix="p13_r10_") as scratch:
        root = pathlib.Path(scratch)
        src = root / "witness.cpp"
        src.write_text(cpp)
        for std, extra in [
            ("c++17", []),
            ("c++20", []),
            ("c++20-ubsan", ["-O1", "-g", "-fsanitize=undefined", "-fno-sanitize-recover=all"]),
        ]:
            exe = root / std
            standard = "c++20" if std == "c++20-ubsan" else std
            cmd = ["g++", f"-std={standard}", "-Wall", "-Wextra", "-Werror",
                   "-Wshadow", "-pedantic", *extra, str(src), "-o", str(exe)]
            subprocess.run(cmd, check=True)
            out = subprocess.run([str(exe)], check=True, text=True, capture_output=True).stdout
            assert "MISMATCH: exact ordinary cap equality proposed=100 actual=0" in out
            assert "MISMATCH: clipped to exact ordinary cap proposed=100 actual=0" in out
            assert "MISMATCH: trial cap rejection proposed=200 actual=0" in out
            assert out.count("MISMATCH:") == 3 and out.count("MATCH:") == 4, out
            assert "PASS: P13-R10 pinned proposed-vs-credited boundary, 7 synthetic cases" in out
            print(f"PASS: {std} literal-source 7-case accounting fixture")
        print("LIMIT: source-compiled payout branch with dummy Player and synthetic caps only")


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    mod, core = [pathlib.Path(arg) for arg in argv[1:]]
    assert_pins(mod, core)
    module_src = (mod / MOD_FILE).read_text()
    core_src = (core / CORE_FILE).read_text()
    earn, summary, money = verify(module_src, core_src)
    print("PASS: original pinned HonorOverflow and Player::ModifyMoney source")
    negative_guards(module_src, core_src)
    compiled_witness(earn, summary, money)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except (AssertionError, subprocess.CalledProcessError, ValueError) as error:
        print("FAIL: " + str(error))
        sys.exit(1)
